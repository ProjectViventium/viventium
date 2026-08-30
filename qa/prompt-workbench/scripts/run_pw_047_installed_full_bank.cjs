#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const RUNNER_ID = "PW-047";
const AUTHORIZATION_ENV = "VIVENTIUM_QA_ALLOW_PW_047_INSTALLED_FULL_BANK";
const DEFAULT_ORIGIN = "http://127.0.0.1:8781";
const APP_SUPPORT_ROOT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
);
const WORKBENCH_PRIVATE_ROOT = path.join(
  APP_SUPPORT_ROOT,
  "private-user-data",
  "prompt-workbench",
);
const DEFAULT_EVIDENCE_ROOT = path.join(
  APP_SUPPORT_ROOT,
  "private-user-data",
  "qa",
  "prompt-workbench-pw-047",
);
const NATIVE_SURFACES = new Set([
  "telegram",
  "voice",
  "wing",
  "listen_only",
  "scheduler",
]);
const RUN_ID_PATTERN = /^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$/;
const ID_PATTERN = /^[A-Za-z0-9_.:-]{1,160}$/;
const HASH_16_PATTERN = /^[0-9a-f]{16}$/;
const HASH_64_PATTERN = /^[0-9a-f]{64}$/;
const MAX_API_BYTES = 32 * 1024 * 1024;
const MAX_PRIVATE_ARTIFACT_BYTES = 256 * 1024 * 1024;
const MAX_CLEANUP_FILES = 32;
const MAX_CLEANUP_BYTES = 512 * 1024 * 1024;
const STANDARD_FAILURE_FIELDS = Object.freeze([
  "failedCount",
  "semanticFailedCount",
  "semanticJudgeUnavailableCount",
  "duplicateResponseQualityFailureCount",
  "unresolvedAsyncQualityFailureCount",
]);
const ACTIVATION_FAILURE_FIELDS = Object.freeze([
  "failureCount",
  "failedCaseRunCount",
  "falsePositiveCount",
  "falseNegativeCount",
  "unavailableCount",
  "unavailableRequiredCount",
  "timeoutOrProviderErrorCount",
  "inconsistentDecisionCount",
  "semanticInconsistentDecisionCount",
]);
const CANONICAL_ARTIFACT_NAMES = new Set([
  "exact-model-eval.json",
  "native-surface-playwright-qa.json",
  "activation-model-eval.json",
]);
const FORBIDDEN_PUBLIC_KEYS =
  /^(?:rawPrompt|rawResponse|promptText|promptBody|renderedPrompt|requestBody|responseBody|providerRequestBody|providerResponseBody|authorization|bearer|token|secret|password|credential|cookie|transcript|userEmail)$/i;
const PRIVATE_STRING_PATTERNS = Object.freeze([
  /\bBearer\s+[A-Za-z0-9._~+\/-]+=*/i,
  /\b(?:authorization|api[_-]?key|token|secret|password|credential)\s*[:=]\s*[^\s,}]+/i,
  /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
  /\/Users\/[^\s)"']+/,
  /[?&](?:access_token|auth|authorization|key|secret|token|workbench_token)=/i,
]);
const PUBLIC_RUN_KEYS = new Set([
  "id",
  "mode",
  "returnCode",
  "resultCount",
  "selectedCaseCount",
  "cases",
  "createdAt",
  "live",
  "maxCases",
  "family",
  "surface",
  "promptId",
  "promptHash",
  "selectedCaseIds",
  "lineageManifest",
  "executionTarget",
  "executionRoute",
  "semanticJudgeRequired",
  "runnerSummary",
  "timeoutSeconds",
  "command",
  "stdoutTail",
  "stderrTail",
  "candidateSourceHash",
  "privateOutputAvailable",
  "artifactName",
]);
const PUBLIC_SUMMARY_KEYS = new Set([
  "status",
  "blockedReason",
  "mode",
  "familyId",
  "sourceBundleHash",
  "promptBankHash",
  "providerOverride",
  "modelOverride",
  "fallbacksEnabled",
  "selectedCaseCount",
  "selectedTargetCount",
  "repetitions",
  "resultCount",
  "completedCount",
  "passCount",
  "failureCount",
  "failedCount",
  "failedCaseRunCount",
  "falsePositiveCount",
  "falseNegativeCount",
  "unavailableCount",
  "unavailableRequiredCount",
  "timeoutOrProviderErrorCount",
  "inconsistentDecisionCount",
  "semanticInconsistentDecisionCount",
  "semanticJudgedCount",
  "semanticPassedCount",
  "semanticFailedCount",
  "semanticJudgeUnavailableCount",
  "duplicateResponseQualityFailureCount",
  "unresolvedAsyncQualityFailureCount",
]);
const PUBLIC_ROUTE_KEYS = new Set([
  "status",
  "reason",
  "requestedProvider",
  "requestedModel",
  "requestedEffort",
  "effectiveProvider",
  "effectiveModel",
  "effectiveEffort",
  "fallbackUsed",
  "fallbackAuthorized",
  "fallbackReason",
  "configuredProvider",
  "configuredModel",
  "configuredProviderHash",
  "configuredModelHash",
  "observedProviderHash",
  "observedModelHash",
  "completedCaseCount",
  "artifactSha256",
  "routes",
  "caseEvidence",
  "routeExecution",
]);
const PUBLIC_ROUTE_VARIANT_KEYS = new Set([
  "targetKey",
  "requestedProvider",
  "requestedModel",
  "requestedEffort",
  "configuredProvider",
  "configuredModel",
  "effectiveProvider",
  "effectiveModel",
  "effectiveEffort",
  "fallbackUsed",
  "fallbackAuthorized",
  "fallbackReason",
]);
const PUBLIC_CASE_EVIDENCE_KEYS = new Set([
  "caseId",
  "agentIdHash",
  "requestIdentityHash",
  "surface",
  "completionSurface",
  "completionExpected",
  "semanticJudged",
  "semanticPassed",
  "targetKey",
  "repetition",
  "required",
  "allowed",
  "actual",
  "passed",
  "requestedProvider",
  "requestedModel",
  "requestedEffort",
  "effectiveProvider",
  "effectiveModel",
  "effectiveEffort",
  "fallbackReason",
  "primaryFailureVerified",
]);
const TYPED_FALLBACK_REASONS = new Set([
  "provider_access_denied",
  "provider_auth_missing",
  "provider_connected_account_reconnect_required",
  "provider_error",
  "provider_invalid_response",
  "provider_network",
  "provider_quota_exhausted",
  "provider_quota_or_billing",
  "provider_rate_limited",
  "provider_response_deadline_exceeded",
  "provider_response_failed",
  "provider_server_error",
  "provider_temporarily_unavailable",
  "provider_timeout",
  "provider_unauthorized",
]);
const PUBLIC_LINEAGE_KEYS = new Set([
  "schemaVersion",
  "familyIds",
  "caseIds",
  "rootPromptIds",
  "promptDependencies",
  "runtimeContextDependencies",
  "includeEdges",
  "executionTarget",
  "promptCount",
  "runtimeContextCount",
  "manifestHash",
]);
const PUBLIC_PROMPT_DEPENDENCY_KEYS = new Set([
  "id",
  "kind",
  "status",
  "direct",
  "path",
  "contentHash",
  "bodyHash",
  "renderedHash",
  "deliveryKind",
  "deliveryTarget",
]);
const PUBLIC_RUNTIME_DEPENDENCY_KEYS = new Set([
  "id",
  "kind",
  "status",
  "tag",
  "lifecycle",
  "owner",
  "valuePolicy",
  "roleContract",
  "contractHash",
]);

function fail(code) {
  throw new Error(code);
}

function sha(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(Buffer.isBuffer(value) ? value : String(value))
    .digest("hex")
    .slice(0, length);
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function jsonHash(value) {
  return sha(stableStringify(value), 64);
}

function safeError(value) {
  return String(value || "pw_047_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(
      /(?:authorization|bearer|token|secret|password|credential)[=: ]+[^\s,}]+/gi,
      "$1=<redacted>",
    )
    .replace(/\s+/g, " ")
    .slice(0, 240);
}

function strictLoopbackOrigin(value) {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    fail("token_free_loopback_origin_required");
  }
  if (
    parsed.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname) ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    fail("token_free_loopback_origin_required");
  }
  return parsed.origin;
}

function flagParts(argv) {
  const flags = new Set();
  const values = new Map();
  for (const item of argv) {
    if (!item.startsWith("--")) fail("unsupported_pw_047_argument");
    const separator = item.indexOf("=");
    if (separator === -1) flags.add(item);
    else values.set(item.slice(0, separator), item.slice(separator + 1));
  }
  return { flags, values };
}

function containedPath(root, candidate, errorCode) {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = path.resolve(candidate);
  if (
    resolvedCandidate !== resolvedRoot &&
    !resolvedCandidate.startsWith(`${resolvedRoot}${path.sep}`)
  ) {
    fail(errorCode);
  }
  return resolvedCandidate;
}

