#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const APP_SUPPORT_ROOT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
);
const WORKBENCH_STATE_PATH = path.join(
  APP_SUPPORT_ROOT,
  "state",
  "prompt-workbench",
  "state.json",
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
  "prompt-workbench-installed-journey",
);

const AUTHORIZATION_ENV = "VIVENTIUM_QA_ALLOW_PROMPT_WORKBENCH_INSTALLED";
const DRAFT_REASON_PREFIX = "PW-INSTALLED-JOURNEY:";
const DEFAULT_ORIGIN = "http://127.0.0.1:8781";
const DEFAULT_FAMILY_ID = "feelings_embodiment_and_reaction";
const DEFAULT_CASE_ID = "feelings_direct_question_without_state_recap";
const CONTINUITY_PROMPT_ID = "scheduler.consciousness_continuity_opportunity";
const REQUIRED_PROMPT_IDS = Object.freeze([
  "main.conscious_agent",
  "main.identity",
  "main.scheduling_self_continuity",
  CONTINUITY_PROMPT_ID,
]);
const SAFE_RUN_STATUSES = new Set([
  "partial_semantic_passed",
  "completed_full_semantic_passed",
]);

function fail(code) {
  throw new Error(code);
}

function sha(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value))
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

function safeError(value) {
  return String(value || "prompt_workbench_installed_journey_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(
      /(?:authorization|bearer|token|secret|password)[=: ]+[^\s,}]+/gi,
      "$1=<redacted>",
    )
    .replace(/\s+/g, " ")
    .slice(0, 320);
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

function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const flags = new Set(argv.filter((item) => !item.includes("=")));
  const values = new Map(
    argv
      .filter((item) => item.startsWith("--") && item.includes("="))
      .map((item) => {
        const separator = item.indexOf("=");
        return [item.slice(0, separator), item.slice(separator + 1)];
      }),
  );
  if (
    !flags.has("--local-qa") ||
    !flags.has("--allow-live-eval") ||
    !flags.has("--allow-synthetic-artifacts")
  ) {
    fail("explicit_local_qa_authorization_required");
  }
  if (env[AUTHORIZATION_ENV] !== "1") {
    fail(`${AUTHORIZATION_ENV}_required`);
  }
  if (env.CI || env.NODE_ENV === "production") {
    fail("installed_local_qa_forbidden_in_ci_or_production");
  }
  const familyId = values.get("--family") || DEFAULT_FAMILY_ID;
  const caseId = values.get("--case") || DEFAULT_CASE_ID;
  if (
    !/^[A-Za-z0-9_.:-]{1,160}$/.test(familyId) ||
    !/^[A-Za-z0-9_.:-]{1,160}$/.test(caseId)
  ) {
    fail("invalid_eval_selection");
  }
  const rawTimeout = Number.parseInt(
    values.get("--timeout-ms") || "480000",
    10,
  );
  if (
    !Number.isInteger(rawTimeout) ||
    rawTimeout < 30_000 ||
    rawTimeout > 900_000
  ) {
    fail("invalid_eval_timeout");
  }
  const evidenceRoot = path.resolve(
    values.get("--evidence-root") || DEFAULT_EVIDENCE_ROOT,
  );
  const allowedEvidenceRoot = path.resolve(DEFAULT_EVIDENCE_ROOT);
  if (
    evidenceRoot !== allowedEvidenceRoot &&
    !evidenceRoot.startsWith(`${allowedEvidenceRoot}${path.sep}`)
  ) {
    fail("private_evidence_root_required");
  }
  return {
    origin: strictLoopbackOrigin(values.get("--origin") || DEFAULT_ORIGIN),
    familyId,
    caseId,
    timeoutMs: rawTimeout,
    headed: flags.has("--headed"),
    evidenceRoot,
  };
}

function assertFreshBuild(build) {
  const backend = build?.backend;
  const frontend = build?.frontend;
  if (
    build?.available !== true ||
    !Array.isArray(build.entryAssets) ||
    build.entryAssets.length === 0
  ) {
    fail("installed_frontend_build_unavailable");
  }
  if (
    !backend ||
    backend.sourceCurrent !== true ||
    !/^[0-9a-f]{16}$/.test(String(backend.loadedSourceHash || "")) ||
    backend.loadedSourceHash !== backend.currentSourceHash
  ) {
    fail("installed_backend_source_stale");
  }
  const frontendHashes = [
    frontend?.receiptFrontendInputHash,
    frontend?.currentFrontendInputHash,
    frontend?.receiptBuiltAssetHash,
    frontend?.currentBuiltAssetHash,
  ];
  if (
    frontend?.receiptAvailable !== true ||
    frontend?.schemaVersion !== 1 ||
    frontend?.sourceCurrent !== true ||
    frontend?.assetsCurrent !== true ||
    frontend?.receiptValid !== true ||
    !frontendHashes.every((value) =>
      /^[0-9a-f]{64}$/.test(String(value || "")),
    ) ||
    frontend.receiptFrontendInputHash !== frontend.currentFrontendInputHash ||
    frontend.receiptBuiltAssetHash !== frontend.currentBuiltAssetHash ||
    !Number.isInteger(frontend.receiptBuiltFileCount) ||
    frontend.receiptBuiltFileCount <= 0 ||
    frontend.receiptBuiltFileCount !== frontend.currentBuiltFileCount
  ) {
    fail("installed_frontend_build_receipt_invalid");
  }
  return backend.loadedSourceHash;
}

function validateFramesHealth(payload) {
  if (!Array.isArray(payload?.frames) || !payload?.health) {
    fail("frames_health_unverified");
  }
  const health = payload.health;
  if (health.status === "degraded") fail("frames_health_degraded");
  if (health.status === "unavailable") fail("frames_health_unavailable");
  if (
    !["ok", "empty"].includes(health.status) ||
    !String(health.source || "").trim() ||
    typeof health.reason !== "string" ||
    health.releaseEvidence !== false ||
    !["filesScanned", "invalidEventCount", "truncatedReadCount"].every(
      (field) => Number.isInteger(health[field]) && health[field] >= 0,
    )
  ) {
    fail("frames_health_unverified");
  }
  return payload.frames.length;
}

