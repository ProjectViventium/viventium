"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
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
} = require("./run_installed_prompt_workbench_journey.cjs");

function sha(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value))
    .digest("hex")
    .slice(0, length);
}

const PROMPT_ID = "scheduler.consciousness_continuity_opportunity";
const FAMILY_ID = "feelings_embodiment_and_reaction";
const CASE_ID = "feelings_direct_question_without_state_recap";
const AGENT_ID = "synthetic-main-agent";
const PROVIDER = "synthetic-provider";
const MODEL = "synthetic-model";
const SOURCE_HASH = "1".repeat(16);
const FRONTEND_INPUT_HASH = "2".repeat(64);
const BUILT_ASSET_HASH = "3".repeat(64);
const REQUIRED_PROMPT_IDS = [
  "main.conscious_agent",
  "main.identity",
  "main.scheduling_self_continuity",
  PROMPT_ID,
];

function buildFixture() {
  return {
    available: true,
    entryAssets: ["/assets/index.js"],
    backend: {
      sourceCurrent: true,
      loadedSourceHash: SOURCE_HASH,
      currentSourceHash: SOURCE_HASH,
    },
    frontend: {
      receiptAvailable: true,
      schemaVersion: 1,
      receiptFrontendInputHash: FRONTEND_INPUT_HASH,
      currentFrontendInputHash: FRONTEND_INPUT_HASH,
      receiptBuiltAssetHash: BUILT_ASSET_HASH,
      currentBuiltAssetHash: BUILT_ASSET_HASH,
      receiptBuiltFileCount: 2,
      currentBuiltFileCount: 2,
      sourceCurrent: true,
      assetsCurrent: true,
      receiptValid: true,
    },
  };
}

function framesFixture() {
  return {
    frames: [],
    health: {
      status: "empty",
      source: "trusted_runtime_logs",
      reason: "no_matching_frames",
      filesScanned: 1,
      invalidEventCount: 0,
      truncatedReadCount: 0,
      releaseEvidence: false,
    },
  };
}

function promptFixtures() {
  const renderedText = "Rendered synthetic continuity prompt.";
  const registryRow = {
    id: PROMPT_ID,
    contentHash: "2".repeat(16),
    bodyHash: "3".repeat(16),
    includeCount: 0,
  };
  return {
    registry: {
      prompts: [
        registryRow,
        {
          id: "main.identity",
          contentHash: "4".repeat(16),
          bodyHash: "5".repeat(16),
          includeCount: 0,
        },
      ],
      flow: { nodes: [{ id: PROMPT_ID }], edges: [] },
    },
    detail: {
      id: PROMPT_ID,
      text: "---\nid: synthetic\n---\nSynthetic source.",
      body: "Synthetic source.",
      rendered: renderedText,
      contentHash: registryRow.contentHash,
      bodyHash: registryRow.bodyHash,
    },
    context: {
      promptId: PROMPT_ID,
      contentHash: registryRow.contentHash,
      bodyHash: registryRow.bodyHash,
      delivery: { kind: "compiled_runtime", state: "synced" },
      runtimePromptBundle: {
        status: "ok",
        promptState: "synced",
        liveBundleAvailable: true,
      },
    },
    rendered: {
      id: PROMPT_ID,
      rendered: renderedText,
      renderedHash: sha(renderedText),
    },
  };
}

function evalBankFixture() {
  return {
    familyCount: 1,
    caseCount: 1,
    families: [
      {
        id: FAMILY_ID,
        semanticJudge: true,
        promptRefs: ["main.conscious_agent"],
        cases: [
          {
            id: CASE_ID,
            surface: "web",
            prompt: "Synthetic prompt.",
            rubric: ["Synthetic rubric."],
            fixture: { feelings: { enabled: true } },
          },
        ],
      },
    ],
  };
}

function lineageFixture() {
  const lineage = {
    schemaVersion: 1,
    familyIds: [FAMILY_ID],
    caseIds: [CASE_ID],
    rootPromptIds: ["main.conscious_agent"],
    promptCount: 1,
    runtimeContextCount: 1,
    promptDependencies: [
      {
        id: "main.conscious_agent",
        kind: "prompt",
        status: "available",
        direct: true,
        contentHash: "6".repeat(16),
        bodyHash: "7".repeat(16),
        renderedHash: "8".repeat(16),
      },
    ],
    runtimeContextDependencies: [
      {
        id: "runtime.feelings.current_state",
        kind: "runtime_context",
        status: "available",
        contractHash: "9".repeat(16),
      },
    ],
    includeEdges: [],
  };
  lineage.manifestHash = sha(
    JSON.stringify(lineage, Object.keys(lineage).sort()),
  );
  return lineage;
}