function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const { flags, values } = flagParts(argv);
  const cleanupOnly = flags.has("--cleanup-only");
  if (!flags.has("--local-qa")) {
    fail("explicit_local_full_bank_authorization_required");
  }
  if (env[AUTHORIZATION_ENV] !== "1") {
    fail(`${AUTHORIZATION_ENV}_required`);
  }
  if (env.CI || env.NODE_ENV === "production") {
    fail("installed_local_qa_forbidden_in_ci_or_production");
  }
  const origin = strictLoopbackOrigin(values.get("--origin") || DEFAULT_ORIGIN);
  const evidenceRoot = containedPath(
    DEFAULT_EVIDENCE_ROOT,
    values.get("--evidence-root") || DEFAULT_EVIDENCE_ROOT,
    "private_evidence_root_required",
  );
  if (cleanupOnly) {
    if (
      flags.has("--run-live") ||
      flags.has("--allow-live-eval") ||
      flags.has("--full-current-bank")
    ) {
      fail("cleanup_only_cannot_run_models");
    }
    const manifestValue = values.get("--manifest");
    if (!manifestValue) fail("cleanup_manifest_required");
    const manifestPath = containedPath(
      evidenceRoot,
      manifestValue,
      "owned_cleanup_scope_invalid",
    );
    return {
      mode: "cleanup",
      origin,
      evidenceRoot,
      manifestPath,
      authorizationConfirmed: true,
      live: false,
    };
  }
  if (
    !flags.has("--full-current-bank") ||
    !flags.has("--allow-live-eval") ||
    !flags.has("--run-live")
  ) {
    fail("explicit_local_full_bank_authorization_required");
  }
  const timeoutMs = Number.parseInt(
    values.get("--timeout-ms") || "14500000",
    10,
  );
  if (
    !Number.isInteger(timeoutMs) ||
    timeoutMs < 60_000 ||
    timeoutMs > 16_200_000
  ) {
    fail("invalid_family_run_timeout");
  }
  return {
    mode: "run",
    origin,
    evidenceRoot,
    timeoutMs,
    authorizationConfirmed: true,
    live: true,
  };
}

function assertStringId(value, missingCode) {
  if (typeof value !== "string" || !ID_PATTERN.test(value)) fail(missingCode);
  return value;
}

function assertEffort(value, missingCode = "execution_effort_lineage_missing") {
  const effort = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9._:-]{0,31}$/.test(effort)) fail(missingCode);
  return effort;
}

function exactUniqueStrings(value, invalidCode) {
  if (
    !Array.isArray(value) ||
    value.some((item) => typeof item !== "string" || !ID_PATTERN.test(item)) ||
    new Set(value).size !== value.length
  ) {
    fail(invalidCode);
  }
  return [...value];
}

function normalizeRunner(value) {
  const runner = String(value || "").trim();
  if (!runner) return "main";
  if (!["background_execution", "background_activation"].includes(runner)) {
    fail("eval_family_runner_invalid");
  }
  return runner;
}

function validateEvalBank(bank) {
  if (!bank || typeof bank !== "object" || Array.isArray(bank)) {
    fail("eval_bank_invalid");
  }
  if (!Number.isInteger(bank.version) || bank.version < 1) {
    fail("eval_bank_version_invalid");
  }
  if (!Array.isArray(bank.families) || bank.families.length === 0) {
    fail("eval_family_missing");
  }
  if (bank.familyCount !== bank.families.length) {
    fail("eval_family_count_drift");
  }
  const familyIds = new Set();
  const globalCaseIds = new Set();
  const families = [];
  for (const rawFamily of bank.families) {
    if (!rawFamily || typeof rawFamily !== "object") {
      fail("eval_family_missing");
    }
    const id = assertStringId(rawFamily.id, "eval_family_id_missing");
    if (familyIds.has(id)) fail("duplicate_eval_family_id");
    familyIds.add(id);
    if (!Array.isArray(rawFamily.cases) || rawFamily.cases.length === 0) {
      fail("eval_case_missing");
    }
    const runner = normalizeRunner(rawFamily.runner);
    const cases = [];
    for (const rawCase of rawFamily.cases) {
      if (!rawCase || typeof rawCase !== "object") fail("eval_case_missing");
      const caseId = assertStringId(rawCase.id, "eval_case_id_missing");
      if (globalCaseIds.has(caseId)) fail("duplicate_eval_case_id");
      globalCaseIds.add(caseId);
      const surface = assertStringId(
        rawCase.surface,
        "eval_case_surface_missing",
      );
      cases.push({
        id: caseId,
        surface,
        semanticJudgeRequired: rawCase.semanticJudge === true,
        requiredActivations: [],
        allowedActivations: [],
      });
    }
    let executionTarget = null;
    let activationTargets = [];
    if (runner === "background_execution") {
      const target = rawFamily.executionTarget;
      if (!target || typeof target !== "object") {
        fail("specialist_execution_target_missing");
      }
      executionTarget = {
        agentId: assertStringId(
          target.agentId,
          "specialist_execution_target_missing",
        ),
        promptRef: assertStringId(
          target.promptRef,
          "specialist_execution_target_missing",
        ),
      };
    }
    if (runner === "background_activation") {
      if (
        !Array.isArray(rawFamily.activationTargets) ||
        rawFamily.activationTargets.length === 0
      ) {
        fail("activation_target_missing");
      }
      const targetKeys = new Set();
      activationTargets = rawFamily.activationTargets.map((target) => {
        if (!target || typeof target !== "object") {
          fail("activation_target_missing");
        }
        const key = assertStringId(target.key, "activation_target_missing");
        if (targetKeys.has(key)) fail("duplicate_activation_target");
        targetKeys.add(key);
        return {
          key,
          agentId: assertStringId(target.agentId, "activation_target_missing"),
          promptRef: assertStringId(
            target.promptRef,
            "activation_target_missing",
          ),
        };
      });
      for (let index = 0; index < rawFamily.cases.length; index += 1) {
        const rawCase = rawFamily.cases[index];
        const required = exactUniqueStrings(
          rawCase.required_activations,
          "activation_case_contract_invalid",
        );
        const allowed = exactUniqueStrings(
          rawCase.allowed_activations,
          "activation_case_contract_invalid",
        );
        if (
          required.some((key) => !allowed.includes(key)) ||
          allowed.some((key) => !targetKeys.has(key))
        ) {
          fail("activation_case_contract_invalid");
        }
        cases[index].requiredActivations = required;
        cases[index].allowedActivations = allowed;
      }
    }
    families.push({
      id,
      runner,
      semanticJudgeRequired: rawFamily.semanticJudge === true,
      executionTarget,
      activationTargets,
      cases,
    });
  }
  if (bank.caseCount !== globalCaseIds.size) {
    fail("eval_case_count_drift");
  }
  const identity = {
    version: bank.version,
    familyCount: families.length,
    caseCount: globalCaseIds.size,
    families: families.map((family) => ({
      id: family.id,
      runner: family.runner,
      semanticJudgeRequired: family.semanticJudgeRequired,
      executionTarget: family.executionTarget,
      activationTargets: family.activationTargets,
      cases: family.cases,
    })),
  };
  const allCaseIds = families.flatMap((family) =>
    family.cases.map((testCase) => testCase.id),
  );
  return {
    version: bank.version,
    familyCount: families.length,
    caseCount: globalCaseIds.size,
    families,
    familyIds: families.map((family) => family.id),
    caseIds: allCaseIds,
    bankHash: jsonHash(identity),
    familySetHash: jsonHash(families.map((family) => family.id).sort()),
    caseSetHash: jsonHash([...allCaseIds].sort()),
  };
}

function validateBuild(build) {
  const backend = build?.backend;
  if (
    build?.available !== true ||
    !HASH_16_PATTERN.test(String(build.indexHash || "")) ||
    !Array.isArray(build.entryAssets) ||
    build.entryAssets.length === 0 ||
    build.entryAssets.some(
      (asset) =>
        typeof asset !== "string" ||
        !asset.startsWith("/assets/") ||
        asset.includes("?") ||
        asset.includes("#"),
    )
  ) {
    fail("installed_frontend_build_unavailable");
  }
  if (
    !backend ||
    backend.sourceCurrent !== true ||
    !HASH_16_PATTERN.test(String(backend.loadedSourceHash || "")) ||
    backend.loadedSourceHash !== backend.currentSourceHash
  ) {
    fail("installed_backend_source_stale");
  }
  return {
    sourceHash: backend.currentSourceHash,
    buildHash: build.indexHash,
    liveRuntimeHash: backend.loadedSourceHash,
    entryAssetSetHash: jsonHash([...build.entryAssets].sort()),
  };
}

function validateMainOwner(context) {
  const sync = context?.sync;
  if (
    context?.promptId !== "main.identity" ||
    context?.delivery?.state !== "synced" ||
    !sync ||
    sync.state !== "synced" ||
    !ID_PATTERN.test(String(sync.agentId || "")) ||
    !HASH_16_PATTERN.test(String(sync.sourceHash || "")) ||
    sync.sourceHash !== sync.liveHash
  ) {
    fail("configured_main_agent_identity_unavailable");
  }
  return sync.agentId;
}

