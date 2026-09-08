"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  AUTHORIZATION_ENV,
  buildFamilyPlans,
  cleanupOwnedArtifacts,
  parseArgs,
  runFullBankAcceptance,
  sha,
  stableStringify,
  validateEvalBank,
  validatePlanCoverage,
  validateRun,
} = require("./run_pw_047_installed_full_bank.cjs");

const NOW_MS = Date.parse("2026-08-26T12:00:00.000Z");
const SOURCE_HASH = "1".repeat(16);
const BUILD_HASH = "2".repeat(16);
const MAIN_AGENT_ID = "agent_synthetic_main";
const NATIVE_SURFACES = new Set([
  "telegram",
  "voice",
  "wing",
  "listen_only",
  "scheduler",
]);

function clone(value) {
  return structuredClone(value);
}

function hash(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value))
    .digest("hex")
    .slice(0, length);
}

function jsonHash(value) {
  return hash(stableStringify(value), 64);
}

function makeBank() {
  const families = [
    {
      id: "synthetic_main_family",
      semanticJudge: true,
      promptRefs: ["main.identity"],
      cases: [
        {
          id: "synthetic_main_case",
          surface: "web",
          promptRefs: ["main.identity"],
        },
      ],
    },
    {
      id: "synthetic_specialist_family",
      runner: "background_execution",
      executionTarget: {
        agentId: "agent_synthetic_specialist",
        promptRef: "cortex.synthetic.execution",
      },
      promptRefs: ["cortex.synthetic.execution"],
      cases: [{ id: "synthetic_specialist_case", surface: "web" }],
    },
    {
      id: "synthetic_activation_family",
      runner: "background_activation",
      activationTargets: [
        {
          key: "synthetic_required",
          agentId: "agent_synthetic_required",
          promptRef: "cortex.synthetic.required.activation",
        },
        {
          key: "synthetic_negative",
          agentId: "agent_synthetic_negative",
          promptRef: "cortex.synthetic.negative.activation",
        },
      ],
      cases: [
        {
          id: "synthetic_activation_case",
          surface: "web",
          required_activations: ["synthetic_required"],
          allowed_activations: ["synthetic_required"],
        },
      ],
    },
  ];
  return {
    version: 7,
    scope: "public-safe synthetic PW-047 fixture",
    familyCount: families.length,
    caseCount: families.reduce(
      (count, family) => count + family.cases.length,
      0,
    ),
    families,
  };
}

function makeBuild() {
  return {
    available: true,
    indexHash: BUILD_HASH,
    entryAssets: ["/assets/synthetic.js"],
    backend: {
      loadedSourceHash: SOURCE_HASH,
      currentSourceHash: SOURCE_HASH,
      sourceCurrent: true,
    },
  };
}

function makeRoutes() {
  return {
    synthetic_main_family: {
      kind: "main",
      family: "synthetic_main_family",
      provider: "synthetic-main-provider",
      model: "synthetic-main-model",
      effort: "medium",
      fallbacks: [],
    },
    synthetic_specialist_family: {
      kind: "background_execution",
      family: "synthetic_specialist_family",
      agentId: "agent_synthetic_specialist",
      promptRef: "cortex.synthetic.execution",
      provider: "synthetic-specialist-provider",
      model: "synthetic-specialist-model",
      effort: "low",
      fallbacks: [],
    },
    synthetic_activation_family: {
      kind: "background_activation",
      family: "synthetic_activation_family",
      targets: [
        {
          targetKey: "synthetic_required",
          provider: "synthetic-required-provider",
          model: "synthetic-required-model",
          effort: "low",
          fallbacks: [
            {
              provider: "synthetic-declared-fallback",
              model: "synthetic-fallback-model",
              effort: "high",
            },
          ],
        },
        {
          targetKey: "synthetic_negative",
          provider: "synthetic-negative-provider",
          model: "synthetic-negative-model",
          effort: "none",
          fallbacks: [],
        },
      ],
    },
  };
}

function makeMixedSurfaceBank() {
  const bank = makeBank();
  bank.families[0].cases.push(
    { id: "synthetic_voice_case", surface: "voice" },
    { id: "synthetic_telegram_case", surface: "telegram" },
    { id: "synthetic_memory_case", surface: "memory_hardening" },
  );
  bank.caseCount = bank.families.reduce(
    (count, family) => count + family.cases.length,
    0,
  );
  return bank;
}

function makeRoutesForCatalog(catalog) {
  return Object.fromEntries(
    catalog.families.map((family, familyIndex) => {
      if (family.runner === "background_activation") {
        return [
          family.id,
          {
            kind: family.runner,
            family: family.id,
            targets: family.activationTargets.map((target, targetIndex) => ({
              targetKey: target.key,
              provider: `synthetic-provider-${familyIndex}-${targetIndex}`,
              model: `synthetic-model-${familyIndex}-${targetIndex}`,
              effort: "low",
              fallbacks: [],
            })),
          },
        ];
      }
      return [
        family.id,
        {
          kind: family.runner,
          family: family.id,
          ...(family.runner === "background_execution"
            ? family.executionTarget
            : {}),
          provider: `synthetic-provider-${familyIndex}`,
          model: `synthetic-model-${familyIndex}`,
          effort: "medium",
          fallbacks: [],
        },
      ];
    }),
  );
}

function makeLineage(familyId, caseIds) {
  const lineage = {
    schemaVersion: 1,
    familyIds: [familyId],
    caseIds,
    rootPromptIds: [],
    promptDependencies: [],
    runtimeContextDependencies: [],
    includeEdges: [],
    promptCount: 0,
    runtimeContextCount: 0,
  };
  lineage.manifestHash = hash(stableStringify(lineage));
  return lineage;
}