function validatePromptLineage(fixtures, promptId) {
  const { registry, detail, context, rendered } = fixtures || {};
  const prompts = registry?.prompts;
  const row = Array.isArray(prompts)
    ? prompts.find((item) => item?.id === promptId)
    : null;
  const nodes = registry?.flow?.nodes;
  const includes = Array.isArray(detail?.includes) ? detail.includes : [];
  const promptIds = new Set(
    Array.isArray(prompts) ? prompts.map((item) => item?.id) : [],
  );
  const nodeIds = new Set(
    Array.isArray(nodes) ? nodes.map((node) => node?.id) : [],
  );
  const includeOnlyComposite =
    !String(detail?.body || "").trim() &&
    Number.isInteger(row?.includeCount) &&
    row.includeCount > 0 &&
    includes.length === row.includeCount &&
    includes.every(
      (includeId) => promptIds.has(includeId) && nodeIds.has(includeId),
    );
  if (
    !row ||
    !Array.isArray(nodes) ||
    !nodes.some((node) => node?.id === promptId) ||
    detail?.id !== promptId ||
    context?.promptId !== promptId ||
    rendered?.id !== promptId ||
    !String(detail.text || "").trim() ||
    (!String(detail.body || "").trim() && !includeOnlyComposite) ||
    !String(rendered.rendered || "").trim() ||
    detail.rendered !== rendered.rendered ||
    row.contentHash !== detail.contentHash ||
    row.bodyHash !== detail.bodyHash ||
    context.contentHash !== detail.contentHash ||
    context.bodyHash !== detail.bodyHash ||
    rendered.renderedHash !== sha(rendered.rendered)
  ) {
    fail("prompt_source_rendered_live_lineage_mismatch");
  }
  const delivery = context.delivery;
  if (!delivery || delivery.state !== "synced") {
    fail("prompt_source_rendered_live_lineage_mismatch");
  }
  if (delivery.kind === "managed_agent") {
    if (
      !context.sync ||
      context.sync.state !== "synced" ||
      !context.sync.sourceHash ||
      context.sync.sourceHash !== context.sync.liveHash
    ) {
      fail("prompt_source_rendered_live_lineage_mismatch");
    }
  } else if (delivery.kind === "compiled_runtime") {
    if (
      !context.runtimePromptBundle ||
      context.runtimePromptBundle.status !== "ok" ||
      context.runtimePromptBundle.promptState !== "synced" ||
      context.runtimePromptBundle.liveBundleAvailable !== true
    ) {
      fail("prompt_source_rendered_live_lineage_mismatch");
    }
  } else {
    fail("prompt_source_rendered_live_lineage_mismatch");
  }
  return true;
}

function selectExactModelCase(bank, { familyId, caseId }) {
  const families = bank?.families;
  const family = Array.isArray(families)
    ? families.find((item) => item?.id === familyId)
    : null;
  const selectedCase = family?.cases?.find((item) => item?.id === caseId);
  if (!family || !selectedCase) fail("exact_eval_case_unavailable");
  if (family.runner) fail("bounded_main_exact_model_case_required");
  if (selectedCase.surface !== "web")
    fail("trusted_native_surface_runner_required");
  if (selectedCase.comparisonCaseId)
    fail("bounded_unpaired_eval_case_required");
  if (family.semanticJudge !== true && selectedCase.semanticJudge !== true) {
    fail("semantic_judge_required");
  }
  if (!family.promptRefs?.includes("main.conscious_agent")) {
    fail("main_prompt_lineage_required");
  }
  if (!selectedCase.fixture?.feelings) {
    fail("restorable_synthetic_fixture_required");
  }
  return { family, case: selectedCase };
}

function validateContinuitySchedule(schedules) {
  const matches = (Array.isArray(schedules) ? schedules : []).filter(
    (row) =>
      row?.sourcePromptId === CONTINUITY_PROMPT_ID && row.active === true,
  );
  if (matches.length !== 1) fail("continuity_schedule_visibility_invalid");
  const row = matches[0];
  if (
    !/^[A-Za-z0-9_.:-]{1,160}$/.test(String(row.id || "")) ||
    !String(row.userId || "").trim() ||
    !String(row.title || "").trim() ||
    !row.schedule ||
    typeof row.schedule !== "object" ||
    Array.isArray(row.schedule) ||
    row.executor !== "viventium_agent" ||
    row.effectivePromptId !== CONTINUITY_PROMPT_ID ||
    row.runEnvelopePromptId !== "scheduler.run_envelope" ||
    row.canonicalOutputPromptId !== "scheduler.canonical_output" ||
    row.standingCapabilityPromptId !== "main.scheduling_self_continuity"
  ) {
    fail("continuity_schedule_visibility_invalid");
  }
  return row;
}

function scheduleConfigFingerprint(schedule) {
  const fields = [
    "id",
    "userId",
    "title",
    "sourcePromptId",
    "effectivePromptId",
    "runEnvelopePromptId",
    "canonicalOutputPromptId",
    "standingCapabilityPromptId",
    "templateId",
    "promptText",
    "schedule",
    "timezone",
    "active",
    "channel",
    "executor",
    "conversationPolicy",
    "memoryWriteMode",
  ];
  return sha(
    stableStringify(
      Object.fromEntries(
        fields.map((field) => [field, schedule?.[field] ?? null]),
      ),
    ),
  );
}

function validateEvalLineage(lineage, { familyId, caseId }) {
  if (
    !lineage ||
    lineage.schemaVersion !== 1 ||
    stableStringify(lineage.familyIds) !== stableStringify([familyId]) ||
    stableStringify(lineage.caseIds) !== stableStringify([caseId]) ||
    !Array.isArray(lineage.rootPromptIds) ||
    !lineage.rootPromptIds.includes("main.conscious_agent") ||
    !Array.isArray(lineage.promptDependencies) ||
    lineage.promptDependencies.length < 1 ||
    lineage.promptCount !== lineage.promptDependencies.length ||
    !Array.isArray(lineage.runtimeContextDependencies) ||
    lineage.runtimeContextCount !== lineage.runtimeContextDependencies.length ||
    lineage.promptDependencies.some(
      (row) =>
        !row ||
        row.kind !== "prompt" ||
        row.status !== "available" ||
        !/^[0-9a-f]{16}$/.test(String(row.contentHash || "")) ||
        !/^[0-9a-f]{16}$/.test(String(row.bodyHash || "")) ||
        !/^[0-9a-f]{16}$/.test(String(row.renderedHash || "")),
    ) ||
    lineage.runtimeContextDependencies.some(
      (row) => !row || row.status === "unknown_contract",
    )
  ) {
    fail("exact_model_lineage_mismatch");
  }
  const unsigned = { ...lineage };
  delete unsigned.manifestHash;
  if (lineage.manifestHash !== sha(stableStringify(unsigned))) {
    fail("exact_model_lineage_mismatch");
  }
}