function canonicalManifestHash(lineage) {
  const unsigned = { ...lineage };
  delete unsigned.manifestHash;
  return sha(stableStringify(unsigned));
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function evalRunFixture(overrides = {}) {
  const expectedAgentHash = sha(AGENT_ID);
  const lineage = lineageFixture();
  lineage.manifestHash = canonicalManifestHash(lineage);
  return {
    id: "20260825T120000Z-aaaaaaaaaaaa",
    artifactName: "20260825T120000Z-aaaaaaaaaaaa",
    createdAt: "2026-08-25T12:00:00+00:00",
    live: true,
    returnCode: 0,
    family: FAMILY_ID,
    surface: "web",
    promptId: "main.conscious_agent",
    selectedCaseIds: [CASE_ID],
    selectedCaseCount: 1,
    resultCount: 1,
    semanticJudgeRequired: true,
    candidateSourceHash: SOURCE_HASH,
    runnerSummary: {
      status: "partial_semantic_passed",
      selectedCaseCount: 1,
      resultCount: 1,
      completedCount: 1,
      failedCount: 0,
      semanticJudgedCount: 1,
      semanticPassedCount: 1,
      semanticFailedCount: 0,
      semanticJudgeUnavailableCount: 0,
      duplicateResponseQualityFailureCount: 0,
      unresolvedAsyncQualityFailureCount: 0,
    },
    lineageManifest: lineage,
    executionRoute: {
      status: "verified",
      configuredProvider: PROVIDER,
      configuredModel: MODEL,
      configuredProviderHash: sha(PROVIDER),
      configuredModelHash: sha(MODEL),
      observedProviderHash: sha(PROVIDER),
      observedModelHash: sha(MODEL),
      completedCaseCount: 1,
      artifactSha256: "a".repeat(64),
      caseEvidence: [
        {
          caseId: CASE_ID,
          agentIdHash: expectedAgentHash,
          requestIdentityHash: "b".repeat(16),
          semanticJudged: true,
          semanticPassed: true,
        },
      ],
    },
    ...overrides,
  };
}

function privateArtifactFixture(overrides = {}) {
  const requestHash = "b".repeat(16);
  const expectedAgentHash = sha(AGENT_ID);
  return {
    args: {
      agentIdHash: expectedAgentHash,
      judgeModelHash: "c".repeat(16),
      family: FAMILY_ID,
      caseId: CASE_ID,
      caseIds: [CASE_ID],
      surface: "web",
      promptId: "main.conscious_agent",
      localJwtFallback: true,
      semanticJudge: true,
    },
    summary: {
      status: "partial_semantic_passed",
      agentIdHash: expectedAgentHash,
      observedAgentIdHash: expectedAgentHash,
      selectedCaseCount: 1,
      resultCount: 1,
      completedCount: 1,
      failedCount: 0,
      semanticJudgedCount: 1,
      semanticPassedCount: 1,
      semanticFailedCount: 0,
      semanticJudgeUnavailableCount: 0,
      login: {
        authMode: "local_jwt_fallback",
        userEmailHash: "d".repeat(16),
      },
    },
    liveResults: [
      {
        caseId: CASE_ID,
        familyId: FAMILY_ID,
        surface: "web",
        observedSurface: "web",
        status: "completed",
        requestIdentityHash: requestHash,
        observedRequestIdentityHash: requestHash,
        observedAgentIdHash: expectedAgentHash,
        semanticJudge: {
          status: "judged",
          pass: true,
          attemptCount: 1,
          rawHash: "e".repeat(16),
        },
        qaCleanup: {
          status: "complete",
          conversationCount: 2,
          messageCount: 4,
        },
        fixtureRestoration: { status: "restored_exact" },
        promptFrameEvidenceForJudge: {
          prompt_frames: [
            {
              source: "runtime_route_log",
              prompt_family: "main_runtime",
              surface: "web",
              provider_hash: sha(PROVIDER),
              model_hash: sha(MODEL),
              agent_id_hash: expectedAgentHash,
              request_identity_hash: requestHash,
            },
          ],
        },
      },
    ],
    ...overrides,
  };
}

function continuityScheduleFixture() {
  return {
    id: "continuity-schedule",
    userId: "owner-id",
    title: "Consciousness Continuity",
    sourcePromptId: PROMPT_ID,
    effectivePromptId: PROMPT_ID,
    runEnvelopePromptId: "scheduler.run_envelope",
    canonicalOutputPromptId: "scheduler.canonical_output",
    standingCapabilityPromptId: "main.scheduling_self_continuity",
    schedule: {
      type: "interval",
      cadence: "restart_daily",
      every: 45,
      unit: "minute",
      activeWindow: { start: "09:00", end: "21:00" },
    },
    active: true,
    executor: "viventium_agent",
    channel: ["librechat"],
    memoryWriteMode: "off",
  };
}

function makeInstalledDriver(privateRoot, { unsafeEvalLink = false } = {}) {
  const draftId = "11111111-2222-4333-8444-555555555555";
  const run = evalRunFixture();
  const schedule = continuityScheduleFixture();
  const promptRows = REQUIRED_PROMPT_IDS.map((promptId) => ({
    id: promptId,
    contentHash: sha(`content:${promptId}`),
    bodyHash: sha(`body:${promptId}`),
  }));
  const registry = {
    prompts: promptRows,
    flow: { nodes: promptRows.map(({ id }) => ({ id })), edges: [] },
  };
  let draftRecord = null;
  let opened = false;
  let closed = false;
  let deterministicUiChecked = false;

  function promptPayload(promptId) {
    const row = promptRows.find((item) => item.id === promptId);
    const rendered = `Rendered ${promptId}.`;
    const context = {
      promptId,
      contentHash: row.contentHash,
      bodyHash: row.bodyHash,
      delivery: {
        kind:
          promptId === "main.identity" ? "managed_agent" : "compiled_runtime",
        state: "synced",
      },
      runtimePromptBundle: {
        status: "ok",
        promptState: "synced",
        liveBundleAvailable: true,
      },
    };
    if (promptId === "main.identity") {
      context.sync = {
        state: "synced",
        sourceHash: "a".repeat(16),
        liveHash: "a".repeat(16),
        agentId: AGENT_ID,
      };
    }
    return {
      detail: {
        id: promptId,
        text: `---\nid: ${promptId}\n---\nSynthetic source.`,
        body: "Synthetic source.",
        rendered,
        contentHash: row.contentHash,
        bodyHash: row.bodyHash,
      },
      context,
      rendered: { id: promptId, rendered, renderedHash: sha(rendered) },
    };
  }

  const driver = {
    get opened() {
      return opened;
    },
    get closed() {
      return closed;
    },
    get deterministicUiChecked() {
      return deterministicUiChecked;
    },
    async open() {
      opened = true;
    },
    async api(apiPath, options = {}) {
      if (apiPath === "/api/auth/status") {
        return {
          authenticated: true,
          admin: true,
          method: "local_loopback_admin",
          userId: "owner-id",
          email: "owner@example.com",
        };
      }
      if (apiPath === "/api/build-version") {
        return buildFixture();
      }
      if (apiPath === "/api/frames") return framesFixture();
      if (apiPath === "/api/prompts") return registry;
      if (apiPath === "/api/prompts/render" && options.method === "POST") {
        return promptPayload(options.body.promptId).rendered;
      }
      const contextMatch = apiPath.match(
        /^\/api\/prompts\/([^/]+)\/workbench-context$/,
      );
      if (contextMatch)
        return promptPayload(decodeURIComponent(contextMatch[1])).context;
      const detailMatch = apiPath.match(/^\/api\/prompts\/([^/]+)$/);
      if (detailMatch)
        return promptPayload(decodeURIComponent(detailMatch[1])).detail;
      if (apiPath === "/api/evals") return evalBankFixture();
      if (apiPath === `/api/evals/execution-route?family=${FAMILY_ID}`) {
        return {
          kind: "main",
          family: FAMILY_ID,
          provider: PROVIDER,
          model: MODEL,
        };
      }
      if (apiPath === "/api/drafts") {
        const draftPath = draftRecord
          ? path.join(privateRoot, "drafts", `${draftRecord.id}.json`)
          : null;
        return {
          drafts: draftPath && fs.existsSync(draftPath) ? [draftRecord] : [],
        };
      }
      if (apiPath === "/api/evals/case-draft" && options.method === "POST") {
        draftRecord = {
          id: draftId,
          kind: "eval-edit",
          status: "draft",
          reason: options.body.reason,
        };
        const draftPath = path.join(privateRoot, "drafts", `${draftId}.json`);
        fs.mkdirSync(path.dirname(draftPath), { recursive: true });
        fs.writeFileSync(draftPath, JSON.stringify(draftRecord));
        return { ...draftRecord };
      }
      if (apiPath === `/api/drafts/${draftId}` && options.method === "DELETE") {
        draftRecord = { ...draftRecord, status: "discarded" };
        fs.writeFileSync(
          path.join(privateRoot, "drafts", `${draftId}.json`),
          JSON.stringify(draftRecord),
        );
        return { ...draftRecord };
      }
      if (apiPath === "/api/evals/runs") {
        return {
          runs: fs.existsSync(path.join(privateRoot, "eval-runs", run.id))
            ? [run]
            : [],
        };
      }
      if (apiPath === "/api/scheduled-prompts?readOnly=true") {
        return { scheduledPrompts: [schedule] };
      }
      throw new Error(`unexpected_api_path:${apiPath}`);
    },
    async assertContinuityUi(observedSchedule) {
      assert.equal(observedSchedule.id, schedule.id);
    },
    async assertDeterministicUi() {
      deterministicUiChecked = true;
    },
    async runExactModelEval(selection) {
      assert.deepEqual(selection, {
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        timeoutMs: 480_000,
      });
      const runDir = path.join(privateRoot, "eval-runs", run.id);
      fs.mkdirSync(runDir, { recursive: true });
      fs.writeFileSync(
        path.join(runDir, "workbench-run.json"),
        JSON.stringify(run),
      );
      fs.writeFileSync(
        path.join(runDir, "exact-model-eval.json"),
        JSON.stringify(privateArtifactFixture()),
      );
      if (unsafeEvalLink) {
        fs.symlinkSync(
          path.join(privateRoot, "outside"),
          path.join(runDir, "unsafe-link"),
        );
      }
      return run;
    },
    async assertEvalHistoryAfterReload(runId) {
      assert.equal(runId, run.id);
      assert.equal(
        fs.existsSync(path.join(privateRoot, "eval-runs", run.id)),
        true,
      );
    },
    async securityReport() {
      return {
        tokenFreeUrl: true,
        noPersistentBearer: true,
        noReferrerDisclosure: true,
        credentialRequestCount: 0,
        externalRequestCount: 0,
        ownerMutationAttemptCount: 0,
        consoleErrorCount: 0,
        failedRequestCount: 0,
        httpErrorCount: 0,
      };
    },
    async close() {
      closed = true;
    },
  };
  return { driver, run };
}

test("requires explicit local QA and synthetic artifact authority", () => {
  assert.throws(
    () => parseArgs([], {}),
    /explicit_local_qa_authorization_required/,
  );
  assert.throws(
    () =>
      parseArgs(
        ["--local-qa", "--allow-live-eval", "--allow-synthetic-artifacts"],
        {},
      ),
    new RegExp(AUTHORIZATION_ENV),
  );
  const parsed = parseArgs(
    ["--local-qa", "--allow-live-eval", "--allow-synthetic-artifacts"],
    { [AUTHORIZATION_ENV]: "1" },
  );
  assert.equal(parsed.origin, "http://127.0.0.1:8781");
  assert.equal(parsed.caseId, CASE_ID);
});

test("accepts only a token-free loopback origin", () => {
  assert.equal(
    strictLoopbackOrigin("http://localhost:8781"),
    "http://localhost:8781",
  );
  for (const value of [
    "https://localhost:8781",
    "http://127.0.0.1:8781/?workbench_token=secret",
    "http://user:secret@localhost:8781",
    "http://example.test:8781",
    "http://localhost:8781/path",
    "http://localhost:8781/#token",
  ]) {
    assert.throws(
      () => strictLoopbackOrigin(value),
      /token_free_loopback_origin_required/,
    );
  }
});

test("consumes only the browser console error caused by the armed synthetic 503", () => {
  assert.equal(
    isExpectedSyntheticSaveConsoleError(
      "Failed to load resource: the server responded with a status of 503 (Service Unavailable)",
    ),
    true,
  );
  for (const message of [
    "Failed to load resource: the server responded with a status of 500 (Internal Server Error)",
    "Failed to save scheduled prompt",
    "Uncaught TypeError: undefined is not a function",
    "Failed to load resource: 503",
  ]) {
    assert.equal(isExpectedSyntheticSaveConsoleError(message), false);
  }
});

test("rejects a stale or incomplete installed backend before mutation", () => {
  assert.doesNotThrow(() => assertFreshBuild(buildFixture()));
  const missingReceipt = buildFixture();
  delete missingReceipt.frontend;
  assert.throws(
    () => assertFreshBuild(missingReceipt),
    /installed_frontend_build_receipt_invalid/,
  );
  const mismatchedReceipt = buildFixture();
  mismatchedReceipt.frontend.currentBuiltAssetHash = "f".repeat(64);
  assert.throws(
    () => assertFreshBuild(mismatchedReceipt),
    /installed_frontend_build_receipt_invalid/,
  );
  assert.throws(
    () =>
      assertFreshBuild({
        ...buildFixture(),
        backend: {
          sourceCurrent: false,
          loadedSourceHash: SOURCE_HASH,
          currentSourceHash: "f".repeat(16),
        },
      }),
    /installed_backend_source_stale/,
  );
});

test("requires a typed healthy Frames response", () => {
  assert.doesNotThrow(() => validateFramesHealth(framesFixture()));
  assert.throws(
    () => validateFramesHealth({ frames: [] }),
    /frames_health_unverified/,
  );
  for (const status of ["degraded", "unavailable"]) {
    const payload = framesFixture();
    payload.health.status = status;
    assert.throws(
      () => validateFramesHealth(payload),
      new RegExp(`frames_health_${status}`),
    );
  }
});

test("validates registry source, rendered, and live lineage", () => {
  assert.doesNotThrow(() => validatePromptLineage(promptFixtures(), PROMPT_ID));
  const bad = promptFixtures();
  bad.context.runtimePromptBundle.promptState = "source-ahead";
  assert.throws(
    () => validatePromptLineage(bad, PROMPT_ID),
    /prompt_source_rendered_live_lineage_mismatch/,
  );
});

test("accepts a verified include-only composite prompt and rejects an empty leaf", () => {
  const composite = promptFixtures();
  composite.registry.prompts[0].includeCount = 1;
  composite.registry.flow.nodes.push({ id: "main.identity" });
  composite.detail.body = "\n";
  composite.detail.includes = ["main.identity"];
  composite.detail.bodyHash = sha(composite.detail.body);
  composite.registry.prompts[0].bodyHash = composite.detail.bodyHash;
  composite.context.bodyHash = composite.detail.bodyHash;
  assert.doesNotThrow(() => validatePromptLineage(composite, PROMPT_ID));

  composite.registry.prompts[0].includeCount = 0;
  composite.detail.includes = [];
  assert.throws(
    () => validatePromptLineage(composite, PROMPT_ID),
    /prompt_source_rendered_live_lineage_mismatch/,
  );
});

test("selects one semantic web exact-model case and refuses native or paired cases", () => {
  const selected = selectExactModelCase(evalBankFixture(), {
    familyId: FAMILY_ID,
    caseId: CASE_ID,
  });
  assert.equal(selected.case.id, CASE_ID);

  const native = evalBankFixture();
  native.families[0].cases[0].surface = "telegram";
  assert.throws(
    () =>
      selectExactModelCase(native, { familyId: FAMILY_ID, caseId: CASE_ID }),
    /trusted_native_surface_runner_required/,
  );

  const paired = evalBankFixture();
  paired.families[0].cases[0].comparisonCaseId = "paired_control";
  assert.throws(
    () =>
      selectExactModelCase(paired, { familyId: FAMILY_ID, caseId: CASE_ID }),
    /bounded_unpaired_eval_case_required/,
  );
});

test("requires one visible active Continuity schedule", () => {
  const schedule = {
    id: "continuity-schedule",
    userId: "owner-id",
    title: "Consciousness Continuity",
    sourcePromptId: PROMPT_ID,
    effectivePromptId: PROMPT_ID,
    runEnvelopePromptId: "scheduler.run_envelope",
    canonicalOutputPromptId: "scheduler.canonical_output",
    standingCapabilityPromptId: "main.scheduling_self_continuity",
    schedule: {
      type: "interval",
      cadence: "restart_daily",
      every: 45,
      unit: "minute",
      activeWindow: { start: "09:00", end: "21:00" },
    },
    active: true,
    executor: "viventium_agent",
    channel: ["librechat"],
    memoryWriteMode: "off",
  };
  assert.equal(validateContinuitySchedule([schedule]).id, schedule.id);
  assert.throws(
    () => validateContinuitySchedule([{ ...schedule, active: false }]),
    /continuity_schedule_visibility_invalid/,
  );
  assert.throws(
    () =>
      validateContinuitySchedule([
        {
          ...schedule,
          effectivePromptId: "main.scheduling_self_continuity",
        },
      ]),
    /continuity_schedule_visibility_invalid/,
  );
});

test("schedule fingerprint covers owner configuration but not run history", () => {
  const schedule = validateContinuitySchedule([
    {
      id: "continuity-schedule",
      userId: "owner-id",
      title: "Consciousness Continuity",
      sourcePromptId: PROMPT_ID,
      effectivePromptId: PROMPT_ID,
      runEnvelopePromptId: "scheduler.run_envelope",
      canonicalOutputPromptId: "scheduler.canonical_output",
      standingCapabilityPromptId: "main.scheduling_self_continuity",
      schedule: { type: "daily", time: "09:00", timezone: "UTC" },
      active: true,
      executor: "viventium_agent",
      channel: ["librechat"],
      memoryWriteMode: "off",
      recentRuns: [{ runId: "old" }],
    },
  ]);
  assert.equal(
    scheduleConfigFingerprint(schedule),
    scheduleConfigFingerprint({
      ...schedule,
      recentRuns: [{ runId: "new" }],
      latestScheduledRun: { runId: "new" },
      updatedAt: "later",
    }),
  );
  assert.notEqual(
    scheduleConfigFingerprint(schedule),
    scheduleConfigFingerprint({ ...schedule, title: "Changed" }),
  );
});

test("accepts an exact candidate-bound provider, model, agent, surface, and semantic result", () => {
  assert.doesNotThrow(() =>
    validateEvalRun(evalRunFixture(), {
      familyId: FAMILY_ID,
      caseId: CASE_ID,
      surface: "web",
      promptId: "main.conscious_agent",
      configuredRoute: {
        kind: "main",
        family: FAMILY_ID,
        provider: PROVIDER,
        model: MODEL,
      },
      expectedAgentHash: sha(AGENT_ID),
      candidateSourceHash: SOURCE_HASH,
    }),
  );
});

test("rejects wrong provider, model, agent, surface, or stale candidate evidence", () => {
  const base = {
    familyId: FAMILY_ID,
    caseId: CASE_ID,
    surface: "web",
    promptId: "main.conscious_agent",
    configuredRoute: {
      kind: "main",
      family: FAMILY_ID,
      provider: PROVIDER,
      model: MODEL,
    },
    expectedAgentHash: sha(AGENT_ID),
    candidateSourceHash: SOURCE_HASH,
  };
  const wrongProvider = evalRunFixture();
  wrongProvider.executionRoute.configuredProvider = "wrong";
  assert.throws(
    () => validateEvalRun(wrongProvider, base),
    /exact_model_route_mismatch/,
  );
  const wrongModel = evalRunFixture();
  wrongModel.executionRoute.observedModelHash = sha("wrong");
  assert.throws(
    () => validateEvalRun(wrongModel, base),
    /exact_model_route_mismatch/,
  );
  const wrongAgent = evalRunFixture();
  wrongAgent.executionRoute.caseEvidence[0].agentIdHash = sha("wrong");
  assert.throws(
    () => validateEvalRun(wrongAgent, base),
    /exact_model_agent_mismatch/,
  );
  assert.throws(
    () => validateEvalRun(evalRunFixture({ surface: "telegram" }), base),
    /exact_model_surface_mismatch/,
  );
  assert.throws(
    () =>
      validateEvalRun(
        evalRunFixture({ candidateSourceHash: "f".repeat(16) }),
        base,
      ),
    /stale_eval_candidate/,
  );
});

test("requires private non-owner exact-model cleanup and fixture restoration", () => {
  assert.doesNotThrow(() =>
    validatePrivateExactModelArtifact(privateArtifactFixture(), {
      familyId: FAMILY_ID,
      caseId: CASE_ID,
      surface: "web",
      expectedAgentHash: sha(AGENT_ID),
      configuredProviderHash: sha(PROVIDER),
      configuredModelHash: sha(MODEL),
      adminEmailHash: "f".repeat(16),
    }),
  );
  const owner = privateArtifactFixture();
  owner.summary.login.userEmailHash = "f".repeat(16);
  assert.throws(
    () =>
      validatePrivateExactModelArtifact(owner, {
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        surface: "web",
        expectedAgentHash: sha(AGENT_ID),
        configuredProviderHash: sha(PROVIDER),
        configuredModelHash: sha(MODEL),
        adminEmailHash: "f".repeat(16),
      }),
    /personal_owner_eval_forbidden/,
  );
  const dirty = privateArtifactFixture();
  dirty.liveResults[0].qaCleanup.status = "skipped";
  assert.throws(
    () =>
      validatePrivateExactModelArtifact(dirty, {
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        surface: "web",
        expectedAgentHash: sha(AGENT_ID),
        configuredProviderHash: sha(PROVIDER),
        configuredModelHash: sha(MODEL),
        adminEmailHash: "f".repeat(16),
      }),
    /synthetic_eval_cleanup_unverified/,
  );
  const staleRestoration = privateArtifactFixture();
  staleRestoration.liveResults[0].fixtureRestoration.status = "restored";
  assert.throws(
    () =>
      validatePrivateExactModelArtifact(staleRestoration, {
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        surface: "web",
        expectedAgentHash: sha(AGENT_ID),
        configuredProviderHash: sha(PROVIDER),
        configuredModelHash: sha(MODEL),
        adminEmailHash: "f".repeat(16),
      }),
    /synthetic_eval_cleanup_unverified/,
  );
});

test("removes only the exact discarded synthetic draft artifact", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw-draft-cleanup-"));
  const draftId = "11111111-2222-4333-8444-555555555555";
  const nonce = "nonce-a";
  const drafts = path.join(root, "drafts");
  fs.mkdirSync(drafts, { recursive: true });
  const draftPath = path.join(drafts, `${draftId}.json`);
  fs.writeFileSync(
    draftPath,
    JSON.stringify({
      id: draftId,
      kind: "eval-edit",
      status: "discarded",
      reason: `${DRAFT_REASON_PREFIX}${nonce}`,
    }),
  );
  removeOwnedDraftArtifact({ privateRoot: root, draftId, nonce });
  assert.equal(fs.existsSync(draftPath), false);

  const wrongId = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
  const wrongPath = path.join(drafts, `${wrongId}.json`);
  fs.writeFileSync(
    wrongPath,
    JSON.stringify({
      id: wrongId,
      kind: "source-edit",
      status: "discarded",
      reason: `${DRAFT_REASON_PREFIX}${nonce}`,
    }),
  );
  assert.throws(
    () =>
      removeOwnedDraftArtifact({ privateRoot: root, draftId: wrongId, nonce }),
    /owned_draft_cleanup_refused/,
  );
  assert.equal(fs.existsSync(wrongPath), true);
  fs.rmSync(root, { recursive: true, force: true });
});