function makeActivationArtifact(family, route) {
  const results = [];
  for (const testCase of family.cases) {
    for (const target of route.targets) {
      const required = testCase.required_activations.includes(target.targetKey);
      const allowed = testCase.allowed_activations.includes(target.targetKey);
      const actual = required;
      results.push({
        caseId: testCase.id,
        familyId: family.id,
        surface: testCase.surface,
        targetKey: target.targetKey,
        repetition: 1,
        required,
        allowed,
        actual,
        pass: true,
        providerUsed: target.provider,
        modelUsed: target.model,
        effortUsed: target.effort,
        requestedProvider: target.provider,
        requestedModel: target.model,
        requestedEffort: target.effort,
        effectiveProvider: target.provider,
        effectiveModel: target.model,
        effectiveEffort: target.effort,
        fallbackReason: "none",
        providerAttempts: [
          {
            provider: target.provider,
            model: target.model,
            effort: target.effort,
            source: "primary",
            status: "completed",
            fallbackReason: "none",
            shouldActivate: actual,
          },
        ],
        error: null,
      });
    }
  }
  return {
    summary: {
      mode: "live",
      status: "passed",
      familyId: family.id,
      sourceBundleHash: "3".repeat(16),
      promptBankHash: "4".repeat(16),
      selectedCaseCount: family.cases.length,
      selectedTargetCount: route.targets.length,
      repetitions: 1,
      resultCount: results.length,
      completedCount: results.length,
      passCount: results.length,
      failureCount: 0,
      failedCaseRunCount: 0,
      falsePositiveCount: 0,
      falseNegativeCount: 0,
      unavailableCount: 0,
      unavailableRequiredCount: 0,
      timeoutOrProviderErrorCount: 0,
      inconsistentDecisionCount: 0,
      semanticInconsistentDecisionCount: 0,
      providerOverride: null,
      modelOverride: null,
      fallbacksEnabled: true,
    },
    results,
  };
}

function makeActivationEvidence(artifact) {
  return artifact.results.map((row) => ({
    caseId: row.caseId,
    targetKey: row.targetKey,
    repetition: row.repetition,
    required: row.required,
    allowed: row.allowed,
    actual: row.actual,
    passed: row.pass,
    requestedProvider: row.requestedProvider,
    requestedModel: row.requestedModel,
    requestedEffort: row.requestedEffort,
    effectiveProvider: row.providerUsed,
    effectiveModel: row.modelUsed,
    effectiveEffort: row.effortUsed,
    fallbackReason: row.fallbackReason,
    primaryFailureVerified: false,
  }));
}

function makeRun({
  family,
  route,
  runIndex,
  artifactBytes,
  surface = family.cases[0]?.surface,
}) {
  const second = String(runIndex + 1).padStart(2, "0");
  const id = `20260826T1200${second}Z-${String(runIndex + 1).padStart(12, "0")}`;
  const caseIds = family.cases.map((row) => row.id);
  const activation = family.runner === "background_activation";
  const semanticRequired =
    family.runner === "background_execution" ||
    family.semanticJudge === true ||
    family.cases.some((row) => row.semanticJudge === true);
  const expectedAgentId =
    family.runner === "background_execution"
      ? family.executionTarget.agentId
      : MAIN_AGENT_ID;
  const resultCount = activation
    ? caseIds.length * route.targets.length
    : caseIds.length;
  const runnerSummary = activation
    ? clone(JSON.parse(artifactBytes).summary)
    : {
        status: semanticRequired
          ? "partial_semantic_passed"
          : "partial_baseline",
        resultCount,
        completedCount: resultCount,
        failedCount: 0,
        semanticJudgedCount: semanticRequired ? caseIds.length : 0,
        semanticPassedCount: semanticRequired ? caseIds.length : 0,
        semanticFailedCount: 0,
        semanticJudgeUnavailableCount: 0,
        duplicateResponseQualityFailureCount: 0,
        unresolvedAsyncQualityFailureCount: 0,
      };
  const executionRoute = activation
    ? {
        status: "verified",
        completedCaseCount: resultCount,
        artifactSha256: hash(artifactBytes, 64),
        routes: route.targets.map((target) => ({
          targetKey: target.targetKey,
          requestedProvider: target.provider,
          requestedModel: target.model,
          requestedEffort: target.effort,
          configuredProvider: target.provider,
          configuredModel: target.model,
          effectiveProvider: target.provider,
          effectiveModel: target.model,
          effectiveEffort: target.effort,
          fallbackUsed: false,
          fallbackAuthorized: false,
          fallbackReason: "none",
        })),
        caseEvidence: makeActivationEvidence(JSON.parse(artifactBytes)),
      }
    : {
        status: "verified",
        requestedProvider: route.provider,
        requestedModel: route.model,
        requestedEffort: route.effort,
        effectiveProvider: route.provider,
        effectiveModel: route.model,
        effectiveEffort: route.effort,
        fallbackUsed: false,
        fallbackAuthorized: false,
        fallbackReason: "none",
        configuredProvider: route.provider,
        configuredModel: route.model,
        configuredProviderHash: hash(route.provider),
        configuredModelHash: hash(route.model),
        observedProviderHash: hash(route.provider),
        observedModelHash: hash(route.model),
        completedCaseCount: caseIds.length,
        artifactSha256: hash(artifactBytes, 64),
        routeExecution: "executed",
        caseEvidence: caseIds.map((caseId) => ({
          caseId,
          agentIdHash: hash(expectedAgentId),
          requestIdentityHash: hash(`request:${caseId}`),
          semanticJudged: semanticRequired,
          semanticPassed: semanticRequired,
        })),
      };
  if (!activation && NATIVE_SURFACES.has(surface)) {
    const completionExpected = surface !== "listen_only";
    const completionSurface =
      surface === "telegram"
        ? "telegram"
        : surface === "scheduler"
          ? "workbench"
          : "voice";
    runnerSummary.status = semanticRequired
      ? "completed_with_semantic_native_surface_evidence"
      : "completed_native_surface_evidence_without_semantic_judge";
    executionRoute.routeExecution = completionExpected
      ? "executed"
      : "suppressed_by_surface_contract";
    for (const evidence of executionRoute.caseEvidence) {
      evidence.surface = surface;
      evidence.completionSurface = completionSurface;
      evidence.completionExpected = completionExpected;
      if (!completionExpected) evidence.agentIdHash = "not_applicable";
    }
  }
  return {
    id,
    returnCode: 0,
    resultCount,
    selectedCaseCount: caseIds.length,
    selectedCaseIds: caseIds,
    createdAt: new Date(NOW_MS + (runIndex + 1) * 1000).toISOString(),
    live: true,
    maxCases: caseIds.length,
    family: family.id,
    surface,
    candidateSourceHash: SOURCE_HASH,
    lineageManifest: makeLineage(family.id, caseIds),
    executionTarget:
      family.runner === "background_execution"
        ? {
            mode: "direct_background_agent",
            ...clone(family.executionTarget),
          }
        : null,
    semanticJudgeRequired: semanticRequired,
    runnerSummary,
    executionRoute,
    artifactName: id,
    privateOutputAvailable: true,
    stdoutTail: "",
    stderrTail: "",
  };
}