function assertConfiguredRoute(route, family) {
  if (
    !route ||
    typeof route !== "object" ||
    route.kind !== family.runner ||
    route.family !== family.id
  ) {
    fail("configured_execution_route_unavailable");
  }
  if (family.runner === "background_activation") {
    if (!Array.isArray(route.targets) || route.targets.length === 0) {
      fail("configured_activation_route_unavailable");
    }
    const declaredKeys = new Set(
      family.activationTargets.map((target) => target.key),
    );
    const observedKeys = new Set();
    for (const target of route.targets) {
      const key = assertStringId(
        target?.targetKey,
        "configured_activation_route_unavailable",
      );
      if (observedKeys.has(key) || !declaredKeys.has(key)) {
        fail("configured_activation_route_unavailable");
      }
      observedKeys.add(key);
      if (
        !String(target.provider || "").trim() ||
        !String(target.model || "").trim() ||
        !String(target.effort || "").trim() ||
        !Array.isArray(target.fallbacks)
      ) {
        fail("configured_activation_route_unavailable");
      }
      const primaryEffort = assertEffort(
        target.effort,
        "configured_activation_route_unavailable",
      );
      const variants = new Set([
        `${target.provider}\u0000${target.model}\u0000${primaryEffort}`,
      ]);
      for (const fallback of target.fallbacks) {
        const provider = String(fallback?.provider || "").trim();
        const model = String(fallback?.model || "").trim();
        const effort = assertEffort(
          fallback?.effort,
          "configured_activation_route_unavailable",
        );
        const variant = `${provider}\u0000${model}\u0000${effort}`;
        if (!provider || !model || variants.has(variant)) {
          fail("configured_activation_route_unavailable");
        }
        variants.add(variant);
      }
    }
    if (
      observedKeys.size !== declaredKeys.size ||
      [...declaredKeys].some((key) => !observedKeys.has(key))
    ) {
      fail("configured_activation_route_unavailable");
    }
    return;
  }
  if (
    !String(route.provider || "").trim() ||
    !String(route.model || "").trim() ||
    !String(route.effort || "").trim() ||
    !Array.isArray(route.fallbacks)
  ) {
    fail("configured_execution_route_unavailable");
  }
  const variants = new Set([
    `${route.provider}\u0000${route.model}\u0000${assertEffort(route.effort)}`,
  ]);
  for (const fallback of route.fallbacks) {
    const provider = String(fallback?.provider || "").trim();
    const model = String(fallback?.model || "").trim();
    const effort = assertEffort(fallback?.effort);
    const variant = `${provider}\u0000${model}\u0000${effort}`;
    if (!provider || !model || variants.has(variant)) {
      fail("configured_execution_route_unavailable");
    }
    variants.add(variant);
  }
  if (family.runner === "background_execution") {
    if (
      route.agentId !== family.executionTarget.agentId ||
      route.promptRef !== family.executionTarget.promptRef
    ) {
      fail("configured_specialist_identity_mismatch");
    }
  }
}

function validatePlanCoverage(catalog, plans) {
  if (!Array.isArray(plans) || plans.length === 0) {
    fail("eval_surface_plan_missing");
  }
  const expectedGroups = new Map();
  for (const family of catalog.families) {
    const groups = new Map();
    for (const testCase of family.cases) {
      if (!groups.has(testCase.surface)) groups.set(testCase.surface, []);
      groups.get(testCase.surface).push(testCase);
    }
    for (const [surface, cases] of groups) {
      expectedGroups.set(`${family.id}\u0000${surface}`, {
        family,
        surface,
        cases,
      });
    }
  }

  const observedGroups = new Set();
  const observedCases = new Set();
  const planIdentityRows = [];
  for (const plan of plans) {
    const familyId = assertStringId(
      plan?.familyId,
      "eval_surface_plan_invalid",
    );
    const surface = assertStringId(plan?.surface, "eval_surface_plan_invalid");
    const groupKey = `${familyId}\u0000${surface}`;
    if (observedGroups.has(groupKey)) fail("duplicate_eval_surface_plan");
    observedGroups.add(groupKey);
    const expected = expectedGroups.get(groupKey);
    if (!expected) fail("eval_surface_plan_invalid");
    const caseIds = exactUniqueStrings(
      plan.caseIds,
      "eval_surface_plan_case_mismatch",
    );
    const expectedCaseIds = expected.cases.map((testCase) => testCase.id);
    const expectedNativeSurface = NATIVE_SURFACES.has(surface) ? surface : null;
    const expectedSemanticJudge =
      expected.family.runner === "background_execution" ||
      expected.family.semanticJudgeRequired ||
      expected.cases.some((testCase) => testCase.semanticJudgeRequired);
    const expectedArtifactName =
      expected.family.runner === "background_activation"
        ? "activation-model-eval.json"
        : expectedNativeSurface
          ? "native-surface-playwright-qa.json"
          : "exact-model-eval.json";
    if (
      plan.family?.id !== familyId ||
      plan.runner !== expected.family.runner ||
      stableStringify(caseIds) !== stableStringify(expectedCaseIds) ||
      plan.caseIdsHash !== jsonHash(expectedCaseIds) ||
      plan.nativeSurface !== expectedNativeSurface ||
      plan.semanticJudgeRequired !== expectedSemanticJudge ||
      plan.canonicalArtifactName !== expectedArtifactName
    ) {
      fail("eval_surface_plan_case_mismatch");
    }
    for (const caseId of caseIds) {
      if (observedCases.has(caseId)) fail("duplicate_eval_plan_case");
      observedCases.add(caseId);
    }
    planIdentityRows.push({
      familyHash: sha(familyId, 64),
      surfaceHash: sha(surface, 64),
      nativeSurfaceHash: expectedNativeSurface
        ? sha(expectedNativeSurface, 64)
        : null,
      runner: plan.runner,
      caseIdsHash: plan.caseIdsHash,
      semanticJudgeRequired: plan.semanticJudgeRequired,
      canonicalArtifactName: plan.canonicalArtifactName,
    });
  }
  if (
    observedGroups.size !== expectedGroups.size ||
    [...expectedGroups.keys()].some((key) => !observedGroups.has(key))
  ) {
    fail("eval_surface_plan_missing");
  }
  if (
    observedCases.size !== catalog.caseCount ||
    [...catalog.caseIds].some((caseId) => !observedCases.has(caseId))
  ) {
    fail("eval_plan_case_coverage_missing");
  }
  return {
    surfacePlanCount: plans.length,
    executedCaseCount: plans.reduce(
      (count, plan) => count + plan.caseIds.length,
      0,
    ),
    uniqueExecutedCaseCount: observedCases.size,
    planSetHash: jsonHash(planIdentityRows),
  };
}

async function buildFamilyPlans({ catalog, configuredRoutes, mainAgentId }) {
  assertStringId(mainAgentId, "configured_main_agent_identity_unavailable");
  const plans = [];
  for (const family of catalog.families) {
    const route = configuredRoutes[family.id];
    assertConfiguredRoute(route, family);
    const surfaceGroups = new Map();
    for (const testCase of family.cases) {
      if (!surfaceGroups.has(testCase.surface)) {
        surfaceGroups.set(testCase.surface, []);
      }
      surfaceGroups.get(testCase.surface).push(testCase);
    }
    const expectedAgentId =
      family.runner === "background_execution"
        ? family.executionTarget.agentId
        : mainAgentId;
    for (const [surface, cases] of surfaceGroups) {
      const nativeSurface = NATIVE_SURFACES.has(surface) ? surface : null;
      const semanticJudgeRequired =
        family.runner === "background_execution" ||
        family.semanticJudgeRequired ||
        cases.some((testCase) => testCase.semanticJudgeRequired);
      if (family.runner === "background_activation" && semanticJudgeRequired) {
        fail(`family_installed_route_unavailable:${sha(family.id)}`);
      }
      const caseIds = cases.map((testCase) => testCase.id);
      plans.push({
        family,
        familyId: family.id,
        runner: family.runner,
        surface,
        caseIds,
        caseIdsHash: jsonHash(caseIds),
        nativeSurface,
        configuredRoute: route,
        expectedAgentHash: sha(expectedAgentId),
        semanticJudgeRequired,
        canonicalArtifactName:
          family.runner === "background_activation"
            ? "activation-model-eval.json"
            : nativeSurface
              ? "native-surface-playwright-qa.json"
              : "exact-model-eval.json",
      });
    }
  }
  validatePlanCoverage(catalog, plans);
  return plans;
}

function routeSetIdentity(plans) {
  const rows = plans.map((plan) => {
    if (plan.runner === "background_activation") {
      return {
        familyHash: sha(plan.familyId, 64),
        kind: plan.runner,
        ownerHash: jsonHash(
          plan.family.activationTargets.map((target) => target.agentId).sort(),
        ),
        targets: plan.configuredRoute.targets.map((target) => ({
          targetKeyHash: sha(target.targetKey, 64),
          providerHash: sha(target.provider, 64),
          modelHash: sha(target.model, 64),
          effort: target.effort,
          fallbackSetHash: jsonHash(
            target.fallbacks
              .map((fallback) => ({
                providerHash: sha(fallback.provider, 64),
                modelHash: sha(fallback.model, 64),
                effort: fallback.effort,
              }))
              .sort((left, right) =>
                stableStringify(left).localeCompare(stableStringify(right)),
              ),
          ),
        })),
      };
    }
    return {
      familyHash: sha(plan.familyId, 64),
      kind: plan.runner,
      ownerHash: plan.expectedAgentHash,
      providerHash: sha(plan.configuredRoute.provider, 64),
      modelHash: sha(plan.configuredRoute.model, 64),
      effort: plan.configuredRoute.effort,
      fallbackSetHash: jsonHash(
        plan.configuredRoute.fallbacks
          .map((fallback) => ({
            providerHash: sha(fallback.provider, 64),
            modelHash: sha(fallback.model, 64),
            effort: fallback.effort,
          }))
          .sort((left, right) =>
            stableStringify(left).localeCompare(stableStringify(right)),
          ),
      ),
    };
  });
  return {
    executionRouteSetHash: jsonHash(rows),
    configuredOwnerSetHash: jsonHash(rows.map((row) => row.ownerHash).sort()),
  };
}

function candidateIdentity(catalog, buildIdentity, plans) {
  const routeIdentity = routeSetIdentity(plans);
  const planCoverage = validatePlanCoverage(catalog, plans);
  const identity = {
    bankVersion: catalog.version,
    bankHash: catalog.bankHash,
    familyCount: catalog.familyCount,
    caseCount: catalog.caseCount,
    familySetHash: catalog.familySetHash,
    caseSetHash: catalog.caseSetHash,
    sourceHash: buildIdentity.sourceHash,
    buildHash: buildIdentity.buildHash,
    liveRuntimeHash: buildIdentity.liveRuntimeHash,
    entryAssetSetHash: buildIdentity.entryAssetSetHash,
    surfacePlanCount: planCoverage.surfacePlanCount,
    planSetHash: planCoverage.planSetHash,
    ...routeIdentity,
  };
  return { ...identity, candidateHash: jsonHash(identity) };
}