test("removes only the exact current synthetic eval run without following links", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw-eval-cleanup-"));
  const run = evalRunFixture();
  const runDir = path.join(root, "eval-runs", run.id);
  fs.mkdirSync(runDir, { recursive: true });
  fs.writeFileSync(
    path.join(runDir, "workbench-run.json"),
    JSON.stringify(run),
  );
  fs.writeFileSync(
    path.join(runDir, "exact-model-eval.json"),
    JSON.stringify(privateArtifactFixture()),
  );
  removeOwnedEvalArtifact({
    privateRoot: root,
    runId: run.id,
    familyId: FAMILY_ID,
    caseId: CASE_ID,
    startedAtMs: Date.parse("2026-08-25T11:59:00Z"),
    nowMs: Date.parse("2026-08-25T12:01:00Z"),
  });
  assert.equal(fs.existsSync(runDir), false);

  fs.mkdirSync(runDir, { recursive: true });
  fs.writeFileSync(
    path.join(runDir, "workbench-run.json"),
    JSON.stringify(run),
  );
  fs.symlinkSync(path.join(root, "outside"), path.join(runDir, "unsafe-link"));
  assert.throws(
    () =>
      removeOwnedEvalArtifact({
        privateRoot: root,
        runId: run.id,
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        startedAtMs: Date.parse("2026-08-25T11:59:00Z"),
        nowMs: Date.parse("2026-08-25T12:01:00Z"),
      }),
    /owned_eval_cleanup_refused/,
  );
  assert.equal(fs.existsSync(runDir), true);
  fs.rmSync(root, { recursive: true, force: true });
});