class FixtureDriver {
  constructor(
    privateRoot,
    {
      bank = makeBank(),
      bankRead = null,
      routeRead = null,
      runMutator = null,
      artifactMutator = null,
      readbackMutator = null,
      historyMissing = false,
    } = {},
  ) {
    this.privateRoot = privateRoot;
    this.bank = bank;
    this.bankRead = bankRead;
    this.routeRead = routeRead;
    this.runMutator = runMutator;
    this.artifactMutator = artifactMutator;
    this.readbackMutator = readbackMutator;
    this.historyMissing = historyMissing;
    this.routes = makeRoutes();
    this.runs = new Map();
    this.postBodies = [];
    this.bankReads = 0;
    this.routeReads = new Map();
  }

  async api(apiPath, options = {}) {
    if (apiPath === "/api/auth/status") {
      return {
        authenticated: true,
        admin: true,
        method: "local_loopback_admin",
      };
    }
    if (apiPath === "/api/build-version") return clone(makeBuild());
    if (apiPath === "/api/prompts/main.identity/workbench-context") {
      return {
        promptId: "main.identity",
        delivery: { kind: "managed_agent", state: "synced" },
        sync: {
          state: "synced",
          agentId: MAIN_AGENT_ID,
          sourceHash: "5".repeat(16),
          liveHash: "5".repeat(16),
        },
      };
    }
    if (apiPath === "/api/evals") {
      this.bankReads += 1;
      return clone(
        this.bankRead
          ? this.bankRead(this.bankReads, clone(this.bank))
          : this.bank,
      );
    }
    if (apiPath.startsWith("/api/evals/execution-route?family=")) {
      const familyId = decodeURIComponent(apiPath.split("=")[1]);
      const readNumber = (this.routeReads.get(familyId) || 0) + 1;
      this.routeReads.set(familyId, readNumber);
      const route = clone(this.routes[familyId]);
      return clone(
        this.routeRead
          ? this.routeRead({ familyId, readNumber, route })
          : route,
      );
    }
    if (apiPath === "/api/evals/run" && options.method === "POST") {
      const body = clone(options.body);
      this.postBodies.push(body);
      const family = this.bank.families.find((row) => row.id === body.family);
      const selectedCases = body.caseIds.map((caseId) =>
        family.cases.find((row) => row.id === caseId),
      );
      if (
        selectedCases.some(
          (testCase) => !testCase || testCase.surface !== body.surface,
        )
      ) {
        throw new Error("synthetic_fixture_surface_selection_mismatch");
      }
      const selectedFamily = { ...clone(family), cases: clone(selectedCases) };
      const route = this.routes[body.family];
      const runIndex = this.runs.size;
      let artifact =
        selectedFamily.runner === "background_activation"
          ? makeActivationArtifact(selectedFamily, route)
          : {
              schemaVersion: 1,
              summary: { status: "synthetic_private_fixture" },
            };
      if (this.artifactMutator) {
        artifact =
          this.artifactMutator({
            artifact: clone(artifact),
            family: clone(selectedFamily),
            route: clone(route),
          }) || artifact;
      }
      const artifactBytes = `${JSON.stringify(artifact)}\n`;
      let run = makeRun({
        family: selectedFamily,
        route,
        runIndex,
        artifactBytes,
        surface: body.surface,
      });
      const runDir = path.join(this.privateRoot, "eval-runs", run.id);
      fs.mkdirSync(runDir, { recursive: true, mode: 0o700 });
      const artifactName =
        selectedFamily.runner === "background_activation"
          ? "activation-model-eval.json"
          : NATIVE_SURFACES.has(body.surface)
            ? "native-surface-playwright-qa.json"
            : "exact-model-eval.json";
      fs.writeFileSync(path.join(runDir, artifactName), artifactBytes, {
        mode: 0o600,
      });
      if (this.runMutator) {
        run =
          this.runMutator({
            run: clone(run),
            family: clone(selectedFamily),
            route: clone(route),
          }) || run;
      }
      fs.writeFileSync(
        path.join(runDir, "workbench-run.json"),
        `${JSON.stringify(run)}\n`,
        { mode: 0o600 },
      );
      this.runs.set(run.id, clone(run));
      return clone(run);
    }
    if (apiPath === "/api/evals/runs") {
      const rows = [...this.runs.values()].reverse();
      return { runs: this.historyMissing ? rows.slice(1) : clone(rows) };
    }
    if (apiPath.startsWith("/api/evals/runs/")) {
      const runId = decodeURIComponent(
        apiPath.slice("/api/evals/runs/".length),
      );
      if (this.historyMissing || !this.runs.has(runId)) {
        throw new Error("synthetic_history_missing");
      }
      const run = clone(this.runs.get(runId));
      return clone(
        this.readbackMutator
          ? this.readbackMutator({ run, runId }) || run
          : run,
      );
    }
    throw new Error(`unexpected_fixture_path:${apiPath}`);
  }
}