function assertOnlyKeys(value, allowed) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail("private_eval_output_exposed");
  }
  if (Object.keys(value).some((key) => !allowed.has(key))) {
    fail("private_eval_output_exposed");
  }
}

function assertPublicRunSchema(run) {
  assertOnlyKeys(run, PUBLIC_RUN_KEYS);
  if (run.runnerSummary != null) {
    assertOnlyKeys(run.runnerSummary, PUBLIC_SUMMARY_KEYS);
  }
  if (run.executionTarget != null) {
    assertOnlyKeys(
      run.executionTarget,
      new Set(["mode", "agentId", "promptRef"]),
    );
  }
  if (run.executionRoute != null) {
    assertOnlyKeys(run.executionRoute, PUBLIC_ROUTE_KEYS);
    for (const route of run.executionRoute.routes || []) {
      assertOnlyKeys(route, PUBLIC_ROUTE_VARIANT_KEYS);
    }
    for (const evidence of run.executionRoute.caseEvidence || []) {
      assertOnlyKeys(evidence, PUBLIC_CASE_EVIDENCE_KEYS);
    }
  }
  if (run.lineageManifest != null) {
    assertOnlyKeys(run.lineageManifest, PUBLIC_LINEAGE_KEYS);
    for (const dependency of run.lineageManifest.promptDependencies || []) {
      assertOnlyKeys(dependency, PUBLIC_PROMPT_DEPENDENCY_KEYS);
    }
    for (const dependency of run.lineageManifest.runtimeContextDependencies ||
      []) {
      assertOnlyKeys(dependency, PUBLIC_RUNTIME_DEPENDENCY_KEYS);
    }
    for (const edge of run.lineageManifest.includeEdges || []) {
      assertOnlyKeys(edge, new Set(["from", "to", "kind"]));
    }
    if (run.lineageManifest.executionTarget != null) {
      assertOnlyKeys(
        run.lineageManifest.executionTarget,
        new Set(["mode", "agentId", "promptRef"]),
      );
    }
  }
  for (const selected of run.cases || []) {
    assertOnlyKeys(selected, new Set(["family", "case", "surface"]));
  }
  if (
    run.command != null &&
    (!Array.isArray(run.command) ||
      run.command.some((item) => typeof item !== "string"))
  ) {
    fail("private_eval_output_exposed");
  }
}

function assertNoPrivateRunOutput(value, key = "") {
  if (FORBIDDEN_PUBLIC_KEYS.test(key)) fail("private_eval_output_exposed");
  if (typeof value === "string") {
    if (PRIVATE_STRING_PATTERNS.some((pattern) => pattern.test(value))) {
      fail("private_eval_output_exposed");
    }
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) assertNoPrivateRunOutput(item, key);
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [childKey, childValue] of Object.entries(value)) {
    assertNoPrivateRunOutput(childValue, childKey);
  }
}

function validateLineage(lineage, plan) {
  if (
    !lineage ||
    typeof lineage !== "object" ||
    lineage.schemaVersion !== 1 ||
    stableStringify(lineage.familyIds) !== stableStringify([plan.familyId]) ||
    stableStringify(lineage.caseIds) !== stableStringify(plan.caseIds) ||
    !Array.isArray(lineage.promptDependencies) ||
    !Array.isArray(lineage.runtimeContextDependencies) ||
    !Array.isArray(lineage.includeEdges) ||
    lineage.promptCount !== lineage.promptDependencies.length ||
    lineage.runtimeContextCount !== lineage.runtimeContextDependencies.length ||
    !HASH_16_PATTERN.test(String(lineage.manifestHash || ""))
  ) {
    fail("eval_lineage_mismatch");
  }
  const unsigned = { ...lineage };
  delete unsigned.manifestHash;
  if (sha(stableStringify(unsigned)) !== lineage.manifestHash) {
    fail("eval_lineage_mismatch");
  }
}

function parseRunTimestamp(runId) {
  if (!RUN_ID_PATTERN.test(String(runId || ""))) fail("eval_run_id_invalid");
  const stamp = runId.slice(0, 16);
  const parsed = Date.parse(
    `${stamp.slice(0, 4)}-${stamp.slice(4, 6)}-${stamp.slice(6, 8)}T${stamp.slice(9, 11)}:${stamp.slice(11, 13)}:${stamp.slice(13, 15)}Z`,
  );
  if (!Number.isFinite(parsed)) fail("eval_run_id_invalid");
  return parsed;
}

function validateRunFreshness(run, startedAtMs, nowMs) {
  const createdMs = Date.parse(String(run.createdAt || ""));
  const idMs = parseRunTimestamp(run.id);
  if (
    !Number.isFinite(createdMs) ||
    Math.abs(createdMs - idMs) > 300_000 ||
    createdMs < startedAtMs - 300_000 ||
    createdMs > nowMs + 300_000
  ) {
    fail("stale_eval_run");
  }
}

function assertNoSymlinkPath(root, candidate, code) {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = containedPath(resolvedRoot, candidate, code);
  const relative = path.relative(resolvedRoot, resolvedCandidate);
  let current = resolvedRoot;
  const rootStat = fs.lstatSync(current);
  if (rootStat.isSymbolicLink()) fail(code);
  for (const part of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    const stat = fs.lstatSync(current);
    if (stat.isSymbolicLink()) fail(code);
  }
  return resolvedCandidate;
}

function secureReadFile(root, candidate, code, maxBytes) {
  let resolved;
  try {
    resolved = assertNoSymlinkPath(root, candidate, code);
    const flags = fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0);
    const descriptor = fs.openSync(resolved, flags);
    try {
      const before = fs.fstatSync(descriptor);
      if (
        !before.isFile() ||
        before.nlink !== 1 ||
        before.size < 1 ||
        before.size > maxBytes
      ) {
        fail(code);
      }
      const bytes = fs.readFileSync(descriptor);
      const after = fs.fstatSync(descriptor);
      if (
        before.dev !== after.dev ||
        before.ino !== after.ino ||
        before.size !== after.size ||
        bytes.length !== before.size
      ) {
        fail(code);
      }
      return bytes;
    } finally {
      fs.closeSync(descriptor);
    }
  } catch (error) {
    if (error?.message === code) throw error;
    fail(code);
  }
}

function readCanonicalArtifact({ privateRoot, runId, artifactName }) {
  if (
    !RUN_ID_PATTERN.test(runId) ||
    !CANONICAL_ARTIFACT_NAMES.has(artifactName)
  ) {
    fail("private_eval_artifact_invalid");
  }
  const target = path.join(privateRoot, "eval-runs", runId, artifactName);
  const bytes = secureReadFile(
    privateRoot,
    target,
    "private_eval_artifact_invalid",
    MAX_PRIVATE_ARTIFACT_BYTES,
  );
  let payload;
  try {
    payload = JSON.parse(bytes.toString("utf8"));
  } catch {
    fail("private_eval_artifact_invalid");
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    fail("private_eval_artifact_invalid");
  }
  return { bytes, payload, artifactSha256: sha(bytes, 64) };
}

function assertZeroFields(summary, fields, code) {
  for (const field of fields) {
    const value = summary[field] ?? 0;
    if (!Number.isInteger(value) || value !== 0) fail(code);
  }
}

function routeTripleKey(provider, model, effort) {
  return `${String(provider || "").trim()}\u0000${String(model || "").trim()}\u0000${assertEffort(effort)}`;
}

function validateReceiptLineage(receipt, configured, mismatchCode) {
  const primary = routeTripleKey(
    configured.provider,
    configured.model,
    configured.effort,
  );
  if (
    receipt?.requestedProvider !== configured.provider ||
    receipt?.requestedModel !== configured.model
  ) {
    fail(mismatchCode);
  }
  if (
    !String(receipt?.requestedEffort || "").trim() ||
    !String(receipt?.effectiveEffort || "").trim()
  ) {
    fail("execution_effort_lineage_missing");
  }
  if (assertEffort(receipt.requestedEffort) !== assertEffort(configured.effort)) {
    fail(mismatchCode);
  }
  const effective = routeTripleKey(
    receipt?.effectiveProvider,
    receipt?.effectiveModel,
    receipt.effectiveEffort,
  );
  const allowed = new Set([
    primary,
    ...(configured.fallbacks || []).map((fallback) =>
      routeTripleKey(fallback.provider, fallback.model, fallback.effort),
    ),
  ]);
  if (!allowed.has(effective)) fail(mismatchCode);
  const fallbackUsed = effective !== primary;
  if (
    receipt.fallbackUsed !== fallbackUsed ||
    receipt.fallbackAuthorized !== fallbackUsed
  ) {
    fail("fallback_lineage_mismatch");
  }
  const reason = String(receipt.fallbackReason || "").trim().toLowerCase();
  if (fallbackUsed) {
    if (!TYPED_FALLBACK_REASONS.has(reason)) fail("fallback_reason_missing");
  } else if (reason !== "none") {
    fail(reason ? "fallback_reason_mismatch" : "fallback_reason_missing");
  }
  return { effective, fallbackUsed, reason };
}

function compareConfiguredStandardRoute(route, plan) {
  const configured = plan.configuredRoute;
  const providerHash = sha(configured.provider);
  const modelHash = sha(configured.model);
  if (
    route.status !== "verified" ||
    route.configuredProvider !== configured.provider ||
    route.configuredModel !== configured.model ||
    route.configuredProviderHash !== providerHash ||
    route.configuredModelHash !== modelHash
  ) {
    fail("configured_execution_route_mismatch");
  }
  validateReceiptLineage(route, configured, "configured_execution_route_mismatch");
  const effectiveProviderHash = sha(route.effectiveProvider);
  const effectiveModelHash = sha(route.effectiveModel);
  if (plan.nativeSurface === "listen_only") {
    if (route.routeExecution !== "suppressed_by_surface_contract") {
      fail("native_execution_route_mismatch");
    }
  } else if (
    route.observedProviderHash !== effectiveProviderHash ||
    route.observedModelHash !== effectiveModelHash
  ) {
    fail("configured_execution_route_mismatch");
  }
}