function validateEvalRun(
  run,
  {
    familyId,
    caseId,
    surface,
    promptId,
    configuredRoute,
    expectedAgentHash,
    candidateSourceHash,
  },
) {
  if (run?.candidateSourceHash !== candidateSourceHash)
    fail("stale_eval_candidate");
  if (run?.surface !== surface) fail("exact_model_surface_mismatch");
  if (
    !/^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$/.test(String(run?.id || "")) ||
    run.artifactName !== run.id ||
    run.live !== true ||
    run.returnCode !== 0 ||
    run.family !== familyId ||
    run.promptId !== promptId ||
    stableStringify(run.selectedCaseIds) !== stableStringify([caseId]) ||
    run.selectedCaseCount !== 1 ||
    run.resultCount !== 1 ||
    run.semanticJudgeRequired !== true
  ) {
    fail("exact_model_result_invalid");
  }
  const summary = run.runnerSummary;
  if (
    !summary ||
    !SAFE_RUN_STATUSES.has(summary.status) ||
    summary.selectedCaseCount !== 1 ||
    summary.resultCount !== 1 ||
    summary.completedCount !== 1 ||
    summary.failedCount !== 0 ||
    summary.semanticJudgedCount !== 1 ||
    summary.semanticPassedCount !== 1 ||
    summary.semanticFailedCount !== 0 ||
    summary.semanticJudgeUnavailableCount !== 0 ||
    summary.duplicateResponseQualityFailureCount !== 0 ||
    summary.unresolvedAsyncQualityFailureCount !== 0
  ) {
    fail("exact_model_semantic_result_invalid");
  }
  validateEvalLineage(run.lineageManifest, { familyId, caseId });
  const route = run.executionRoute;
  const providerHash = sha(configuredRoute?.provider || "");
  const modelHash = sha(configuredRoute?.model || "");
  if (
    configuredRoute?.kind !== "main" ||
    configuredRoute.family !== familyId ||
    !configuredRoute.provider ||
    !configuredRoute.model ||
    route?.status !== "verified" ||
    route.configuredProvider !== configuredRoute.provider ||
    route.configuredModel !== configuredRoute.model ||
    route.configuredProviderHash !== providerHash ||
    route.configuredModelHash !== modelHash ||
    route.observedProviderHash !== providerHash ||
    route.observedModelHash !== modelHash ||
    route.completedCaseCount !== 1 ||
    !/^[0-9a-f]{64}$/.test(String(route.artifactSha256 || ""))
  ) {
    fail("exact_model_route_mismatch");
  }
  const evidence = route.caseEvidence;
  if (
    !Array.isArray(evidence) ||
    evidence.length !== 1 ||
    evidence[0].caseId !== caseId ||
    evidence[0].agentIdHash !== expectedAgentHash
  ) {
    fail("exact_model_agent_mismatch");
  }
  if (
    !/^[0-9a-f]{16}$/.test(String(evidence[0].requestIdentityHash || "")) ||
    evidence[0].semanticJudged !== true ||
    evidence[0].semanticPassed !== true
  ) {
    fail("exact_model_case_evidence_invalid");
  }
  return run;
}