function makeProgrammaticArgs(evidenceRoot) {
  return {
    origin: "http://127.0.0.1:8781",
    evidenceRoot,
    authorizationConfirmed: true,
    live: true,
  };
}

async function withFixture(options, callback) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw047-"));
  const privateRoot = path.join(root, "private-workbench");
  const evidenceRoot = path.join(root, "evidence");
  fs.mkdirSync(privateRoot, { recursive: true });
  const driver = new FixtureDriver(privateRoot, options);
  try {
    return await callback({ root, privateRoot, evidenceRoot, driver });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

async function executeFixture(options = {}) {
  return withFixture(options, async ({ privateRoot, evidenceRoot, driver }) => {
    const result = await runFullBankAcceptance({
      driver,
      readbackDriver: driver,
      args: makeProgrammaticArgs(evidenceRoot),
      privateRoot,
      now: () => NOW_MS + 60_000,
      randomBytes: () => Buffer.alloc(16, 7),
    });
    return {
      result,
      driver,
      privateReport: JSON.parse(
        fs.readFileSync(result.privateAggregatePath, "utf8"),
      ),
      publicReport: JSON.parse(
        fs.readFileSync(result.publicSummaryPath, "utf8"),
      ),
    };
  });
}

test("requires all explicit local full-bank and live authorizations", () => {
  assert.throws(
    () => parseArgs([], { [AUTHORIZATION_ENV]: "1" }),
    /explicit_local_full_bank_authorization_required/,
  );
  assert.throws(
    () =>
      parseArgs(
        [
          "--local-qa",
          "--full-current-bank",
          "--allow-live-eval",
          "--run-live",
        ],
        {},
      ),
    new RegExp(`${AUTHORIZATION_ENV}_required`),
  );
  assert.throws(
    () =>
      parseArgs(
        [
          "--local-qa",
          "--full-current-bank",
          "--allow-live-eval",
          "--run-live",
        ],
        { [AUTHORIZATION_ENV]: "1", CI: "true" },
      ),
    /installed_local_qa_forbidden_in_ci_or_production/,
  );
});

test("rejects non-loopback, credential-bearing, and token URLs", () => {
  const base = [
    "--local-qa",
    "--full-current-bank",
    "--allow-live-eval",
    "--run-live",
  ];
  const env = { [AUTHORIZATION_ENV]: "1" };
  for (const origin of [
    "https://example.com",
    "http://127.0.0.1:8781/?workbench_token=synthetic-value",
    "http://qa-user:synthetic-value@127.0.0.1:8781/",
    "http://localhost:8781/#token",
  ]) {
    assert.throws(
      () => parseArgs([...base, `--origin=${origin}`], env),
      /token_free_loopback_origin_required/,
    );
  }
});

test("rejects a missing family, missing case, and declared count drift", () => {
  const missingFamily = makeBank();
  missingFamily.familyCount += 1;
  assert.throws(
    () => validateEvalBank(missingFamily),
    /eval_family_count_drift/,
  );

  const missingCase = makeBank();
  delete missingCase.families[0].cases[0].id;
  assert.throws(() => validateEvalBank(missingCase), /eval_case_id_missing/);

  const countDrift = makeBank();
  countDrift.caseCount += 1;
  assert.throws(() => validateEvalBank(countDrift), /eval_case_count_drift/);
});

test("rejects duplicate family and globally duplicate case IDs", () => {
  const duplicateFamily = makeBank();
  duplicateFamily.families[1].id = duplicateFamily.families[0].id;
  assert.throws(
    () => validateEvalBank(duplicateFamily),
    /duplicate_eval_family_id/,
  );

  const duplicateCase = makeBank();
  duplicateCase.families[1].cases[0].id = duplicateCase.families[0].cases[0].id;
  assert.throws(
    () => validateEvalBank(duplicateCase),
    /duplicate_eval_case_id/,
  );
});

test("partitions one mixed family into exact web, native, and non-native surface plans", async () => {
  const bank = makeMixedSurfaceBank();
  const catalog = validateEvalBank(bank);
  const plans = await buildFamilyPlans({
    catalog,
    configuredRoutes: makeRoutes(),
    mainAgentId: MAIN_AGENT_ID,
  });
  const mixedPlans = plans.filter(
    (plan) => plan.familyId === "synthetic_main_family",
  );

  assert.deepEqual(
    mixedPlans.map((plan) => ({
      surface: plan.surface,
      nativeSurface: plan.nativeSurface,
      caseIds: plan.caseIds,
      model: plan.configuredRoute.model,
      semanticJudgeRequired: plan.semanticJudgeRequired,
    })),
    [
      {
        surface: "web",
        nativeSurface: null,
        caseIds: ["synthetic_main_case"],
        model: "synthetic-main-model",
        semanticJudgeRequired: true,
      },
      {
        surface: "voice",
        nativeSurface: "voice",
        caseIds: ["synthetic_voice_case"],
        model: "synthetic-main-model",
        semanticJudgeRequired: true,
      },
      {
        surface: "telegram",
        nativeSurface: "telegram",
        caseIds: ["synthetic_telegram_case"],
        model: "synthetic-main-model",
        semanticJudgeRequired: true,
      },
      {
        surface: "memory_hardening",
        nativeSurface: null,
        caseIds: ["synthetic_memory_case"],
        model: "synthetic-main-model",
        semanticJudgeRequired: true,
      },
    ],
  );
});

test("rejects a missing or duplicate surface subgroup before any execution", async () => {
  const catalog = validateEvalBank(makeMixedSurfaceBank());
  const plans = await buildFamilyPlans({
    catalog,
    configuredRoutes: makeRoutes(),
    mainAgentId: MAIN_AGENT_ID,
  });

  assert.throws(
    () => validatePlanCoverage(catalog, plans.slice(1)),
    /eval_surface_plan_missing/,
  );
  assert.throws(
    () => validatePlanCoverage(catalog, [...plans, clone(plans[0])]),
    /duplicate_eval_surface_plan/,
  );
});

test("inventories every current-bank case and refuses unsupported installed runners", async () => {
  const bank = JSON.parse(
    fs.readFileSync(
      path.resolve(
        __dirname,
        "..",
        "..",
        "prompt-architecture",
        "evals",
        "prompt-bank.json",
      ),
      "utf8",
    ),
  );
  assert.equal(Object.hasOwn(bank, "familyCount"), false);
  assert.equal(Object.hasOwn(bank, "caseCount"), false);
  bank.familyCount = bank.families.length;
  bank.caseCount = bank.families.reduce(
    (count, family) => count + family.cases.length,
    0,
  );
  const catalog = validateEvalBank(bank);
  const unsupported = catalog.families.filter((family) =>
    ["main_compaction", "worker_source"].includes(family.runner));
  assert.ok(unsupported.length > 0);
  assert.equal(catalog.caseCount, bank.caseCount);
  assert.equal(catalog.caseIds.length, bank.caseCount);
  await assert.rejects(buildFamilyPlans({
    catalog, configuredRoutes: makeRoutesForCatalog(catalog), mainAgentId: MAIN_AGENT_ID,
  }), /family_installed_route_unavailable/);
});

test("partitions every supported current-bank case exactly once with complete hashes", async () => {
  const bank = JSON.parse(
    fs.readFileSync(
      path.resolve(
        __dirname,
        "..",
        "..",
        "prompt-architecture",
        "evals",
        "prompt-bank.json",
      ),
      "utf8",
    ),
  );
  assert.equal(Object.hasOwn(bank, "familyCount"), false);
  assert.equal(Object.hasOwn(bank, "caseCount"), false);
  bank.families = bank.families.filter((family) =>
    !["main_compaction", "worker_source"].includes(family.runner));
  bank.familyCount = bank.families.length;
  bank.caseCount = bank.families.reduce(
    (count, family) => count + family.cases.length,
    0,
  );
  const catalog = validateEvalBank(bank);
  const plans = await buildFamilyPlans({
    catalog,
    configuredRoutes: makeRoutesForCatalog(catalog),
    mainAgentId: MAIN_AGENT_ID,
  });
  const coverage = validatePlanCoverage(catalog, plans);
  const selectedCaseIds = plans.flatMap((plan) => plan.caseIds);
  const expectedPlanCount = new Set(
    catalog.families.flatMap((family) =>
      family.cases.map((testCase) => `${family.id}\u0000${testCase.surface}`),
    ),
  ).size;

  assert.equal(plans.length, expectedPlanCount);
  assert.equal(coverage.surfacePlanCount, expectedPlanCount);
  assert.equal(coverage.executedCaseCount, catalog.caseCount);
  assert.equal(coverage.uniqueExecutedCaseCount, catalog.caseCount);
  assert.deepEqual([...selectedCaseIds].sort(), [...catalog.caseIds].sort());
  assert.equal(new Set(selectedCaseIds).size, catalog.caseCount);
  assert.match(catalog.bankHash, /^[0-9a-f]{64}$/);
  assert.equal(catalog.caseSetHash, jsonHash([...selectedCaseIds].sort()));
  assert.match(coverage.planSetHash, /^[0-9a-f]{64}$/);
  for (const plan of plans) {
    const family = catalog.families.find((row) => row.id === plan.familyId);
    assert.ok(
      plan.caseIds.every(
        (caseId) =>
          family.cases.find((row) => row.id === caseId)?.surface ===
          plan.surface,
      ),
    );
  }
});

test("fails closed when an activation family declares an unsupported semantic judge", async () => {
  const bank = makeBank();
  bank.families[2].semanticJudge = true;
  const catalog = validateEvalBank(bank);

  await assert.rejects(
    () =>
      buildFamilyPlans({
        catalog,
        configuredRoutes: makeRoutes(),
        mainAgentId: MAIN_AGENT_ID,
      }),
    /family_installed_route_unavailable/,
  );
});

test("runs each family with the exact complete case list and writes only bounded aggregate reports", async () => {
  const { result, driver, privateReport, publicReport } =
    await executeFixture();

  assert.equal(result.status, "pass");
  assert.deepEqual(
    driver.postBodies.map((body) => ({
      family: body.family,
      surface: body.surface,
      caseIds: body.caseIds,
      maxCases: body.maxCases,
      live: body.live,
    })),
    makeBank().families.map((family) => ({
      family: family.id,
      surface: family.cases[0].surface,
      caseIds: family.cases.map((row) => row.id),
      maxCases: family.cases.length,
      live: true,
    })),
  );
  assert.equal(privateReport.candidateMode, "PRE-GATE / NOT READY");
  assert.equal(privateReport.runs.length, makeBank().familyCount);
  assert.deepEqual(
    privateReport.runs.map((row) => row.runId),
    [...driver.runs.keys()],
  );
  assert.equal(publicReport.candidateMode, "PRE-GATE / NOT READY");
  assert.equal(publicReport.releaseEligible, false);
  assert.equal(publicReport.counts.caseCount, makeBank().caseCount);
  assert.equal(publicReport.counts.surfacePlanCount, makeBank().familyCount);
  assert.equal(publicReport.counts.executedCaseCount, makeBank().caseCount);
  assert.equal(
    publicReport.counts.uniqueExecutedCaseCount,
    makeBank().caseCount,
  );
  assert.match(publicReport.hashes.candidateHash, /^[0-9a-f]{64}$/);
  assert.match(publicReport.hashes.planSetHash, /^[0-9a-f]{64}$/);
  const publicText = JSON.stringify(publicReport);
  for (const family of makeBank().families) {
    assert.equal(publicText.includes(family.id), false);
    for (const testCase of family.cases) {
      assert.equal(publicText.includes(testCase.id), false);
    }
  }
  assert.equal(publicText.includes(MAIN_AGENT_ID), false);
  assert.equal(publicText.includes("synthetic-main-model"), false);
});

test("runs every mixed-family subgroup on its exact surface and aggregates each case once", async () => {
  const bank = makeMixedSurfaceBank();
  const { driver, privateReport, publicReport } = await executeFixture({
    bank,
  });
  const mainBodies = driver.postBodies.filter(
    (body) => body.family === "synthetic_main_family",
  );

  assert.deepEqual(
    mainBodies.map((body) => ({
      surface: body.surface,
      caseIds: body.caseIds,
    })),
    [
      { surface: "web", caseIds: ["synthetic_main_case"] },
      { surface: "voice", caseIds: ["synthetic_voice_case"] },
      { surface: "telegram", caseIds: ["synthetic_telegram_case"] },
      {
        surface: "memory_hardening",
        caseIds: ["synthetic_memory_case"],
      },
    ],
  );
  assert.ok(
    driver.postBodies.every((body) => typeof body.surface === "string"),
  );
  assert.equal(privateReport.coverage.surfacePlanCount, 6);
  assert.equal(privateReport.coverage.executedCaseCount, bank.caseCount);
  assert.equal(privateReport.coverage.uniqueExecutedCaseCount, bank.caseCount);
  assert.equal(publicReport.counts.surfacePlanCount, 6);
  assert.equal(publicReport.counts.executedCaseCount, bank.caseCount);
  assert.equal(publicReport.counts.uniqueExecutedCaseCount, bank.caseCount);
  assert.equal(
    new Set(privateReport.runs.flatMap((run) => run.caseIds)).size,
    bank.caseCount,
  );
});

test("requires the exact installed native surface and backend-verified canonical artifact", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw047-native-"));
  try {
    const family = {
      id: "synthetic_native_family",
      semanticJudge: true,
      cases: [{ id: "synthetic_native_case", surface: "voice" }],
    };
    const bank = {
      version: 7,
      scope: "public-safe native fixture",
      familyCount: 1,
      caseCount: 1,
      families: [family],
    };
    const catalog = validateEvalBank(bank);
    const configuredRoute = {
      kind: "main",
      family: family.id,
      provider: "synthetic-native-provider",
      model: "synthetic-native-model",
      effort: "medium",
      fallbacks: [],
    };
    const [plan] = await buildFamilyPlans({
      catalog,
      configuredRoutes: { [family.id]: configuredRoute },
      mainAgentId: MAIN_AGENT_ID,
    });
    const artifactBytes = '{"schemaVersion":1,"native":true}\n';
    const run = makeRun({
      family,
      route: configuredRoute,
      runIndex: 0,
      artifactBytes,
    });
    run.surface = "voice";
    run.runnerSummary.status =
      "completed_with_semantic_native_surface_evidence";
    run.executionRoute.artifactSha256 = hash(artifactBytes, 64);
    run.executionRoute.caseEvidence[0].surface = "voice";
    run.executionRoute.caseEvidence[0].completionSurface = "voice";
    run.executionRoute.caseEvidence[0].completionExpected = true;
    const runDir = path.join(root, "eval-runs", run.id);
    fs.mkdirSync(runDir, { recursive: true });
    fs.writeFileSync(
      path.join(runDir, "native-surface-playwright-qa.json"),
      artifactBytes,
    );

    const validated = validateRun({
      run,
      plan,
      candidate: { sourceHash: SOURCE_HASH },
      privateRoot: root,
      startedAtMs: NOW_MS,
      nowMs: NOW_MS + 60_000,
    });
    assert.equal(validated.nativeSurfaceHash, hash("voice", 64));

    const missingSurface = clone(run);
    delete missingSurface.surface;
    assert.throws(
      () =>
        validateRun({
          run: missingSurface,
          plan,
          candidate: { sourceHash: SOURCE_HASH },
          privateRoot: root,
          startedAtMs: NOW_MS,
          nowMs: NOW_MS + 60_000,
        }),
      /execution_surface_mismatch/,
    );

    const unverified = clone(run);
    unverified.executionRoute.status = "unverified";
    assert.throws(
      () =>
        validateRun({
          run: unverified,
          plan,
          candidate: { sourceHash: SOURCE_HASH },
          privateRoot: root,
          startedAtMs: NOW_MS,
          nowMs: NOW_MS + 60_000,
        }),
      /backend_strict_artifact_verification_missing/,
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("rejects bank drift after the family runs", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        bankRead(readNumber, bank) {
          if (readNumber === 1) return bank;
          bank.families[0].cases.push({
            id: "synthetic_drifted_case",
            surface: "web",
          });
          bank.caseCount += 1;
          return bank;
        },
      }),
    /installed_eval_bank_drift/,
  );
});