function validateStandardRun(run, plan) {
  const route = run.executionRoute;
  const summary = run.runnerSummary;
  if (plan.runner === "background_execution") {
    if (
      run.executionTarget?.mode !== "direct_background_agent" ||
      run.executionTarget.agentId !== plan.family.executionTarget.agentId ||
      run.executionTarget.promptRef !== plan.family.executionTarget.promptRef
    ) {
      fail("execution_agent_identity_mismatch");
    }
  } else if (run.executionTarget != null) {
    fail("execution_agent_identity_mismatch");
  }
  compareConfiguredStandardRoute(route, plan);
  if (
    !summary ||
    typeof summary !== "object" ||
    run.resultCount !== plan.caseIds.length ||
    summary.resultCount !== plan.caseIds.length ||
    summary.completedCount !== plan.caseIds.length ||
    route.completedCaseCount !== plan.caseIds.length
  ) {
    fail("eval_result_count_mismatch");
  }
  assertZeroFields(summary, STANDARD_FAILURE_FIELDS, "eval_quality_failure");
  const acceptableStatuses = plan.nativeSurface
    ? new Set([
        "completed_native_surface_evidence_without_semantic_judge",
        "completed_with_semantic_native_surface_evidence",
      ])
    : plan.semanticJudgeRequired
      ? new Set(["partial_semantic_passed", "completed_full_semantic_passed"])
      : new Set(["partial_baseline", "completed_full"]);
  if (!acceptableStatuses.has(summary.status)) {
    fail("eval_summary_status_invalid");
  }
  const evidenceRows = route.caseEvidence;
  if (
    !Array.isArray(evidenceRows) ||
    evidenceRows.length !== plan.caseIds.length
  ) {
    fail("eval_case_evidence_incomplete");
  }
  const seen = new Set();
  let judgedCount = 0;
  let passedCount = 0;
  for (const evidence of evidenceRows) {
    const caseId = evidence?.caseId;
    if (!plan.caseIds.includes(caseId) || seen.has(caseId)) {
      fail("eval_case_evidence_incomplete");
    }
    seen.add(caseId);
    const suppressed =
      plan.nativeSurface === "listen_only" &&
      evidence.completionExpected === false;
    if (
      suppressed
        ? evidence.agentIdHash !== "not_applicable"
        : evidence.agentIdHash !== plan.expectedAgentHash
    ) {
      fail("execution_agent_identity_mismatch");
    }
    if (plan.nativeSurface) {
      const expectedCompletionSurface =
        plan.nativeSurface === "telegram"
          ? "telegram"
          : plan.nativeSurface === "scheduler"
            ? "workbench"
            : "voice";
      if (
        evidence.surface !== plan.nativeSurface ||
        evidence.completionSurface !== expectedCompletionSurface ||
        evidence.completionExpected !== (plan.nativeSurface !== "listen_only")
      ) {
        fail("native_execution_surface_mismatch");
      }
    }
    if (
      typeof evidence.semanticJudged !== "boolean" ||
      typeof evidence.semanticPassed !== "boolean" ||
      (evidence.semanticPassed && !evidence.semanticJudged)
    ) {
      fail("semantic_judge_evidence_missing");
    }
    if (
      plan.semanticJudgeRequired &&
      (!evidence.semanticJudged || !evidence.semanticPassed)
    ) {
      fail("semantic_judge_evidence_missing");
    }
    judgedCount += Number(evidence.semanticJudged);
    passedCount += Number(evidence.semanticPassed);
  }
  if (seen.size !== plan.caseIds.length) fail("eval_case_evidence_incomplete");
  if (run.semanticJudgeRequired !== plan.semanticJudgeRequired) {
    fail("semantic_judge_contract_mismatch");
  }
  if (
    plan.semanticJudgeRequired &&
    (summary.semanticJudgedCount !== plan.caseIds.length ||
      summary.semanticPassedCount !== plan.caseIds.length ||
      judgedCount !== plan.caseIds.length ||
      passedCount !== plan.caseIds.length)
  ) {
    fail("semantic_judge_evidence_missing");
  }
}

function activationTargetMap(plan) {
  return new Map(
    plan.configuredRoute.targets.map((target) => [target.targetKey, target]),
  );
}

function activationAllowedRoutes(target) {
  return new Set([
    routeTripleKey(target.provider, target.model, target.effort),
    ...target.fallbacks.map(
      (fallback) =>
        routeTripleKey(fallback.provider, fallback.model, fallback.effort),
    ),
  ]);
}

function matchingCompletedAttempt(attempts, provider, model, effort) {
  return attempts.findIndex(
    (attempt) =>
      attempt?.status === "completed" &&
      attempt.provider === provider &&
      attempt.model === model &&
      attempt.effort === effort,
  );
}

function validateActivationArtifact({ artifact, run, plan }) {
  const summary = artifact?.summary;
  const results = artifact?.results;
  const targetMap = activationTargetMap(plan);
  if (
    !summary ||
    typeof summary !== "object" ||
    summary.mode !== "live" ||
    summary.status !== "passed" ||
    summary.familyId !== plan.familyId ||
    summary.selectedCaseCount !== plan.caseIds.length ||
    summary.selectedTargetCount !== targetMap.size ||
    !Number.isInteger(summary.repetitions) ||
    summary.repetitions < 1 ||
    summary.providerOverride !== null ||
    summary.modelOverride !== null ||
    summary.fallbacksEnabled !== true ||
    !Array.isArray(results)
  ) {
    fail("activation_canonical_summary_invalid");
  }
  const expectedCount =
    plan.caseIds.length * targetMap.size * summary.repetitions;
  if (
    results.length !== expectedCount ||
    summary.resultCount !== expectedCount ||
    summary.completedCount !== expectedCount ||
    summary.passCount !== expectedCount ||
    run.resultCount !== expectedCount ||
    run.executionRoute.completedCaseCount !== expectedCount
  ) {
    fail("activation_canonical_decision_coverage_incomplete");
  }
  assertZeroFields(
    summary,
    ACTIVATION_FAILURE_FIELDS,
    "activation_canonical_quality_failure",
  );
  const publicSummary = run.runnerSummary;
  for (const field of [
    "status",
    "selectedCaseCount",
    "selectedTargetCount",
    "repetitions",
    "resultCount",
    "completedCount",
    "passCount",
    ...ACTIVATION_FAILURE_FIELDS,
  ]) {
    if ((publicSummary?.[field] ?? 0) !== (summary[field] ?? 0)) {
      fail("activation_summary_not_canonical");
    }
  }
  const routeRows = run.executionRoute.routes;
  if (!Array.isArray(routeRows)) {
    fail("activation_target_route_coverage_incomplete");
  }
  const routeVariants = new Set();
  const routedTargets = new Set();
  for (const route of routeRows) {
    const target = targetMap.get(route?.targetKey);
    if (!target) fail("activation_execution_route_undeclared");
    if (
      route.configuredProvider !== target.provider ||
      route.configuredModel !== target.model
    ) {
      fail("activation_execution_route_undeclared");
    }
    const lineage = validateReceiptLineage(
      route,
      target,
      "activation_execution_route_undeclared",
    );
    const variant = `${route.targetKey}\u0000${lineage.effective}\u0000${lineage.reason}`;
    if (routeVariants.has(variant)) {
      fail("activation_target_route_coverage_incomplete");
    }
    routeVariants.add(variant);
    routedTargets.add(route.targetKey);
  }
  if (
    routedTargets.size !== targetMap.size ||
    [...targetMap.keys()].some((key) => !routedTargets.has(key))
  ) {
    fail("activation_target_route_coverage_incomplete");
  }
  const caseMap = new Map(
    plan.family.cases.map((testCase) => [testCase.id, testCase]),
  );
  const canonical = new Map();
  for (const row of results) {
    const testCase = caseMap.get(row?.caseId);
    const target = targetMap.get(row?.targetKey);
    const repetition = row?.repetition;
    const key = `${row?.caseId}\u0000${row?.targetKey}\u0000${repetition}`;
    if (
      !testCase ||
      !target ||
      !Number.isInteger(repetition) ||
      repetition < 1 ||
      repetition > summary.repetitions ||
      canonical.has(key)
    ) {
      fail("activation_canonical_decision_coverage_incomplete");
    }
    const required = testCase.requiredActivations.includes(row.targetKey);
    const allowed = testCase.allowedActivations.includes(row.targetKey);
    if (
      row.required !== required ||
      row.allowed !== allowed ||
      typeof row.actual !== "boolean" ||
      row.pass !== true ||
      (required && row.actual !== true) ||
      (row.actual && !allowed) ||
      row.error
    ) {
      fail("activation_canonical_decision_invalid");
    }
    if (
      !String(row.requestedEffort || "").trim() ||
      !String(row.effectiveEffort || "").trim() ||
      !String(row.effortUsed || "").trim()
    ) {
      fail("execution_effort_lineage_missing");
    }
    if (
      row.requestedProvider !== target.provider ||
      row.requestedModel !== target.model ||
      row.requestedEffort !== target.effort ||
      row.effectiveProvider !== row.providerUsed ||
      row.effectiveModel !== row.modelUsed ||
      row.effectiveEffort !== row.effortUsed
    ) {
      fail("activation_execution_route_undeclared");
    }
    const effective = routeTripleKey(
      row.providerUsed,
      row.modelUsed,
      row.effortUsed,
    );
    const primary = routeTripleKey(target.provider, target.model, target.effort);
    if (!activationAllowedRoutes(target).has(effective)) {
      fail("activation_execution_route_undeclared");
    }
    if (!Array.isArray(row.providerAttempts)) {
      fail("activation_provider_completion_unverified");
    }
    const completedIndex = matchingCompletedAttempt(
      row.providerAttempts,
      row.providerUsed,
      row.modelUsed,
      row.effortUsed,
    );
    if (completedIndex < 0) fail("activation_provider_completion_unverified");
    const fallbackUsed = effective !== primary;
    const fallbackReason = String(row.fallbackReason || "")
      .trim()
      .toLowerCase();
    if (fallbackUsed) {
      if (!TYPED_FALLBACK_REASONS.has(fallbackReason)) {
        fail("fallback_reason_missing");
      }
    } else if (fallbackReason !== "none") {
      fail(fallbackReason ? "fallback_reason_mismatch" : "fallback_reason_missing");
    }
    const completedAttempt = row.providerAttempts[completedIndex];
    if (
      completedAttempt.fallbackReason !== fallbackReason ||
      completedAttempt.source !== (fallbackUsed ? "fallback" : "primary")
    ) {
      fail("fallback_lineage_mismatch");
    }
    const primaryFailureVerified = row.providerAttempts
      .slice(0, completedIndex)
      .some(
        (attempt) =>
          attempt?.provider === target.provider &&
          attempt?.model === target.model &&
          attempt?.effort === target.effort &&
          ["error", "failed", "timeout", "unavailable"].includes(
            attempt.status,
          ),
      );
    if (fallbackUsed && !primaryFailureVerified) {
      fail("activation_primary_failure_unverified");
    }
    if (fallbackUsed) {
      const priorReason = [...row.providerAttempts.slice(0, completedIndex)]
        .reverse()
        .map((attempt) => String(attempt?.error?.class || "").trim().toLowerCase())
        .find(Boolean);
      if (priorReason !== fallbackReason) fail("fallback_reason_mismatch");
    }
    const variant = `${row.targetKey}\u0000${effective}\u0000${fallbackReason}`;
    if (!routeVariants.has(variant)) {
      fail("activation_target_route_coverage_incomplete");
    }
    canonical.set(key, {
      caseId: row.caseId,
      targetKey: row.targetKey,
      repetition,
      required,
      allowed,
      actual: row.actual,
      passed: true,
      requestedProvider: target.provider,
      requestedModel: target.model,
      requestedEffort: target.effort,
      effectiveProvider: row.providerUsed,
      effectiveModel: row.modelUsed,
      effectiveEffort: row.effortUsed,
      fallbackReason,
      primaryFailureVerified,
    });
  }
  const evidenceRows = run.executionRoute.caseEvidence;
  if (!Array.isArray(evidenceRows) || evidenceRows.length !== expectedCount) {
    fail("activation_public_decision_coverage_incomplete");
  }
  const publicKeys = new Set();
  for (const evidence of evidenceRows) {
    const key = `${evidence?.caseId}\u0000${evidence?.targetKey}\u0000${evidence?.repetition}`;
    const expected = canonical.get(key);
    if (publicKeys.has(key) || !expected) {
      fail("activation_public_decision_coverage_incomplete");
    }
    publicKeys.add(key);
    if (stableStringify(evidence) !== stableStringify(expected)) {
      fail("activation_public_decision_mismatch");
    }
  }
  if (publicKeys.size !== canonical.size) {
    fail("activation_public_decision_coverage_incomplete");
  }
  return expectedCount;
}