test("requires draft and eval history to return exactly to their baselines", () => {
  const before = [
    { id: "old", status: "discarded" },
    { id: "older", status: "applied" },
  ];
  assert.doesNotThrow(() => assertHistoryRestored(before, [...before], "id"));
  assert.throws(
    () =>
      assertHistoryRestored(
        before,
        [...before, { id: "new", status: "discarded" }],
        "id",
      ),
    /history_cleanup_incomplete/,
  );
  assert.throws(
    () =>
      assertHistoryRestored(
        before,
        [{ ...before[0], reason: "changed" }, before[1]],
        "id",
      ),
    /history_cleanup_incomplete/,
  );
});

test("filters the virtualized atlas before selecting an exact prompt", async () => {
  const events = [];
  const item = {
    async waitFor(options) {
      events.push(["waitFor", options]);
    },
    async click() {
      events.push(["click"]);
    },
  };
  const page = {
    getByPlaceholder(label, options) {
      assert.equal(label, "Search prompt flow...");
      assert.deepEqual(options, { exact: true });
      return {
        async fill(value) {
          events.push(["fill", value]);
        },
      };
    },
    locator(selector) {
      assert.equal(selector, ".atlas-pane");
      return {
        getByText(label, options) {
          assert.equal(label, "Main agent instruction");
          assert.deepEqual(options, { exact: true });
          return { first: () => item };
        },
      };
    },
  };

  await selectPromptFromAtlas(page, "Main agent instruction");

  assert.deepEqual(events, [
    ["fill", "Main agent instruction"],
    ["waitFor", { state: "visible" }],
    ["click"],
    ["fill", ""],
  ]);
});