test("rejects configured owner or model route drift after the family runs", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        routeRead({ familyId, readNumber, route }) {
          if (familyId === "synthetic_main_family" && readNumber > 1) {
            route.model = "synthetic-drifted-model";
          }
          return route;
        },
      }),
    /installed_candidate_route_drift/,
  );
});

test("rejects route drift after every mixed-surface subgroup run", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        bank: makeMixedSurfaceBank(),
        routeRead({ familyId, readNumber, route }) {
          if (familyId === "synthetic_main_family" && readNumber > 1) {
            route.provider = "synthetic-drifted-provider";
          }
          return route;
        },
      }),
    /installed_candidate_route_drift/,
  );
});

test("rejects a forged passing activation summary when canonical decisions are incomplete", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id === "synthetic_activation_family") {
            artifact.results.pop();
          }
          return artifact;
        },
      }),
    /activation_canonical_decision_coverage_incomplete/,
  );
});

test("rejects the wrong specialist identity or configured model", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_specialist_family") {
            run.executionRoute.configuredModel = "synthetic-wrong-model";
            run.executionRoute.caseEvidence[0].agentIdHash = hash(
              "agent_wrong_specialist",
            );
          }
          return run;
        },
      }),
    /configured_execution_route_mismatch|execution_agent_identity_mismatch/,
  );
});