function validateRun({
  run,
  plan,
  candidate,
  privateRoot,
  startedAtMs,
  nowMs,
}) {
  if (!run || typeof run !== "object" || Array.isArray(run)) {
    fail("eval_run_invalid");
  }
  assertPublicRunSchema(run);
  assertNoPrivateRunOutput(run);
  validateRunFreshness(run, startedAtMs, nowMs);
  if (run.surface !== plan.surface) fail("execution_surface_mismatch");
  if (
    run.live !== true ||
    run.returnCode !== 0 ||
    run.family !== plan.familyId ||
    run.maxCases !== plan.caseIds.length ||
    run.selectedCaseCount !== plan.caseIds.length ||
    stableStringify(run.selectedCaseIds) !== stableStringify(plan.caseIds) ||
    run.candidateSourceHash !== candidate.sourceHash
  ) {
    fail("eval_run_selection_or_candidate_mismatch");
  }
  validateLineage(run.lineageManifest, plan);
  if (
    !run.executionRoute ||
    run.executionRoute.status !== "verified" ||
    !HASH_64_PATTERN.test(String(run.executionRoute.artifactSha256 || ""))
  ) {
    fail("backend_strict_artifact_verification_missing");
  }
  const canonical = readCanonicalArtifact({
    privateRoot,
    runId: run.id,
    artifactName: plan.canonicalArtifactName,
  });
  if (canonical.artifactSha256 !== run.executionRoute.artifactSha256) {
    fail("canonical_artifact_hash_mismatch");
  }
  let resultCount = plan.caseIds.length;
  if (plan.runner === "background_activation") {
    resultCount = validateActivationArtifact({
      artifact: canonical.payload,
      run,
      plan,
    });
  } else {
    validateStandardRun(run, plan);
  }
  return {
    runId: run.id,
    familyId: plan.familyId,
    familyHash: sha(plan.familyId, 64),
    caseIds: [...plan.caseIds],
    caseIdsHash: plan.caseIdsHash,
    caseCount: plan.caseIds.length,
    resultCount,
    routeKind: plan.runner,
    surface: plan.surface,
    surfaceHash: sha(plan.surface, 64),
    nativeSurfaceHash: plan.nativeSurface ? sha(plan.nativeSurface, 64) : null,
    configuredProviderHash:
      plan.runner === "background_activation"
        ? null
        : sha(plan.configuredRoute.provider, 64),
    configuredModelHash:
      plan.runner === "background_activation"
        ? null
        : sha(plan.configuredRoute.model, 64),
    configuredOwnerHash:
      plan.runner === "background_activation"
        ? jsonHash(
            plan.family.activationTargets
              .map((target) => target.agentId)
              .sort(),
          )
        : sha(plan.expectedAgentHash, 64),
    canonicalArtifactName: plan.canonicalArtifactName,
    canonicalArtifactSha256: canonical.artifactSha256,
    runEvidenceHash: runEvidenceHash(run),
  };
}

function runEvidenceShape(run) {
  return {
    id: run.id,
    family: run.family,
    live: run.live,
    returnCode: run.returnCode,
    resultCount: run.resultCount,
    selectedCaseCount: run.selectedCaseCount,
    selectedCaseIds: run.selectedCaseIds,
    surface: run.surface,
    createdAt: run.createdAt,
    candidateSourceHash: run.candidateSourceHash,
    semanticJudgeRequired: run.semanticJudgeRequired,
    lineageManifest: run.lineageManifest,
    runnerSummary: run.runnerSummary,
    executionTarget: run.executionTarget,
    executionRoute: run.executionRoute,
  };
}

function runEvidenceHash(run) {
  return jsonHash(runEvidenceShape(run));
}

function ensurePrivateDirectory(root) {
  fs.mkdirSync(root, { recursive: true, mode: 0o700 });
  fs.chmodSync(root, 0o700);
}

function writeJsonAtomic(target, payload) {
  const parent = path.dirname(target);
  ensurePrivateDirectory(parent);
  const temp = path.join(
    parent,
    `.${path.basename(target)}.${process.pid}.${crypto.randomBytes(6).toString("hex")}.tmp`,
  );
  let descriptor;
  try {
    descriptor = fs.openSync(
      temp,
      fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL,
      0o600,
    );
    fs.writeFileSync(descriptor, `${JSON.stringify(payload, null, 2)}\n`);
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    fs.renameSync(temp, target);
    fs.chmodSync(target, 0o600);
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    try {
      fs.unlinkSync(temp);
    } catch {
      // Nothing to recover.
    }
    throw error;
  }
}

function reportPaths(evidenceRoot, reportId, candidateHash) {
  const stem = `pw-047-${reportId}-${candidateHash.slice(0, 16)}`;
  return {
    privateAggregatePath: path.join(evidenceRoot, `${stem}.private.json`),
    publicSummaryPath: path.join(evidenceRoot, `${stem}.public.json`),
  };
}

function validateAggregateCoverage(catalog, plans, runs) {
  const planCoverage = validatePlanCoverage(catalog, plans);
  if (!Array.isArray(runs) || runs.length !== plans.length) {
    fail("eval_aggregate_surface_plan_missing");
  }
  const observedRunIds = new Set();
  const observedCaseIds = new Set();
  for (let index = 0; index < plans.length; index += 1) {
    const plan = plans[index];
    const run = runs[index];
    if (
      !run ||
      observedRunIds.has(run.runId) ||
      run.familyId !== plan.familyId ||
      run.surface !== plan.surface ||
      run.surfaceHash !== sha(plan.surface, 64) ||
      run.caseIdsHash !== plan.caseIdsHash ||
      stableStringify(run.caseIds) !== stableStringify(plan.caseIds)
    ) {
      fail("eval_aggregate_surface_plan_mismatch");
    }
    observedRunIds.add(run.runId);
    for (const caseId of exactUniqueStrings(
      run.caseIds,
      "eval_aggregate_case_coverage_mismatch",
    )) {
      if (observedCaseIds.has(caseId)) {
        fail("duplicate_eval_aggregate_case");
      }
      observedCaseIds.add(caseId);
    }
  }
  if (
    observedCaseIds.size !== catalog.caseCount ||
    [...catalog.caseIds].some((caseId) => !observedCaseIds.has(caseId))
  ) {
    fail("eval_aggregate_case_coverage_missing");
  }
  return {
    ...planCoverage,
    executedCaseSetHash: jsonHash([...observedCaseIds].sort()),
    runSetHash: jsonHash([...observedRunIds].sort()),
  };
}