function parsePromptFrames(value) {
  if (value && typeof value === "object") return value;
  if (typeof value !== "string") return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function validatePrivateExactModelArtifact(
  payload,
  {
    familyId,
    caseId,
    surface,
    expectedAgentHash,
    configuredProviderHash,
    configuredModelHash,
    adminEmailHash,
  },
) {
  const summary = payload?.summary;
  const args = payload?.args;
  const login = summary?.login;
  const rows = payload?.liveResults;
  if (
    !summary ||
    !args ||
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    args.agentIdHash !== expectedAgentHash ||
    summary.agentIdHash !== expectedAgentHash ||
    summary.observedAgentIdHash !== expectedAgentHash ||
    args.family !== familyId ||
    stableStringify(args.caseIds) !== stableStringify([caseId]) ||
    args.surface !== surface ||
    args.promptId !== "main.conscious_agent" ||
    args.localJwtFallback !== true ||
    args.semanticJudge !== true ||
    summary.selectedCaseCount !== 1 ||
    summary.resultCount !== 1 ||
    summary.completedCount !== 1 ||
    summary.failedCount !== 0 ||
    summary.semanticJudgedCount !== 1 ||
    summary.semanticPassedCount !== 1 ||
    summary.semanticFailedCount !== 0 ||
    summary.semanticJudgeUnavailableCount !== 0
  ) {
    fail("private_exact_model_evidence_invalid");
  }
  if (
    login?.authMode !== "local_jwt_fallback" ||
    !/^[0-9a-f]{16}$/.test(String(login.userEmailHash || ""))
  ) {
    fail("synthetic_eval_identity_unverified");
  }
  if (login.userEmailHash === adminEmailHash)
    fail("personal_owner_eval_forbidden");
  const row = rows[0];
  if (
    row.caseId !== caseId ||
    row.familyId !== familyId ||
    row.surface !== surface ||
    row.observedSurface !== surface ||
    row.status !== "completed" ||
    row.observedAgentIdHash !== expectedAgentHash ||
    !/^[0-9a-f]{16}$/.test(String(row.requestIdentityHash || "")) ||
    row.observedRequestIdentityHash !== row.requestIdentityHash ||
    row.semanticJudge?.status !== "judged" ||
    row.semanticJudge.pass !== true ||
    !Number.isInteger(row.semanticJudge.attemptCount) ||
    row.semanticJudge.attemptCount < 1 ||
    !/^[0-9a-f]{16}$/.test(String(row.semanticJudge.rawHash || ""))
  ) {
    fail("private_exact_model_case_invalid");
  }
  if (
    row.qaCleanup?.status !== "complete" ||
    !Number.isInteger(row.qaCleanup.conversationCount) ||
    row.qaCleanup.conversationCount < 1 ||
    !Number.isInteger(row.qaCleanup.messageCount) ||
    row.qaCleanup.messageCount < 1 ||
    row.fixtureRestoration?.status !== "restored_exact"
  ) {
    fail("synthetic_eval_cleanup_unverified");
  }
  const framePayload = parsePromptFrames(row.promptFrameEvidenceForJudge);
  const frames = framePayload?.prompt_frames;
  const matching = Array.isArray(frames)
    ? frames.filter(
        (frame) =>
          ["main_run_create", "main_runtime"].includes(frame?.prompt_family) &&
          frame.request_identity_hash === row.requestIdentityHash,
      )
    : [];
  if (
    matching.length < 1 ||
    matching.some(
      (frame) =>
        frame.surface !== surface ||
        String(frame.provider_hash || "").replace(/^h/, "") !==
          configuredProviderHash ||
        String(frame.model_hash || "").replace(/^h/, "") !==
          configuredModelHash ||
        String(frame.agent_id_hash || "").replace(/^h/, "") !==
          expectedAgentHash,
    )
  ) {
    fail("private_exact_model_route_mismatch");
  }
  return true;
}

function ensureContainedPath(root, candidate) {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = path.resolve(candidate);
  if (!resolvedCandidate.startsWith(`${resolvedRoot}${path.sep}`)) {
    fail("owned_artifact_path_invalid");
  }
  return resolvedCandidate;
}

function assertNoLinks(candidate) {
  const stat = fs.lstatSync(candidate);
  if (stat.isSymbolicLink()) fail("owned_eval_cleanup_refused");
  if (!stat.isDirectory()) return;
  for (const entry of fs.readdirSync(candidate)) {
    assertNoLinks(path.join(candidate, entry));
  }
}

function removeOwnedDraftArtifact({ privateRoot, draftId, nonce }) {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      String(draftId || ""),
    )
  ) {
    fail("owned_draft_cleanup_refused");
  }
  const draftPath = ensureContainedPath(
    privateRoot,
    path.join(privateRoot, "drafts", `${draftId}.json`),
  );
  try {
    const stat = fs.lstatSync(draftPath);
    const payload = JSON.parse(fs.readFileSync(draftPath, "utf8"));
    if (
      !stat.isFile() ||
      stat.isSymbolicLink() ||
      payload.id !== draftId ||
      payload.kind !== "eval-edit" ||
      payload.status !== "discarded" ||
      payload.reason !== `${DRAFT_REASON_PREFIX}${nonce}`
    ) {
      fail("owned_draft_cleanup_refused");
    }
    fs.unlinkSync(draftPath);
  } catch (error) {
    if (error?.message === "owned_draft_cleanup_refused") throw error;
    fail("owned_draft_cleanup_refused");
  }
}

function removeOwnedEvalArtifact({
  privateRoot,
  runId,
  familyId,
  caseId,
  startedAtMs,
  nowMs = Date.now(),
}) {
  if (!/^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$/.test(String(runId || ""))) {
    fail("owned_eval_cleanup_refused");
  }
  const runDir = ensureContainedPath(
    privateRoot,
    path.join(privateRoot, "eval-runs", runId),
  );
  try {
    assertNoLinks(runDir);
    const record = JSON.parse(
      fs.readFileSync(path.join(runDir, "workbench-run.json"), "utf8"),
    );
    const createdAtMs = Date.parse(String(record.createdAt || ""));
    if (
      record.id !== runId ||
      record.family !== familyId ||
      stableStringify(record.selectedCaseIds) !== stableStringify([caseId]) ||
      record.live !== true ||
      !Number.isFinite(createdAtMs) ||
      createdAtMs < startedAtMs - 5_000 ||
      createdAtMs > nowMs + 5_000
    ) {
      fail("owned_eval_cleanup_refused");
    }
    fs.rmSync(runDir, { recursive: true, force: false });
  } catch (error) {
    if (error?.message === "owned_eval_cleanup_refused") throw error;
    fail("owned_eval_cleanup_refused");
  }
}

function historySignature(rows, idField) {
  return stableStringify(
    [...(Array.isArray(rows) ? rows : [])].sort((left, right) =>
      String(left?.[idField] ?? "").localeCompare(
        String(right?.[idField] ?? ""),
      ),
    ),
  );
}

function assertHistoryRestored(before, after, idField) {
  if (historySignature(before, idField) !== historySignature(after, idField)) {
    fail("history_cleanup_incomplete");
  }
}

function readWorkbenchState(requestedOrigin) {
  let state;
  try {
    state = JSON.parse(fs.readFileSync(WORKBENCH_STATE_PATH, "utf8"));
  } catch {
    fail("workbench_state_unavailable");
  }
  if (Object.hasOwn(state, "authUrl")) fail("retired_bearer_url_present");
  const stateOrigin = strictLoopbackOrigin(state.url);
  if (stateOrigin !== requestedOrigin)
    fail("installed_workbench_origin_mismatch");
  return stateOrigin;
}

function isExpectedSyntheticSaveConsoleError(message) {
  return (
    String(message || "") ===
    "Failed to load resource: the server responded with a status of 503 (Service Unavailable)"
  );
}

async function selectPromptFromAtlas(page, label) {
  const search = page.getByPlaceholder("Search prompt flow...", {
    exact: true,
  });
  await search.fill(label);
  try {
    const item = page
      .locator(".atlas-pane")
      .getByText(label, { exact: true })
      .first();
    await item.waitFor({ state: "visible" });
    await item.click();
  } finally {
    await search.fill("");
  }
}

class BrowserWorkbenchDriver {
  constructor({ origin, headed, timeoutMs }) {
    this.origin = origin;
    this.headed = headed;
    this.timeoutMs = timeoutMs;
    this.browser = null;
    this.context = null;
    this.page = null;
    this.consoleErrors = [];
    this.failedRequests = [];
    this.httpErrors = [];
    this.credentialRequests = [];
    this.externalRequests = [];
    this.ownerMutationAttempts = [];
    this.failedSaveProbeActive = false;
    this.failedSaveProbeObserved = false;
    this.expectedSyntheticSaveConsoleErrors = 0;
    this.expectedHttpErrors = new Set();
  }