test("rejects a specialist run that self-asserts a different execution target", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_specialist_family") {
            run.executionTarget.agentId = "agent_wrong_specialist";
          }
          return run;
        },
      }),
    /execution_agent_identity_mismatch/,
  );
});

for (const [label, mutate] of [
  ["nonzero return code", (run) => (run.returnCode = 1)],
  ["selected ID drift", (run) => (run.selectedCaseIds = ["wrong_case"])],
  ["result count drift", (run) => (run.resultCount += 1)],
]) {
  test(`rejects ${label} even when the run summary claims success`, async () => {
    await assert.rejects(
      () =>
        executeFixture({
          runMutator({ run, family }) {
            if (family.id === "synthetic_main_family") mutate(run);
            return run;
          },
        }),
      /eval_run_selection_or_candidate_mismatch|eval_result_count_mismatch/,
    );
  });
}

test("rejects a required semantic judge that is missing from summary and case evidence", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_main_family") {
            delete run.runnerSummary.semanticJudgedCount;
            run.executionRoute.caseEvidence[0].semanticJudged = false;
            run.executionRoute.caseEvidence[0].semanticPassed = false;
          }
          return run;
        },
      }),
    /semantic_judge_evidence_missing/,
  );
});

test("rejects a missing activation target route", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_activation_family") {
            run.executionRoute.routes.pop();
          }
          return run;
        },
      }),
    /activation_target_route_coverage_incomplete/,
  );
});