function makePublicSummary(privateAggregate, privateAggregateSha256) {
  const runSetHash = jsonHash(
    privateAggregate.runs.map((run) => run.runEvidenceHash).sort(),
  );
  const executedCaseIds = privateAggregate.runs.flatMap(
    (run) => run.caseIds || [],
  );
  const uniqueExecutedCaseIds = [...new Set(executedCaseIds)].sort();
  return {
    schemaVersion: 1,
    qaCase: RUNNER_ID,
    status: privateAggregate.status,
    releaseEligible: false,
    candidateMode: "PRE-GATE / NOT READY",
    counts: {
      bankVersion: privateAggregate.candidate.bankVersion,
      familyCount: privateAggregate.candidate.familyCount,
      caseCount: privateAggregate.candidate.caseCount,
      surfacePlanCount: privateAggregate.candidate.surfacePlanCount,
      completedSurfacePlanCount: privateAggregate.runs.length,
      executedCaseCount: executedCaseIds.length,
      uniqueExecutedCaseCount: uniqueExecutedCaseIds.length,
      resultCount: privateAggregate.runs.reduce(
        (count, run) => count + (run.resultCount || 0),
        0,
      ),
      persistedRunCount: privateAggregate.persistedRunCount || 0,
      blockerCount: privateAggregate.status === "pass" ? 0 : 1,
    },
    hashes: {
      candidateHash: privateAggregate.candidate.candidateHash,
      bankHash: privateAggregate.candidate.bankHash,
      familySetHash: privateAggregate.candidate.familySetHash,
      caseSetHash: privateAggregate.candidate.caseSetHash,
      sourceHash: privateAggregate.candidate.sourceHash,
      buildHash: privateAggregate.candidate.buildHash,
      liveRuntimeHash: privateAggregate.candidate.liveRuntimeHash,
      entryAssetSetHash: privateAggregate.candidate.entryAssetSetHash,
      planSetHash: privateAggregate.candidate.planSetHash,
      executionRouteSetHash: privateAggregate.candidate.executionRouteSetHash,
      configuredOwnerSetHash: privateAggregate.candidate.configuredOwnerSetHash,
      executedCaseSetHash: jsonHash(uniqueExecutedCaseIds),
      runSetHash,
      privateAggregateSha256,
      blockerHash:
        privateAggregate.status === "pass"
          ? null
          : sha(privateAggregate.blocker || "blocked", 64),
    },
  };
}

function assertSameSourceCandidate(
  initialCatalog,
  currentBank,
  initialBuild,
  currentBuild,
) {
  const currentCatalog = validateEvalBank(currentBank);
  const currentBuildIdentity = validateBuild(currentBuild);
  if (currentCatalog.bankHash !== initialCatalog.bankHash) {
    fail("installed_eval_bank_drift");
  }
  if (stableStringify(currentBuildIdentity) !== stableStringify(initialBuild)) {
    fail("installed_candidate_build_drift");
  }
  return { currentCatalog, currentBuildIdentity };
}

async function verifyReadback({
  readbackDriver,
  trackedRuns,
  catalog,
  buildIdentity,
  plans,
  candidate,
}) {
  for (const tracked of trackedRuns) {
    let readback;
    try {
      readback = await readbackDriver.api(
        `/api/evals/runs/${encodeURIComponent(tracked.runId)}`,
      );
    } catch {
      fail("eval_history_readback_missing");
    }
    assertPublicRunSchema(readback);
    assertNoPrivateRunOutput(readback);
    if (runEvidenceHash(readback) !== tracked.runEvidenceHash) {
      fail("eval_history_readback_mismatch");
    }
  }
  const history = await readbackDriver.api("/api/evals/runs");
  if (!Array.isArray(history?.runs) || trackedRuns.length === 0) {
    fail("eval_history_readback_missing");
  }
  const historyRunCounts = new Map();
  for (const run of history.runs) {
    const runId = String(run?.id || "");
    historyRunCounts.set(runId, (historyRunCounts.get(runId) || 0) + 1);
  }
  if (
    trackedRuns.some((tracked) => historyRunCounts.get(tracked.runId) !== 1)
  ) {
    fail("eval_history_readback_missing");
  }
  const [currentBank, currentBuild, currentMainContext] = await Promise.all([
    readbackDriver.api("/api/evals"),
    readbackDriver.api("/api/build-version"),
    readbackDriver.api("/api/prompts/main.identity/workbench-context"),
  ]);
  const { currentCatalog, currentBuildIdentity } = assertSameSourceCandidate(
    catalog,
    currentBank,
    buildIdentity,
    currentBuild,
  );
  const currentMainAgentId = validateMainOwner(currentMainContext);
  const currentRoutes = {};
  for (const family of currentCatalog.families) {
    currentRoutes[family.id] = await readbackDriver.api(
      `/api/evals/execution-route?family=${encodeURIComponent(family.id)}`,
    );
  }
  const currentPlans = await buildFamilyPlans({
    catalog: currentCatalog,
    configuredRoutes: currentRoutes,
    mainAgentId: currentMainAgentId,
  });
  const currentCandidate = candidateIdentity(
    currentCatalog,
    currentBuildIdentity,
    currentPlans,
  );
  if (
    currentCandidate.executionRouteSetHash !==
      candidate.executionRouteSetHash ||
    currentCandidate.configuredOwnerSetHash !==
      candidate.configuredOwnerSetHash ||
    currentCandidate.planSetHash !== candidate.planSetHash ||
    currentCandidate.surfacePlanCount !== candidate.surfacePlanCount
  ) {
    fail("installed_candidate_route_drift");
  }
  if (currentCandidate.candidateHash !== candidate.candidateHash) {
    fail("installed_candidate_drift");
  }
}

async function runFullBankAcceptance({
  driver,
  readbackDriver,
  args,
  privateRoot = WORKBENCH_PRIVATE_ROOT,
  now = Date.now,
  randomBytes = crypto.randomBytes,
}) {
  if (
    !args?.authorizationConfirmed ||
    args.live !== true ||
    !driver ||
    !readbackDriver
  ) {
    fail("explicit_local_full_bank_authorization_required");
  }
  strictLoopbackOrigin(args.origin);
  const startedAtMs = now();
  const auth = await driver.api("/api/auth/status");
  if (
    auth?.authenticated !== true ||
    auth.admin !== true ||
    auth.method !== "local_loopback_admin"
  ) {
    fail("loopback_administrator_unavailable");
  }
  const [build, bank, mainContext] = await Promise.all([
    driver.api("/api/build-version"),
    driver.api("/api/evals"),
    driver.api("/api/prompts/main.identity/workbench-context"),
  ]);
  const buildIdentity = validateBuild(build);
  const catalog = validateEvalBank(bank);
  const mainAgentId = validateMainOwner(mainContext);
  const configuredRoutes = {};
  for (const family of catalog.families) {
    configuredRoutes[family.id] = await driver.api(
      `/api/evals/execution-route?family=${encodeURIComponent(family.id)}`,
    );
  }
  const plans = await buildFamilyPlans({
    catalog,
    configuredRoutes,
    mainAgentId,
  });
  const candidate = candidateIdentity(catalog, buildIdentity, plans);
  const reportId = randomBytes(16).toString("hex");
  if (!/^[0-9a-f]{32}$/.test(reportId)) fail("report_identity_invalid");
  const paths = reportPaths(
    args.evidenceRoot,
    reportId,
    candidate.candidateHash,
  );
  const privateAggregate = {
    schemaVersion: 1,
    runner: RUNNER_ID,
    status: "running",
    releaseEligible: false,
    candidateMode: "PRE-GATE / NOT READY",
    originHash: sha(args.origin, 64),
    startedAtMs,
    candidate,
    catalog: {
      familyIds: catalog.familyIds,
      caseIds: catalog.caseIds,
    },
    runs: [],
    persistedRunCount: 0,
  };
  writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
  try {
    for (const plan of plans) {
      const body = {
        maxCases: plan.caseIds.length,
        live: true,
        family: plan.familyId,
        surface: plan.surface,
        caseIds: [...plan.caseIds],
      };
      const run = await driver.api("/api/evals/run", {
        method: "POST",
        body,
        timeoutMs: args.timeoutMs,
      });
      if (RUN_ID_PATTERN.test(String(run?.id || ""))) {
        privateAggregate.runs.push({
          runId: run.id,
          familyId: plan.familyId,
          familyHash: sha(plan.familyId, 64),
          caseIds: [...plan.caseIds],
          caseIdsHash: plan.caseIdsHash,
          caseCount: plan.caseIds.length,
          resultCount: 0,
          routeKind: plan.runner,
          surface: plan.surface,
          surfaceHash: sha(plan.surface, 64),
          canonicalArtifactName: plan.canonicalArtifactName,
          canonicalArtifactSha256: String(
            run?.executionRoute?.artifactSha256 || "",
          ),
          runEvidenceHash: jsonHash({ runId: run.id, status: "unverified" }),
        });
        writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
      }
      const validated = validateRun({
        run,
        plan,
        candidate,
        privateRoot,
        startedAtMs,
        nowMs: now(),
      });
      privateAggregate.runs[privateAggregate.runs.length - 1] = validated;
      writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
    }
    privateAggregate.coverage = validateAggregateCoverage(
      catalog,
      plans,
      privateAggregate.runs,
    );
    writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
    await verifyReadback({
      readbackDriver,
      trackedRuns: privateAggregate.runs,
      catalog,
      buildIdentity,
      plans,
      candidate,
    });
    privateAggregate.persistedRunCount = privateAggregate.runs.length;
    privateAggregate.status = "pass";
    privateAggregate.completedAtMs = now();
    writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
    const privateBytes = secureReadFile(
      args.evidenceRoot,
      paths.privateAggregatePath,
      "private_aggregate_unavailable",
      MAX_PRIVATE_ARTIFACT_BYTES,
    );
    const publicSummary = makePublicSummary(
      privateAggregate,
      sha(privateBytes, 64),
    );
    writeJsonAtomic(paths.publicSummaryPath, publicSummary);
    return {
      status: "pass",
      privateAggregatePath: paths.privateAggregatePath,
      publicSummaryPath: paths.publicSummaryPath,
      publicSummary,
    };
  } catch (error) {
    privateAggregate.status = "blocked";
    privateAggregate.blocker = safeError(error?.message);
    privateAggregate.completedAtMs = now();
    try {
      writeJsonAtomic(paths.privateAggregatePath, privateAggregate);
      const privateBytes = secureReadFile(
        args.evidenceRoot,
        paths.privateAggregatePath,
        "private_aggregate_unavailable",
        MAX_PRIVATE_ARTIFACT_BYTES,
      );
      writeJsonAtomic(
        paths.publicSummaryPath,
        makePublicSummary(privateAggregate, sha(privateBytes, 64)),
      );
    } catch {
      // Preserve the original blocker.
    }
    error.privateAggregatePath = paths.privateAggregatePath;
    error.publicSummaryPath = paths.publicSummaryPath;
    throw error;
  }
}