  async open() {
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    this.browser = await chromium.launch({
      channel: "chrome",
      headless: !this.headed,
    });
    this.context = await this.browser.newContext({
      viewport: { width: 1512, height: 1050 },
    });
    await this.context.addInitScript(() => {
      localStorage.setItem(
        "viventium.promptWorkbench.launchToken",
        "synthetic-retired-token",
      );
      sessionStorage.setItem(
        "viventium.promptWorkbench.launchToken",
        "synthetic-retired-token",
      );
    });
    this.page = await this.context.newPage();
    this.page.setDefaultTimeout(30_000);
    await this.page.route("**/api/scheduled-prompts**", async (route) => {
      const request = route.request();
      const requestUrl = new URL(request.url());
      if (request.method() !== "GET") {
        if (
          this.failedSaveProbeActive &&
          request.method() === "PATCH" &&
          /^\/api\/scheduled-prompts\/[^/]+$/.test(requestUrl.pathname)
        ) {
          this.failedSaveProbeObserved = true;
          this.expectedSyntheticSaveConsoleErrors += 1;
          this.expectedHttpErrors.add(`PATCH:${requestUrl.pathname}`);
          await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "synthetic_failed_save_probe" }),
          });
          return;
        }
        this.ownerMutationAttempts.push(
          `${request.method()}:${requestUrl.pathname}`,
        );
        await route.abort("blockedbyclient");
        return;
      }
      if (!requestUrl.searchParams.has("readOnly")) {
        requestUrl.searchParams.set("readOnly", "true");
        await route.continue({ url: requestUrl.toString() });
        return;
      }
      await route.continue();
    });
    this.page.on("request", (request) => {
      const requestUrl = new URL(request.url());
      if (!["http:", "https:"].includes(requestUrl.protocol)) return;
      const headers = request.headers();
      if (!["127.0.0.1", "localhost", "[::1]"].includes(requestUrl.hostname)) {
        this.externalRequests.push(sha(requestUrl.hostname, 12));
      }
      if (
        requestUrl.searchParams.has("workbench_token") ||
        headers.authorization ||
        headers["x-viventium-workbench-token"] ||
        String(headers.referer || "").includes("workbench_token=")
      ) {
        this.credentialRequests.push(sha(requestUrl.pathname, 12));
      }
    });
    this.page.on("console", (message) => {
      if (message.type() !== "error") return;
      if (
        this.expectedSyntheticSaveConsoleErrors > 0 &&
        isExpectedSyntheticSaveConsoleError(message.text())
      ) {
        this.expectedSyntheticSaveConsoleErrors -= 1;
        return;
      }
      this.consoleErrors.push(sha(message.text(), 12));
    });
    this.page.on("requestfailed", (request) => {
      if (
        !/ERR_ABORTED|NS_BINDING_ABORTED/i.test(
          request.failure()?.errorText || "",
        )
      ) {
        this.failedRequests.push(sha(new URL(request.url()).pathname, 12));
      }
    });
    this.page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname;
      if (response.status() >= 400 && pathname.startsWith("/api/")) {
        const expectedKey = `${response.request().method()}:${pathname}`;
        if (!this.expectedHttpErrors.delete(expectedKey)) {
          this.httpErrors.push(`${sha(pathname, 12)}:${response.status()}`);
        }
      }
    });
    const response = await this.page.goto(this.origin, {
      waitUntil: "domcontentloaded",
    });
    if (!response || new URL(response.url()).origin !== this.origin) {
      fail("workbench_navigation_redirected");
    }
    await this.page
      .getByText("Viventium Prompt Workbench", { exact: false })
      .first()
      .waitFor();
    await this.page.getByText("Prompt Flow", { exact: true }).waitFor();
  }

  async api(apiPath, { method = "GET", body } = {}) {
    if (!apiPath.startsWith("/api/")) fail("workbench_api_path_invalid");
    const result = await this.page.evaluate(
      async ({ requestPath, requestMethod, requestBody }) => {
        const response = await fetch(requestPath, {
          method: requestMethod,
          cache: "no-store",
          headers:
            requestBody === undefined
              ? undefined
              : { "content-type": "application/json" },
          body:
            requestBody === undefined ? undefined : JSON.stringify(requestBody),
        });
        const text = await response.text();
        let payload = null;
        try {
          payload = text ? JSON.parse(text) : {};
        } catch {
          payload = null;
        }
        return { ok: response.ok, status: response.status, payload };
      },
      { requestPath: apiPath, requestMethod: method, requestBody: body },
    );
    if (!result.ok || !result.payload || typeof result.payload !== "object") {
      fail(`workbench_api_request_failed_${result.status}`);
    }
    return result.payload;
  }

  async assertContinuityUi(schedule, nonce) {
    const atlas = this.page.locator(".atlas-pane");
    const scheduleItem = atlas
      .getByText(schedule.title, { exact: true })
      .first();
    await scheduleItem.waitFor({ state: "visible" });
    await scheduleItem.click();
    await this.page
      .getByText("Scheduled Prompt Object", { exact: true })
      .waitFor();
    await this.page
      .getByText(`Source prompt: ${CONTINUITY_PROMPT_ID}`, { exact: true })
      .waitFor();
    const editor = this.page.locator(".schedule-editor-pane");
    const titleInput = editor.getByLabel("Title", { exact: true });
    if (!(await titleInput.isEditable()))
      fail("continuity_schedule_not_editable");
    const original = await titleInput.inputValue();
    await titleInput.fill(`${original} [${nonce}]`);
    if ((await titleInput.inputValue()) === original)
      fail("continuity_schedule_not_editable");
    if (
      !(await editor
        .getByRole("button", { name: "Save", exact: true })
        .isEnabled())
    ) {
      fail("continuity_schedule_not_editable");
    }
    this.failedSaveProbeActive = true;
    const failedSaveResponse = this.page.waitForResponse((response) => {
      const request = response.request();
      return (
        request.method() === "PATCH" &&
        /^\/api\/scheduled-prompts\/[^/]+$/.test(
          new URL(response.url()).pathname,
        )
      );
    });
    await editor.getByRole("button", { name: "Save", exact: true }).click();
    const failedResponse = await failedSaveResponse;
    this.failedSaveProbeActive = false;
    if (
      !this.failedSaveProbeObserved ||
      failedResponse.status() < 400 ||
      (await titleInput.inputValue()) !== `${original} [${nonce}]`
    ) {
      fail("failed_save_buffer_not_retained");
    }
    await this.page.reload({ waitUntil: "domcontentloaded" });
    this.expectedSyntheticSaveConsoleErrors = 0;
    await this.page.getByText("Prompt Flow", { exact: true }).waitFor();
    const reloadedAtlas = this.page.locator(".atlas-pane");
    const reloadedItem = reloadedAtlas
      .getByText(schedule.title, { exact: true })
      .first();
    await reloadedItem.waitFor({ state: "visible" });
    await reloadedItem.click();
    await this.page
      .getByText(`Source prompt: ${CONTINUITY_PROMPT_ID}`, { exact: true })
      .waitFor();
    const reloadedTitle = await this.page
      .locator(".schedule-editor-pane")
      .getByLabel("Title", { exact: true })
      .inputValue();
    if (reloadedTitle !== original)
      fail("continuity_failed_save_reload_mismatch");
  }

  async assertDeterministicUi() {
    const sidebarButton = this.page.getByRole("button", {
      name: "Hide prompt flow sidebar",
      exact: true,
    });
    await sidebarButton.waitFor({ state: "visible" });
    await this.page.locator("body").press("Control+b");
    const showSidebarButton = this.page.getByRole("button", {
      name: "Show prompt flow sidebar",
      exact: true,
    });
    await showSidebarButton.waitFor({ state: "visible" });
    await this.page.locator("body").press("Control+b");
    await sidebarButton.waitFor({ state: "visible" });

    await this.page.locator('button[title="Workbench settings"]').click();
    const settings = this.page.getByRole("dialog", {
      name: "Workbench settings",
      exact: true,
    });
    await settings.waitFor({ state: "visible" });
    await settings.getByRole("radio", { name: "Light", exact: true }).click();
    if (
      (await this.page.locator(".app-shell").getAttribute("data-theme")) !==
      "light"
    ) {
      fail("light_theme_not_applied");
    }
    await settings.getByRole("radio", { name: "Dark", exact: true }).click();
    if (
      (await this.page.locator(".app-shell").getAttribute("data-theme")) !==
      "dark"
    ) {
      fail("dark_theme_not_applied");
    }
    await this.page.keyboard.press("Escape");
    await settings.waitFor({ state: "hidden" });

    for (const width of [1512, 1024, 320]) {
      await this.page.setViewportSize({
        width,
        height: width === 320 ? 900 : 1050,
      });
      await this.page
        .getByText("Viventium Prompt Workbench", { exact: false })
        .first()
        .waitFor();
      const fitsViewport = await this.page.evaluate(() => {
        const shell = document.querySelector(".app-shell");
        const bounds = shell?.getBoundingClientRect();
        return Boolean(
          bounds &&
          bounds.left >= -1 &&
          bounds.right <= window.innerWidth + 1 &&
          document.documentElement.scrollWidth <= window.innerWidth + 1,
        );
      });
      if (!fitsViewport) fail(`responsive_viewport_overflow_${width}`);
    }
    await this.page.setViewportSize({ width: 1512, height: 1050 });
  }

  async runExactModelEval({ familyId, caseId, timeoutMs }) {
    await selectPromptFromAtlas(this.page, "Main agent instruction");
    const tab = this.page
      .locator(".flexlayout__tab_button")
      .filter({ hasText: /^Evals$/ })
      .first();
    await tab.waitFor({ state: "visible" });
    await tab.click();
    const designer = this.page.locator(".eval-designer");
    await designer.getByText("Run Eval Cases", { exact: true }).waitFor();
    const linkedToggle = designer
      .locator("label")
      .filter({ hasText: "show only cases linked to this prompt" })
      .locator('input[type="checkbox"]');
    if (await linkedToggle.isChecked()) await linkedToggle.click();
    await designer
      .locator("label")
      .filter({ hasText: /^Family/ })
      .locator("select")
      .selectOption(familyId);
    await designer
      .locator("label")
      .filter({ hasText: /^Surface/ })
      .locator("select")
      .selectOption("web");
    const clear = designer.getByRole("button", { name: "Clear", exact: true });
    if (await clear.isVisible().catch(() => false)) await clear.click();
    await designer
      .getByRole("checkbox", { name: `Include ${caseId}`, exact: true })
      .check();
    const liveToggle = designer
      .locator("label")
      .filter({ hasText: "live exact-model run" })
      .locator('input[type="checkbox"]');
    if (!(await liveToggle.isChecked())) await liveToggle.click();
    const responsePromise = this.page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/evals/run" &&
        response.request().method() === "POST",
      { timeout: timeoutMs },
    );
    await designer
      .getByRole("button", { name: "Run live eval", exact: true })
      .click();
    const response = await responsePromise;
    let run;
    try {
      run = await response.json();
    } catch {
      fail("exact_model_response_invalid");
    }
    if (!response.ok()) fail(`exact_model_request_failed_${response.status()}`);
    await this.page.getByText(run.id, { exact: true }).first().waitFor();
    return run;
  }

  async assertEvalHistoryAfterReload(runId) {
    await this.page.reload({ waitUntil: "domcontentloaded" });
    const tab = this.page
      .locator(".flexlayout__tab_button")
      .filter({ hasText: /^Evals$/ })
      .first();
    await tab.waitFor({ state: "visible" });
    await tab.click();
    try {
      await this.page
        .getByText(runId, { exact: true })
        .first()
        .waitFor({ state: "visible", timeout: 30_000 });
    } catch {
      fail("eval_history_reload_mismatch");
    }
  }

  async securityReport() {
    const storage = await this.page.evaluate(() => ({
      localKeys: Object.keys(localStorage),
      sessionKeys: Object.keys(sessionStorage),
      url: window.location.href,
      referrer: document.referrer,
    }));
    let referrerIsTokenFree = true;
    if (storage.referrer) {
      try {
        const referrer = new URL(storage.referrer);
        referrerIsTokenFree =
          referrer.origin === this.origin &&
          !referrer.search &&
          !referrer.hash &&
          !referrer.username &&
          !referrer.password;
      } catch {
        referrerIsTokenFree = false;
      }
    }
    return {
      tokenFreeUrl: !new URL(storage.url).search && !new URL(storage.url).hash,
      noPersistentBearer:
        !storage.localKeys.includes("viventium.promptWorkbench.launchToken") &&
        !storage.sessionKeys.includes("viventium.promptWorkbench.launchToken"),
      noReferrerDisclosure: referrerIsTokenFree,
      credentialRequestCount: this.credentialRequests.length,
      externalRequestCount: this.externalRequests.length,
      ownerMutationAttemptCount: this.ownerMutationAttempts.length,
      consoleErrorCount: this.consoleErrors.length,
      failedRequestCount: this.failedRequests.length,
      httpErrorCount: this.httpErrors.length,
    };
  }

  async close() {
    await this.browser?.close().catch(() => {});
  }
}