test("rejects a missing activation decision", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_activation_family") {
            run.executionRoute.caseEvidence.pop();
          }
          return run;
        },
      }),
    /activation_public_decision_coverage_incomplete/,
  );
});

test("rejects an undeclared activation fallback even when the summary says pass", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id !== "synthetic_activation_family") return artifact;
          const row = artifact.results[0];
          row.providerUsed = "synthetic-undeclared-provider";
          row.modelUsed = "synthetic-undeclared-model";
          row.effortUsed = "high";
          row.effectiveProvider = row.providerUsed;
          row.effectiveModel = row.modelUsed;
          row.effectiveEffort = row.effortUsed;
          row.fallbackReason = "provider_timeout";
          row.providerAttempts = [
            {
              provider: "synthetic-required-provider",
              model: "synthetic-required-model",
              effort: "low",
              source: "primary",
              status: "failed",
              fallbackReason: "none",
              error: { class: "provider_timeout" },
              shouldActivate: null,
            },
            {
              provider: row.providerUsed,
              model: row.modelUsed,
              effort: row.effortUsed,
              source: "fallback",
              status: "completed",
              fallbackReason: row.fallbackReason,
              shouldActivate: row.actual,
            },
          ];
          return artifact;
        },
        runMutator({ run, family }) {
          if (family.id === "synthetic_activation_family") {
            const route = run.executionRoute.routes[0];
            route.effectiveProvider = "synthetic-undeclared-provider";
            route.effectiveModel = "synthetic-undeclared-model";
            route.effectiveEffort = "high";
            route.fallbackUsed = true;
            route.fallbackAuthorized = true;
            route.fallbackReason = "provider_timeout";
            const evidence = run.executionRoute.caseEvidence[0];
            evidence.effectiveProvider = route.effectiveProvider;
            evidence.effectiveModel = route.effectiveModel;
            evidence.effectiveEffort = route.effectiveEffort;
            evidence.fallbackReason = route.fallbackReason;
            evidence.primaryFailureVerified = true;
          }
          return run;
        },
      }),
    /activation_execution_route_undeclared/,
  );
});

test("rejects a successful receipt missing requested and effective effort", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id !== "synthetic_activation_family") return artifact;
          const row = artifact.results[0];
          delete row.requestedEffort;
          delete row.effectiveEffort;
          delete row.effortUsed;
          delete row.providerAttempts[0].effort;
          return artifact;
        },
      }),
    /execution_effort_lineage_missing/,
  );
});

test("rejects a successful receipt with requested and effective effort mismatch", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id !== "synthetic_activation_family") return artifact;
          const row = artifact.results[0];
          row.effectiveEffort = "high";
          row.effortUsed = "high";
          row.providerAttempts[0].effort = "high";
          return artifact;
        },
      }),
    /activation_execution_route_undeclared/,
  );
});

test("rejects an undeclared same-provider/model effort fallback", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id !== "synthetic_activation_family") return artifact;
          const row = artifact.results[0];
          row.effectiveEffort = "xhigh";
          row.effortUsed = "xhigh";
          row.providerAttempts[0].effort = "xhigh";
          row.providerAttempts[0].source = "fallback";
          row.providerAttempts[0].fallbackReason = "provider_timeout";
          row.fallbackReason = "provider_timeout";
          return artifact;
        },
      }),
    /activation_execution_route_undeclared/,
  );
});

test("rejects a declared fallback missing its typed fallback reason", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        artifactMutator({ artifact, family }) {
          if (family.id !== "synthetic_activation_family") return artifact;
          const row = artifact.results[0];
          row.providerUsed = "synthetic-declared-fallback";
          row.modelUsed = "synthetic-fallback-model";
          row.effortUsed = "high";
          row.effectiveProvider = row.providerUsed;
          row.effectiveModel = row.modelUsed;
          row.effectiveEffort = row.effortUsed;
          delete row.fallbackReason;
          row.providerAttempts = [
            {
              provider: "synthetic-required-provider",
              model: "synthetic-required-model",
              effort: "low",
              source: "primary",
              status: "failed",
              fallbackReason: "none",
              error: { class: "provider_timeout" },
              shouldActivate: null,
            },
            {
              provider: row.providerUsed,
              model: row.modelUsed,
              effort: row.effortUsed,
              source: "fallback",
              status: "completed",
              shouldActivate: row.actual,
            },
          ];
          return artifact;
        },
        runMutator({ run, family }) {
          if (family.id === "synthetic_activation_family") {
            const route = run.executionRoute.routes[0];
            route.effectiveProvider = "synthetic-declared-fallback";
            route.effectiveModel = "synthetic-fallback-model";
            route.effectiveEffort = "high";
            route.fallbackUsed = true;
            route.fallbackAuthorized = true;
            delete route.fallbackReason;
            const evidence = run.executionRoute.caseEvidence[0];
            evidence.effectiveProvider = route.effectiveProvider;
            evidence.effectiveModel = route.effectiveModel;
            evidence.effectiveEffort = route.effectiveEffort;
            delete evidence.fallbackReason;
            evidence.primaryFailureVerified = true;
          }
          return run;
        },
      }),
    /fallback_reason_missing/,
  );
});