test("clears the atlas filter when prompt selection fails", async () => {
  const fills = [];
  const page = {
    getByPlaceholder() {
      return { fill: async (value) => fills.push(value) };
    },
    locator() {
      return {
        getByText() {
          return {
            first: () => ({
              waitFor: async () => {},
              click: async () => {
                throw new Error("synthetic_selection_failure");
              },
            }),
          };
        },
      };
    },
  };

  await assert.rejects(
    () => selectPromptFromAtlas(page, "Main agent instruction"),
    /synthetic_selection_failure/,
  );
  assert.deepEqual(fills, ["Main agent instruction", ""]);
});

test("runs the complete installed contract and restores exact synthetic history", async () => {
  const privateRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "pw-installed-journey-"),
  );
  const { driver, run } = makeInstalledDriver(privateRoot);
  try {
    const report = await runInstalledJourney({
      driver,
      args: {
        familyId: FAMILY_ID,
        caseId: CASE_ID,
        timeoutMs: 480_000,
      },
      privateRoot,
      now: () => Date.parse("2026-08-25T12:00:00Z"),
    });
    assert.equal(report.status, "pass");
    assert.equal(report.releaseEligible, false);
    assert.equal(report.candidateMode, "PRE-GATE / NOT READY");
    assert.equal(driver.opened, true);
    assert.equal(driver.closed, true);
    assert.equal(driver.deterministicUiChecked, true);
    assert.equal(
      fs.existsSync(
        path.join(
          privateRoot,
          "drafts",
          "11111111-2222-4333-8444-555555555555.json",
        ),
      ),
      false,
    );
    assert.equal(
      fs.existsSync(path.join(privateRoot, "eval-runs", run.id)),
      false,
    );
  } finally {
    fs.rmSync(privateRoot, { recursive: true, force: true });
  }
});

test("fails closed when the exact synthetic eval cannot be removed", async () => {
  const privateRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "pw-installed-cleanup-"),
  );
  const { driver } = makeInstalledDriver(privateRoot, { unsafeEvalLink: true });
  try {
    await assert.rejects(
      () =>
        runInstalledJourney({
          driver,
          args: {
            familyId: FAMILY_ID,
            caseId: CASE_ID,
            timeoutMs: 480_000,
          },
          privateRoot,
          now: () => Date.parse("2026-08-25T12:00:00Z"),
        }),
      /synthetic_artifact_cleanup_failed:owned_eval_cleanup_refused/,
    );
    assert.equal(driver.closed, true);
  } finally {
    fs.rmSync(privateRoot, { recursive: true, force: true });
  }
});