function assertSecurityReport(report) {
  if (
    report?.tokenFreeUrl !== true ||
    report.noPersistentBearer !== true ||
    report.noReferrerDisclosure !== true ||
    report.credentialRequestCount !== 0 ||
    report.externalRequestCount !== 0 ||
    report.ownerMutationAttemptCount !== 0 ||
    report.consoleErrorCount !== 0 ||
    report.failedRequestCount !== 0 ||
    report.httpErrorCount !== 0
  ) {
    fail("workbench_browser_security_or_runtime_error");
  }
}

async function fetchPromptLineage(driver, registry, promptId) {
  const encoded = encodeURIComponent(promptId);
  const [detail, context, rendered] = await Promise.all([
    driver.api(`/api/prompts/${encoded}`),
    driver.api(`/api/prompts/${encoded}/workbench-context`),
    driver.api("/api/prompts/render", {
      method: "POST",
      body: { promptId, variables: {} },
    }),
  ]);
  validatePromptLineage({ registry, detail, context, rendered }, promptId);
  return { detail, context, rendered };
}

function readPrivateJson(candidate) {
  try {
    const stat = fs.lstatSync(candidate);
    if (!stat.isFile() || stat.isSymbolicLink())
      fail("private_eval_artifact_invalid");
    return JSON.parse(fs.readFileSync(candidate, "utf8"));
  } catch (error) {
    if (error?.message === "private_eval_artifact_invalid") throw error;
    fail("private_eval_artifact_invalid");
  }
}