function readJsonSecure(root, candidate, code, maxBytes) {
  const bytes = secureReadFile(root, candidate, code, maxBytes);
  try {
    const value = JSON.parse(bytes.toString("utf8"));
    if (!value || typeof value !== "object" || Array.isArray(value)) fail(code);
    return value;
  } catch (error) {
    if (error?.message === code) throw error;
    fail(code);
  }
}

function inspectCleanupTree(runDir) {
  const entries = fs.readdirSync(runDir, { withFileTypes: true });
  if (entries.length < 2 || entries.length > MAX_CLEANUP_FILES) {
    fail("owned_cleanup_scope_invalid");
  }
  let bytes = 0;
  for (const entry of entries) {
    if (!entry.isFile() || entry.isSymbolicLink()) {
      fail("owned_cleanup_scope_invalid");
    }
    const target = path.join(runDir, entry.name);
    const stat = fs.lstatSync(target);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) {
      fail("owned_cleanup_scope_invalid");
    }
    bytes += stat.size;
    if (bytes > MAX_CLEANUP_BYTES) fail("owned_cleanup_scope_invalid");
  }
}

function cleanupOwnedArtifacts({ manifestPath, evidenceRoot, privateRoot }) {
  const safeManifest = containedPath(
    evidenceRoot,
    manifestPath,
    "owned_cleanup_scope_invalid",
  );
  const aggregate = readJsonSecure(
    evidenceRoot,
    safeManifest,
    "owned_cleanup_scope_invalid",
    8 * 1024 * 1024,
  );
  if (
    aggregate.schemaVersion !== 1 ||
    aggregate.runner !== RUNNER_ID ||
    !HASH_16_PATTERN.test(String(aggregate.candidate?.sourceHash || "")) ||
    !HASH_64_PATTERN.test(String(aggregate.candidate?.candidateHash || "")) ||
    !Array.isArray(aggregate.runs) ||
    aggregate.runs.length === 0
  ) {
    fail("owned_cleanup_scope_invalid");
  }
  const validated = [];
  const seen = new Set();
  for (const item of aggregate.runs) {
    const runId = String(item?.runId || "");
    const familyId = String(item?.familyId || "");
    const artifactName = String(item?.canonicalArtifactName || "");
    if (
      !RUN_ID_PATTERN.test(runId) ||
      seen.has(runId) ||
      !ID_PATTERN.test(familyId) ||
      !HASH_64_PATTERN.test(String(item?.caseIdsHash || "")) ||
      !CANONICAL_ARTIFACT_NAMES.has(artifactName) ||
      !HASH_64_PATTERN.test(String(item?.canonicalArtifactSha256 || ""))
    ) {
      fail("owned_cleanup_scope_invalid");
    }
    seen.add(runId);
    const runDir = containedPath(
      path.join(privateRoot, "eval-runs"),
      path.join(privateRoot, "eval-runs", runId),
      "owned_cleanup_scope_invalid",
    );
    assertNoSymlinkPath(privateRoot, runDir, "owned_cleanup_scope_invalid");
    const runRecord = readJsonSecure(
      privateRoot,
      path.join(runDir, "workbench-run.json"),
      "owned_cleanup_scope_invalid",
      16 * 1024 * 1024,
    );
    if (
      runRecord.id !== runId ||
      runRecord.family !== familyId ||
      runRecord.candidateSourceHash !== aggregate.candidate.sourceHash ||
      !Array.isArray(runRecord.selectedCaseIds) ||
      jsonHash(runRecord.selectedCaseIds) !== item.caseIdsHash ||
      (Array.isArray(item.caseIds) &&
        stableStringify(item.caseIds) !==
          stableStringify(runRecord.selectedCaseIds))
    ) {
      fail("owned_cleanup_scope_invalid");
    }
    const artifactBytes = secureReadFile(
      privateRoot,
      path.join(runDir, artifactName),
      "owned_cleanup_scope_invalid",
      MAX_PRIVATE_ARTIFACT_BYTES,
    );
    if (sha(artifactBytes, 64) !== item.canonicalArtifactSha256) {
      fail("owned_cleanup_scope_invalid");
    }
    inspectCleanupTree(runDir);
    validated.push(runDir);
  }
  for (const runDir of validated) {
    fs.rmSync(runDir, { recursive: true, force: false });
  }
  return {
    schemaVersion: 1,
    qaCase: RUNNER_ID,
    status: "cleaned",
    releaseEligible: false,
    candidateMode: "PRE-GATE / NOT READY",
    removedCount: validated.length,
    removedSetHash: jsonHash([...seen].sort()),
  };
}

class HttpWorkbenchDriver {
  constructor({ origin, timeoutMs }) {
    this.origin = strictLoopbackOrigin(origin);
    this.timeoutMs = timeoutMs;
  }

  async api(apiPath, { method = "GET", body, timeoutMs } = {}) {
    if (!apiPath.startsWith("/api/") || apiPath.startsWith("//")) {
      fail("workbench_api_path_invalid");
    }
    const target = new URL(apiPath, this.origin);
    if (target.origin !== this.origin) fail("workbench_api_path_invalid");
    const payload = body === undefined ? null : JSON.stringify(body);
    const hostname = target.hostname.replace(/^\[|\]$/g, "");
    return new Promise((resolve, reject) => {
      const request = http.request(
        {
          protocol: target.protocol,
          hostname,
          port: target.port,
          path: `${target.pathname}${target.search}`,
          method,
          agent: false,
          headers: {
            Accept: "application/json",
            "Cache-Control": "no-store",
            ...(payload
              ? {
                  "Content-Type": "application/json",
                  "Content-Length": Buffer.byteLength(payload),
                }
              : {}),
          },
        },
        (response) => {
          const chunks = [];
          let size = 0;
          response.on("data", (chunk) => {
            size += chunk.length;
            if (size > MAX_API_BYTES) {
              request.destroy(new Error("workbench_api_response_too_large"));
              return;
            }
            chunks.push(chunk);
          });
          response.on("end", () => {
            if (
              !Number.isInteger(response.statusCode) ||
              response.statusCode < 200 ||
              response.statusCode >= 300
            ) {
              reject(
                new Error(
                  `workbench_api_request_failed_${response.statusCode || 0}`,
                ),
              );
              return;
            }
            let value;
            try {
              value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
            } catch {
              reject(new Error("workbench_api_response_invalid"));
              return;
            }
            if (!value || typeof value !== "object" || Array.isArray(value)) {
              reject(new Error("workbench_api_response_invalid"));
              return;
            }
            resolve(value);
          });
        },
      );
      request.setTimeout(timeoutMs || this.timeoutMs || 30_000, () => {
        request.destroy(new Error("workbench_api_request_timeout"));
      });
      request.on("error", reject);
      if (payload) request.write(payload);
      request.end();
    });
  }
}

async function main() {
  let args;
  try {
    args = parseArgs();
    if (args.mode === "cleanup") {
      const result = cleanupOwnedArtifacts({
        manifestPath: args.manifestPath,
        evidenceRoot: args.evidenceRoot,
        privateRoot: WORKBENCH_PRIVATE_ROOT,
      });
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    const driver = new HttpWorkbenchDriver(args);
    const readbackDriver = new HttpWorkbenchDriver(args);
    const result = await runFullBankAcceptance({
      driver,
      readbackDriver,
      args,
    });
    console.log(JSON.stringify(result.publicSummary, null, 2));
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          schemaVersion: 1,
          qaCase: RUNNER_ID,
          status: "blocked",
          releaseEligible: false,
          candidateMode: "PRE-GATE / NOT READY",
          blockerHash: sha(safeError(error?.message), 64),
        },
        null,
        2,
      ),
    );
    process.exitCode = 1;
  }
}

module.exports = {
  AUTHORIZATION_ENV,
  RUNNER_ID,
  HttpWorkbenchDriver,
  buildFamilyPlans,
  cleanupOwnedArtifacts,
  makePublicSummary,
  parseArgs,
  runFullBankAcceptance,
  sha,
  stableStringify,
  strictLoopbackOrigin,
  validateActivationArtifact,
  validateEvalBank,
  validatePlanCoverage,
  validateRun,
};

if (require.main === module) {
  main();
}