test("rejects a stale run even when its route and summary claim success", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_main_family") {
            run.createdAt = "2026-08-24T12:00:00.000Z";
          }
          return run;
        },
      }),
    /stale_eval_run/,
  );
});

test("rejects private body or credential fields in installed run output", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_main_family") {
            run.providerResponseBody = {
              authorization: "synthetic-public-safe-placeholder",
            };
          }
          return run;
        },
      }),
    /private_eval_output_exposed/,
  );
});

test("rejects an unregistered completion-text field even without a credential marker", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        runMutator({ run, family }) {
          if (family.id === "synthetic_main_family") {
            run.completionText = "Synthetic private completion content.";
          }
          return run;
        },
      }),
    /private_eval_output_exposed/,
  );
});

test("fails when independent readback cannot recover every exact run", async () => {
  await assert.rejects(
    () => executeFixture({ historyMissing: true }),
    /eval_history_readback_missing/,
  );
});

test("fails replay when persisted lineage loses effective effort", async () => {
  await assert.rejects(
    () =>
      executeFixture({
        readbackMutator({ run }) {
          if (run.family === "synthetic_main_family") {
            delete run.executionRoute.effectiveEffort;
          }
          return run;
        },
      }),
    /eval_history_readback_mismatch/,
  );
});

function writeCleanupFixture(root) {
  const evidenceRoot = path.join(root, "evidence");
  const privateRoot = path.join(root, "private-workbench");
  const runId = "20260826T120001Z-000000000001";
  const siblingId = "20260826T120002Z-000000000002";
  const runDir = path.join(privateRoot, "eval-runs", runId);
  const siblingDir = path.join(privateRoot, "eval-runs", siblingId);
  fs.mkdirSync(runDir, { recursive: true });
  fs.mkdirSync(siblingDir, { recursive: true });
  const artifact = '{"synthetic":true}\n';
  const runRecord = {
    id: runId,
    family: "synthetic_main_family",
    candidateSourceHash: SOURCE_HASH,
    selectedCaseIds: ["synthetic_main_case"],
  };
  fs.writeFileSync(path.join(runDir, "exact-model-eval.json"), artifact);
  fs.writeFileSync(
    path.join(runDir, "workbench-run.json"),
    `${JSON.stringify(runRecord)}\n`,
  );
  fs.writeFileSync(path.join(siblingDir, "keep.json"), "{}\n");
  fs.mkdirSync(evidenceRoot, { recursive: true });
  const aggregate = {
    schemaVersion: 1,
    runner: "PW-047",
    candidate: {
      sourceHash: SOURCE_HASH,
      candidateHash: "a".repeat(64),
    },
    runs: [
      {
        runId,
        familyId: "synthetic_main_family",
        caseIdsHash: jsonHash(["synthetic_main_case"]),
        canonicalArtifactName: "exact-model-eval.json",
        canonicalArtifactSha256: hash(artifact, 64),
      },
    ],
  };
  const manifestPath = path.join(evidenceRoot, "pw-047.private.json");
  fs.writeFileSync(manifestPath, `${JSON.stringify(aggregate)}\n`);
  return { evidenceRoot, privateRoot, manifestPath, runDir, siblingDir };
}

test("cleanup-only removes only exact manifest-bound runner artifacts", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw047-cleanup-"));
  try {
    const fixture = writeCleanupFixture(root);
    const result = cleanupOwnedArtifacts({
      manifestPath: fixture.manifestPath,
      evidenceRoot: fixture.evidenceRoot,
      privateRoot: fixture.privateRoot,
    });
    assert.equal(result.removedCount, 1);
    assert.equal(fs.existsSync(fixture.runDir), false);
    assert.equal(fs.existsSync(fixture.siblingDir), true);
    assert.equal(fs.existsSync(fixture.manifestPath), true);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("cleanup-only refuses path traversal, mismatched ownership, and sibling deletion", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "pw047-cleanup-"));
  try {
    const fixture = writeCleanupFixture(root);
    const aggregate = JSON.parse(fs.readFileSync(fixture.manifestPath, "utf8"));
    aggregate.runs[0].runId = "../synthetic-sibling";
    fs.writeFileSync(fixture.manifestPath, `${JSON.stringify(aggregate)}\n`);
    assert.throws(
      () =>
        cleanupOwnedArtifacts({
          manifestPath: fixture.manifestPath,
          evidenceRoot: fixture.evidenceRoot,
          privateRoot: fixture.privateRoot,
        }),
      /owned_cleanup_scope_invalid/,
    );
    assert.equal(fs.existsSync(fixture.runDir), true);
    assert.equal(fs.existsSync(fixture.siblingDir), true);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

for (const runner of ["main_compaction", "worker_source"]) {
  test(`specialized ${runner} inventory cannot fall through to Main acceptance`, async () => {
    const bank = makeBank();
    bank.families = [{ ...bank.families[0], runner }];
    bank.familyCount = 1;
    bank.caseCount = 1;
    const catalog = validateEvalBank(bank);
    assert.equal(catalog.families[0].runner, runner);
    await assert.rejects(buildFamilyPlans({ catalog, configuredRoutes: {}, mainAgentId: MAIN_AGENT_ID }),
      /family_installed_route_unavailable/);
  });
}