async function runInstalledJourney({
  driver,
  args,
  privateRoot = WORKBENCH_PRIVATE_ROOT,
  now = Date.now,
}) {
  const startedAtMs = now();
  const nonce = crypto.randomBytes(8).toString("hex");
  let draftId = null;
  let draftDiscarded = false;
  let draftBaseline = null;
  let runId = null;
  let evalHistoryBaseline = null;
  let cleanupFailure = null;
  let journeyFailure = null;
  let result = null;
  try {
    await driver.open();
    const auth = await driver.api("/api/auth/status");
    if (
      auth.authenticated !== true ||
      auth.admin !== true ||
      auth.method !== "local_loopback_admin" ||
      !String(auth.userId || "").trim() ||
      !String(auth.email || "").trim()
    ) {
      fail("loopback_administrator_unavailable");
    }
    const build = await driver.api("/api/build-version");
    const candidateSourceHash = assertFreshBuild(build);
    const frameCount = validateFramesHealth(await driver.api("/api/frames"));
    const registry = await driver.api("/api/prompts");
    const promptIds = new Set((registry.prompts || []).map((row) => row?.id));
    if (!REQUIRED_PROMPT_IDS.every((promptId) => promptIds.has(promptId))) {
      fail("required_prompt_registry_entries_missing");
    }
    const lineage = {};
    for (const promptId of REQUIRED_PROMPT_IDS) {
      lineage[promptId] = await fetchPromptLineage(driver, registry, promptId);
    }
    const mainSync = lineage["main.identity"].context.sync;
    if (
      !mainSync ||
      !String(mainSync.agentId || "").trim() ||
      mainSync.state !== "synced" ||
      mainSync.sourceHash !== mainSync.liveHash
    ) {
      fail("configured_main_agent_identity_unavailable");
    }
    const expectedAgentHash = sha(mainSync.agentId);
    const evalBank = await driver.api("/api/evals");
    const selected = selectExactModelCase(evalBank, {
      familyId: args.familyId,
      caseId: args.caseId,
    });
    const configuredRoute = await driver.api(
      `/api/evals/execution-route?family=${encodeURIComponent(args.familyId)}`,
    );
    draftBaseline = (await driver.api("/api/drafts")).drafts;
    if (
      !Array.isArray(draftBaseline) ||
      draftBaseline.some((draft) => draft?.status === "draft")
    ) {
      fail("preexisting_active_draft_blocks_installed_journey");
    }
    evalHistoryBaseline = (await driver.api("/api/evals/runs")).runs;
    if (!Array.isArray(evalHistoryBaseline)) fail("eval_history_unavailable");
    const schedulePayload = await driver.api(
      "/api/scheduled-prompts?readOnly=true",
    );
    const schedule = validateContinuitySchedule(
      schedulePayload.scheduledPrompts,
    );
    if (schedule.userId !== auth.userId)
      fail("continuity_schedule_owner_mismatch");
    const scheduleFingerprint = scheduleConfigFingerprint(schedule);
    await driver.assertContinuityUi(schedule, nonce);
    await driver.assertDeterministicUi();
    const draft = await driver.api("/api/evals/case-draft", {
      method: "POST",
      body: {
        familyId: args.familyId,
        caseId: `pw_installed_journey_${nonce}`,
        create: true,
        updatedCase: {
          surface: "web",
          prompt: "Synthetic Prompt Workbench draft probe. Do not apply.",
          rubric: ["The synthetic draft remains review-only."],
        },
        reason: `${DRAFT_REASON_PREFIX}${nonce}`,
      },
    });
    draftId = draft.id;
    if (
      !draftId ||
      draft.kind !== "eval-edit" ||
      draft.status !== "draft" ||
      draft.reason !== `${DRAFT_REASON_PREFIX}${nonce}` ||
      draftBaseline.some((row) => row?.id === draftId)
    ) {
      fail("synthetic_eval_draft_identity_invalid");
    }
    const discarded = await driver.api(
      `/api/drafts/${encodeURIComponent(draftId)}`,
      {
        method: "DELETE",
      },
    );
    if (discarded.id !== draftId || discarded.status !== "discarded") {
      fail("synthetic_eval_draft_discard_failed");
    }
    draftDiscarded = true;
    removeOwnedDraftArtifact({ privateRoot, draftId, nonce });
    draftId = null;
    assertHistoryRestored(
      draftBaseline,
      (await driver.api("/api/drafts")).drafts,
      "id",
    );
    const run = await driver.runExactModelEval({
      familyId: args.familyId,
      caseId: args.caseId,
      timeoutMs: args.timeoutMs,
    });
    runId = run.id;
    validateEvalRun(run, {
      familyId: args.familyId,
      caseId: args.caseId,
      surface: "web",
      promptId: "main.conscious_agent",
      configuredRoute,
      expectedAgentHash,
      candidateSourceHash,
    });
    const privateArtifact = readPrivateJson(
      ensureContainedPath(
        privateRoot,
        path.join(privateRoot, "eval-runs", runId, "exact-model-eval.json"),
      ),
    );
    validatePrivateExactModelArtifact(privateArtifact, {
      familyId: args.familyId,
      caseId: args.caseId,
      surface: "web",
      expectedAgentHash,
      configuredProviderHash: sha(configuredRoute.provider),
      configuredModelHash: sha(configuredRoute.model),
      adminEmailHash: sha(auth.email),
    });
    await driver.assertEvalHistoryAfterReload(runId);
    const historyWithRun = (await driver.api("/api/evals/runs")).runs;
    if (!historyWithRun.some((row) => row?.id === runId)) {
      fail("eval_history_reload_mismatch");
    }
    const scheduleAfter = validateContinuitySchedule(
      (await driver.api("/api/scheduled-prompts?readOnly=true"))
        .scheduledPrompts,
    );
    if (scheduleConfigFingerprint(scheduleAfter) !== scheduleFingerprint) {
      fail("personal_owner_schedule_mutation_detected");
    }
    assertSecurityReport(await driver.securityReport());
    result = {
      schemaVersion: 1,
      status: "pass",
      releaseEligible: false,
      candidateMode: "PRE-GATE / NOT READY",
      checks: {
        tokenFreeLoopbackAdmin: true,
        installedBuildCurrent: true,
        framesHealthy: true,
        obsoleteCredentialRejected: true,
        promptRegistryAndLineage: true,
        continuityVisibleEditableWithoutSave: true,
        exactModelRouteAndSemanticEvidence: true,
        evalHistoryPersistedAfterReload: true,
        personalOwnerConfigurationUnchanged: true,
      },
      counts: {
        promptCount: registry.prompts.length,
        evalCaseCount: evalBank.caseCount,
        scheduleCount: schedulePayload.scheduledPrompts.length,
        frameCount,
        selectedEvalCaseCount: 1,
      },
      hashes: {
        candidateSourceHash,
        configuredProviderHash: sha(configuredRoute.provider),
        configuredModelHash: sha(configuredRoute.model),
        configuredAgentHash: expectedAgentHash,
        scheduleConfigHash: scheduleFingerprint,
      },
    };
  } catch (error) {
    journeyFailure = error;
  } finally {
    if (draftId) {
      try {
        if (!draftDiscarded) {
          await driver.api(`/api/drafts/${encodeURIComponent(draftId)}`, {
            method: "DELETE",
          });
        }
        removeOwnedDraftArtifact({ privateRoot, draftId, nonce });
        if (draftBaseline) {
          assertHistoryRestored(
            draftBaseline,
            (await driver.api("/api/drafts")).drafts,
            "id",
          );
        }
        draftId = null;
      } catch (error) {
        cleanupFailure = cleanupFailure || safeError(error?.message);
      }
    }
    if (runId) {
      try {
        removeOwnedEvalArtifact({
          privateRoot,
          runId,
          familyId: args.familyId,
          caseId: args.caseId,
          startedAtMs,
          nowMs: now(),
        });
        if (evalHistoryBaseline) {
          assertHistoryRestored(
            evalHistoryBaseline,
            (await driver.api("/api/evals/runs")).runs,
            "id",
          );
        }
        runId = null;
      } catch (error) {
        cleanupFailure = cleanupFailure || safeError(error?.message);
      }
    }
    await driver.close();
  }
  if (cleanupFailure)
    fail(`synthetic_artifact_cleanup_failed:${cleanupFailure}`);
  if (journeyFailure) throw journeyFailure;
  return result;
}

function writePrivateReport(root, report) {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  fs.mkdirSync(root, { recursive: true, mode: 0o700 });
  fs.chmodSync(root, 0o700);
  const target = path.join(root, `${stamp}.json`);
  fs.writeFileSync(target, `${JSON.stringify(report, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
    flag: "wx",
  });
  return sha(target, 16);
}

async function main() {
  let args;
  let driver;
  try {
    args = parseArgs();
    readWorkbenchState(args.origin);
    driver = new BrowserWorkbenchDriver(args);
    const report = await runInstalledJourney({ driver, args });
    const evidencePathHash = writePrivateReport(args.evidenceRoot, report);
    console.log(
      JSON.stringify(
        {
          ...report,
          evidence: { private: true, pathHash: evidencePathHash },
        },
        null,
        2,
      ),
    );
  } catch (error) {
    if (driver) await driver.close().catch(() => {});
    const report = {
      schemaVersion: 1,
      status: "blocked",
      releaseEligible: false,
      candidateMode: "PRE-GATE / NOT READY",
      blocker: safeError(error?.message),
    };
    if (args?.evidenceRoot) {
      try {
        report.evidence = {
          private: true,
          pathHash: writePrivateReport(args.evidenceRoot, report),
        };
      } catch {
        report.evidence = { private: true, status: "write_failed" };
      }
    }
    console.error(JSON.stringify(report, null, 2));
    process.exitCode = 1;
  }
}

module.exports = {
  AUTHORIZATION_ENV,
  DRAFT_REASON_PREFIX,
  assertFreshBuild,
  assertHistoryRestored,
  isExpectedSyntheticSaveConsoleError,
  parseArgs,
  removeOwnedDraftArtifact,
  removeOwnedEvalArtifact,
  runInstalledJourney,
  scheduleConfigFingerprint,
  selectPromptFromAtlas,
  selectExactModelCase,
  strictLoopbackOrigin,
  validateContinuitySchedule,
  validateEvalRun,
  validateFramesHealth,
  validatePrivateExactModelArtifact,
  validatePromptLineage,
};

if (require.main === module) {
  main();
}
