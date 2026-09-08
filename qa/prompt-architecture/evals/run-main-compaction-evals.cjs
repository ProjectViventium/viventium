#!/usr/bin/env node
"use strict";

// Bounded Prompt Workbench family executor. Run under the isolated dev-env runner.
// It exercises the production compactor assembly, not a normal-chat approximation.
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const Module = require("module");
const root = path.resolve(__dirname, "../../..");
const lc = path.join(root, "viventium_v0_4/LibreChat");
const requireLC = Module.createRequire(path.join(lc, "package.json"));
const cliOptions = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    const index = arg.indexOf("=");
    return [arg.slice(2, index), arg.slice(index + 1)];
  }),
);
const sha = (value) => crypto.createHash("sha256").update(value).digest("hex");

const compactorOwner =
  "api/server/services/viventium/ViventiumMainCompactionService.js";
const continuityOwner =
  "api/server/services/viventium/ViventiumMainContinuityService.js";
const registryOwner = "api/server/services/viventium/promptRegistry.js";

function loadSourceModule(source, owner, overrides = {}) {
  const filename = path.join(lc, owner);
  const module = new Module(filename, require.main);
  module.filename = filename;
  module.paths = Module._nodeModulePaths(path.dirname(filename));
  const nativeRequire = module.require.bind(module);
  module.require = (name) =>
    Object.hasOwn(overrides, name) ? overrides[name] : nativeRequire(name);
  module._compile(source, filename);
  return module.exports;
}

function loadCompactor(source, overrides) {
  // Export the existing private invocation for evaluation; its implementation is unmodified.
  return loadSourceModule(
    source + "\nmodule.exports.executeForEvaluation = defaultExecuteCompactor;",
    compactorOwner,
    overrides,
  );
}

function readSnapshot(snapshotDirectory) {
  const directory = path.resolve(snapshotDirectory);
  const manifestBytes = fs.readFileSync(path.join(directory, "manifest.json"));
  const manifest = JSON.parse(manifestBytes);
  const read = (relative) => {
    if (!Object.hasOwn(manifest, relative))
      throw new Error(`snapshot_file_unrecorded:${relative}`);
    const filename = path.resolve(directory, relative);
    if (!filename.startsWith(directory + path.sep))
      throw new Error("snapshot_path_outside_root");
    const bytes = fs.readFileSync(filename);
    if (sha(bytes) !== manifest[relative])
      throw new Error(`snapshot_hash_mismatch:${relative}`);
    return bytes;
  };
  // Validate the complete captured set before any DB/model work, including compiled chunks.
  for (const relative of Object.keys(manifest)) read(relative);
  return { directory, manifest, manifestHash: sha(manifestBytes), read };
}

function loadSnapshotPackages(snapshot) {
  const modules = new Map();
  const load = (relative) => {
    if (modules.has(relative)) return modules.get(relative).exports;
    const filename = path.join(snapshot.directory, relative);
    const module = new Module(filename, require.main);
    module.filename = filename;
    module.paths = Module._nodeModulePaths(path.join(lc, "packages/api"));
    modules.set(relative, module);
    module.require = (name) => {
      if (name === "@librechat/data-schemas")
        return load("compiled/data-schemas/dist/index.cjs");
      if (name.startsWith(".")) {
        const next = path.posix.normalize(
          path.posix.join(path.posix.dirname(relative), name),
        );
        return load(next);
      }
      return requireLC(name);
    };
    module._compile(snapshot.read(relative).toString("utf8"), filename);
    return module.exports;
  };
  return {
    api: load("compiled/api/dist/index.js"),
    dataSchemas: load("compiled/data-schemas/dist/index.cjs"),
  };
}

function selectedPromptRegistry(registry, bundlePath) {
  // Rendering is synchronous in the existing registry; only this isolated executor selects it.
  return {
    getRequiredPromptText(...args) {
      const previous = process.env.VIVENTIUM_PROMPT_BUNDLE_PATH;
      process.env.VIVENTIUM_PROMPT_BUNDLE_PATH = bundlePath;
      try {
        return registry.getRequiredPromptText(...args);
      } finally {
        if (previous === undefined)
          delete process.env.VIVENTIUM_PROMPT_BUNDLE_PATH;
        else process.env.VIVENTIUM_PROMPT_BUNDLE_PATH = previous;
      }
    },
  };
}

function caseEvidence(testCase, family) {
  const fixture = testCase.fixture?.compaction;
  const source = family.sources?.[fixture?.sourceId];
  if (!source || !["baseline", "candidate", "review"].includes(fixture?.mode)) {
    throw new Error("invalid_compaction_fixture");
  }
  return {
    version: 1,
    sourceDigest: source.sourceDigest || sha(JSON.stringify(source)),
    acceptedOlderTurns: source.sourceTurns,
    previousSemanticCompaction: source.previousSemanticCompaction,
    ...(fixture.candidate ? { candidate: fixture.candidate } : {}),
    ...(fixture.priorRejection ? { priorRejection: fixture.priorRejection } : {}),
  };
}

async function run(options = cliOptions, qaAuth = null) {
  for (const key of ["bank", "output", "api"]) {
    if (!options[key]) throw new Error(`missing_${key}`);
  }
  const variant = options.variant || "proposed";
  if (!["baseline", "proposed"].includes(variant))
    throw new Error("invalid_compaction_variant");
  if (variant === "baseline" && !options.snapshot)
    throw new Error("baseline_snapshot_required");
  const snapshot =
    variant === "baseline" ? readSnapshot(options.snapshot) : null;
  // The isolated runner supplies these exact generated bindings; do not load personal env files.
  if (
    !process.env.CONFIG_PATH ||
    !process.env.VIVENTIUM_PROMPT_BUNDLE_PATH ||
    !process.env.MONGO_URI
  ) {
    throw new Error("isolated_runtime_environment_required");
  }
  let login;
  if (qaAuth?.ok && qaAuth.token && qaAuth.userId) {
    login = { token: qaAuth.token, user: { id: qaAuth.userId, role: "USER" } };
  } else {
    if (!options.credentials) throw new Error("missing_credentials");
    const credentials = JSON.parse(
      fs.readFileSync(options.credentials, "utf8"),
    );
    if (!String(credentials.email).endsWith(".invalid"))
      throw new Error("synthetic_invalid_email_required");
    const response = await fetch(`${options.api}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    login = await response.json();
    if (
      !response.ok ||
      !login.token ||
      !login.user?.id ||
      login.user.role !== "USER" ||
      login.user.email !== credentials.email
    ) {
      throw new Error("synthetic_qa_login_failed");
    }
  }
  const runId = `compaction-eval-${crypto.randomUUID()}`;
  const bank = JSON.parse(fs.readFileSync(options.bank, "utf8"));
  const family = bank.families.find(
    (item) => item.id === "main_compaction_fidelity",
  );
  const allCases = family?.cases;
  if (!allCases) throw new Error("compaction_family_missing");
  const selected = allCases
    .filter(
      (testCase) =>
        !options.case || options.case.split(",").includes(testCase.id),
    )
    .slice(0, Number(options.max || allCases.length));
  if (!selected.length) throw new Error("compaction_selection_empty");
  fs.mkdirSync(path.dirname(options.output), { recursive: true });
  requireLC("module-alias")({ base: path.join(lc, "api") });
  for (const patch of [
    "anthropicOAuthPatch",
    "anthropicThinkingPatch",
    "openaiResponsesOutputPatch",
    "agentSchemaToolBindingPatch",
  ]) {
    require(path.join(lc, "api/server/services/viventium", patch));
  }
  const { connectDb } = require(path.join(lc, "api/db"));
  const mongoose = requireLC("mongoose");
  await connectDb();
  const { getAppConfig } = require(path.join(lc, "api/server/services/Config"));
  const config = await getAppConfig();
  const { User, Agent } = require(path.join(lc, "api/db/models"));
  const user = await User.findById(login.user.id).lean();
  if (!user || user.role !== "USER" || !String(user.email).endsWith(".invalid"))
    throw new Error("synthetic_user_context_required");
  login.user = { ...user, id: String(user._id) };
  const sourceAgent = options.route
    ? JSON.parse(fs.readFileSync(options.route, "utf8"))
    : await Agent.findOne({ id: options.agentId }).lean();
  if (!sourceAgent?.provider || !sourceAgent?.model)
    throw new Error("configured_main_route_unavailable");
  const route = Object.fromEntries(
    [
      "provider",
      "model",
      "model_parameters",
      "fallback_llm_provider",
      "fallback_llm_model",
      "fallback_llm_model_parameters",
    ]
      .filter((key) => sourceAgent[key] != null)
      .map((key) => [key, sourceAgent[key]]),
  );
  const req = {
    body: {},
    user: login.user,
    config,
    headers: { authorization: `Bearer ${login.token}` },
  };
  req.get = (name) => req.headers[String(name).toLowerCase()];
  const source = snapshot
    ? snapshot.read(`source/${compactorOwner}`).toString("utf8")
    : fs.readFileSync(path.join(lc, compactorOwner), "utf8");
  const bundlePath = snapshot
    ? path.join(snapshot.directory, "compiled-prompt-bundle.json")
    : process.env.VIVENTIUM_PROMPT_BUNDLE_PATH;
  const packages = snapshot ? loadSnapshotPackages(snapshot) : null;
  const background = require(
    path.join(lc, "api/server/services/BackgroundCortexService"),
  );
  const continuity = snapshot
    ? loadSourceModule(
        snapshot.read(`source/${continuityOwner}`).toString("utf8"),
        continuityOwner,
        {
          "@librechat/api": packages.api,
          "@librechat/data-schemas": packages.dataSchemas,
          "~/models": packages.dataSchemas.createMethods(mongoose),
        },
      )
    : require(path.join(lc, continuityOwner));
  const registry = snapshot
    ? loadSourceModule(
        snapshot.read(`source/${registryOwner}`).toString("utf8"),
        registryOwner,
        { "@librechat/data-schemas": packages.dataSchemas },
      )
    : require(path.join(lc, registryOwner));
  const executor = loadCompactor(source, {
    "./promptRegistry": selectedPromptRegistry(registry, bundlePath),
    "./ViventiumMainContinuityService": continuity,
    ...(packages
      ? {
          "@librechat/api": packages.api,
          "@librechat/data-schemas": packages.dataSchemas,
        }
      : {}),
  });
  const { ViventiumMainContinuityState, Message, Conversation } = require(
    path.join(lc, "api/db/models"),
  );
  const originalExecute = background.executeCortex;
  const results = [];
  const httpFailures = [];
  let currentCaseId = "";
  const originalFetch = globalThis.fetch;
  const numericFields = (value) =>
    Object.fromEntries(
      Object.entries(value || {}).filter(
        ([, number]) => typeof number === "number" && Number.isFinite(number),
      ),
    );
  globalThis.fetch = async (...args) => {
    const response = await originalFetch(...args);
    if (!response.ok) {
      let body = {};
      try {
        body = await response.clone().json();
      } catch {
        /* Non-JSON failure stays distinct. */
      }
      const detail =
        body.detail && typeof body.detail === "object"
          ? body.detail
          : body.error || {};
      httpFailures.push({
        caseId: currentCaseId,
        status: response.status,
        code: String(detail.code || "").slice(0, 80),
        capacityClass: String(detail.capacityClass || "").slice(0, 80),
        dimension: String(detail.dimension || "").slice(0, 80),
        available: numericFields(detail.available),
        required: numericFields(detail.required),
        shortage: numericFields(detail.shortage),
        reservation: numericFields(detail.reservation),
        retryAfter: Number(response.headers.get("retry-after")) || null,
      });
    }
    return response;
  };
  let currentCalls = [];
  let afterApprovedReview = null;
  background.executeCortex = async (invocation) => {
    const startedAt = Date.now();
    const record = {
      runId: invocation.runId,
      contextMode: invocation.contextMode,
      instructionsHash: sha(invocation.agent.instructions || ""),
      messageHashes: invocation.messages.map((message) =>
        sha(String(message.content)),
      ),
      requestedRoute: {
        provider: invocation.agent.provider,
        model: invocation.agent.model,
        parameters: invocation.agent.model_parameters,
        fallbackProvider: invocation.agent.fallback_llm_provider,
        fallbackModel: invocation.agent.fallback_llm_model,
        fallbackParameters: invocation.agent.fallback_llm_model_parameters,
      },
      toolCount: invocation.agent.tools.length,
      completedResultPolicy: invocation.completedResultPolicy,
      evidence: invocation.messages.map((message) => {
        const content = String(message.content);
        const match = content.match(
          /<untrusted_(?:conversation_data|compaction_evidence)_v1>\s*([\s\S]*?)\s*<\/untrusted_(?:conversation_data|compaction_evidence)_v1>/,
        );
        if (!match) return null;
        try {
          const payload = JSON.parse(match[1]);
          return {
            sourceDigest: payload.sourceDigest,
            sourceTurnCount: payload.acceptedOlderTurns?.length,
            sourceBytes: Buffer.byteLength(
              JSON.stringify(payload.acceptedOlderTurns || []),
              "utf8",
            ),
          };
        } catch {
          return null;
        }
      }),
    };
    currentCalls.push(record);
    try {
      const result = await originalExecute(invocation);
      record.result = result;
      if (
        afterApprovedReview &&
        executor.parseSemanticCompactionOutput(result.insight)?.approved ===
          true
      ) {
        const mutateSource = afterApprovedReview;
        afterApprovedReview = null;
        await mutateSource();
      }
      return result;
    } finally {
      record.durationMs = Date.now() - startedAt;
    }
  };
  const checkpoint = () =>
    fs.writeFileSync(
      options.output,
      JSON.stringify(
        {
          runId,
          bankHash: sha(fs.readFileSync(options.bank)),
          routeHash: sha(JSON.stringify(route)),
          artifactVariant: variant,
          snapshotManifestHash: snapshot?.manifestHash || null,
          selectedSourceHash: sha(source),
          selectedContinuitySourceHash: sha(
            snapshot
              ? snapshot.read(`source/${continuityOwner}`)
              : fs.readFileSync(path.join(lc, continuityOwner)),
          ),
          compiledApiEntryHash: sha(
            snapshot
              ? snapshot.read("compiled/api/dist/index.js")
              : fs.readFileSync(path.join(lc, "packages/api/dist/index.js")),
          ),
          compiledDataSchemasEntryHash: sha(
            snapshot
              ? snapshot.read("compiled/data-schemas/dist/index.cjs")
              : fs.readFileSync(
                  path.join(lc, "packages/data-schemas/dist/index.cjs"),
                ),
          ),
          sharedExecutionSourceHash: sha(
            fs.readFileSync(
              path.join(lc, "api/server/services/BackgroundCortexService.js"),
            ),
          ),
          compiledPromptBundleHash: sha(fs.readFileSync(bundlePath)),
          artifactScope:
            "Selected continuity/compactor/prompt artifacts; shared current executeCortex, config, third-party dependencies and Mongo model schema.",
          results,
          httpFailures,
          summary: {
            status: "partial_model_evidence",
            resultCount: results.length,
            completedCount: results.filter(
              (item) => item.status === "completed",
            ).length,
            failedCount: results.filter((item) => item.status !== "completed")
              .length,
          },
          status:
            results.length === selected.length
              ? "completed_calls_only"
              : "partial",
          humanCalibration: "not recorded",
          realUserQa: "not performed by this executor",
        },
        null,
        2,
      ),
      { mode: 0o600 },
    );
  const ledgerIds = [];
  const sourceConversationIds = [];
  try {
    for (const testCase of selected) {
      currentCaseId = testCase.id;
      currentCalls = [];
      afterApprovedReview = null;
      const startedAt = Date.now();
      const evidence = caseEvidence(testCase, family);
      const claim = {
        sourceDigest: evidence.sourceDigest,
        sourceTurns: evidence.acceptedOlderTurns,
        previousSemanticCompaction: evidence.previousSemanticCompaction,
        domainEpochKey: sha(`${runId}:${testCase.id}`),
      };
      const result = {
        caseId: testCase.id,
        calls: currentCalls,
        fixtureSourceDigest: claim.sourceDigest,
      };
      results.push(result);
      try {
        // Fixture mode selects generation, review or persisted promotion; the run's explicit
        // artifact variant selects the baseline/proposed implementation for every selected case.
        if (testCase.fixture.compaction.mode === "candidate") {
          const agentId = `${runId}-${testCase.id}`;
          const identity = {
            ownerId: login.user.id,
            agentId,
            stableAuthoritySha256: sha(JSON.stringify(route)),
          };
          ledgerIds.push(agentId);
          const conversationId = `${runId}-${testCase.id}`;
          sourceConversationIds.push(conversationId);
          await Conversation.create({
            user: login.user.id,
            conversationId,
            agent_id: agentId,
            endpoint: "agents",
            title: "Synthetic compaction evaluation",
          });
          const legacyFixture = testCase.fixture.compaction.legacy === true;
          const persistSourceTurn = async (turn, index, accept = true) => {
            const userMessageId = `${conversationId}-user-${index}`;
            const assistantMessageId = `${conversationId}-answer-${index}`;
            const interactionContext = {
              logical_turn_id: turn.logicalTurnId,
              revision: turn.revision,
            };
            await Message.create({
              user: login.user.id,
              conversationId,
              messageId: userMessageId,
              isCreatedByUser: true,
              text: turn.userText,
            });
            await Message.create({
              user: login.user.id,
              conversationId,
              messageId: assistantMessageId,
              parentMessageId: userMessageId,
              isCreatedByUser: false,
              text: turn.assistantText,
              metadata: {
                viventium: {
                  interactionContext,
                  mainContext: {
                    agentId,
                    stableAuthoritySha256: identity.stableAuthoritySha256,
                  },
                },
              },
              content: (turn.toolPairs || []).map((pair) => ({
                type: "tool_call",
                tool_call: {
                  id: pair.callId,
                  name: pair.toolName,
                  output: pair.outcome,
                },
              })),
            });
            if (accept) {
              const accepted =
                await continuity.commitAcceptedMainTurnFromPresentation({
                  userId: login.user.id,
                  responseMessageId: assistantMessageId,
                  interactionContext,
                });
              if (accepted.status !== "committed")
                throw new Error(`source_acceptance_${accepted.status}`);
            }
            return {
              ...turn,
              conversationId,
              userMessageId,
              assistantMessageId,
              committedAt: new Date(),
              userText: "Legacy native source reference.",
              assistantText: "Legacy native source reference.",
            };
          };
          const legacyReferences = [];
          for (let index = 0; index < claim.sourceTurns.length; index += 1)
            legacyReferences.push(
              await persistSourceTurn(
                claim.sourceTurns[index],
                index,
                !legacyFixture,
              ),
            );
          let legacyRecordId, legacyRecordDigest;
          const legacyProjection = {
            acceptedTurns: 1,
            pendingCompactionTurns: 1,
            semanticCompaction: 1,
          };
          if (legacyFixture) {
            const legacyRecord = await ViventiumMainContinuityState.create({
              ...identity,
              continuityDomainId: continuity.continuityDomainId(
                identity.ownerId,
                agentId,
              ),
              domainEpochKey: sha(`${runId}:${testCase.id}:legacy-fixture`),
              contextEpoch: identity.stableAuthoritySha256,
              recordKind: "legacy",
              acceptedTurns: [],
              pendingCompactionTurns: legacyReferences,
              semanticCompaction: claim.previousSemanticCompaction || null,
            });
            legacyRecordId = legacyRecord._id;
            legacyRecordDigest = sha(
              JSON.stringify(
                await ViventiumMainContinuityState.findById(legacyRecordId)
                  .select(legacyProjection)
                  .lean(),
              ),
            );
            result.legacyFixture = {
              sourceCount: legacyReferences.length,
              sourceBytes: Buffer.byteLength(
                JSON.stringify(claim.sourceTurns),
                "utf8",
              ),
            };
          }
          for (let index = 0; index < 3; index += 1) {
            await persistSourceTurn(
              {
                logicalTurnId: `recent-${index}`,
                revision: 1,
                userText: "A separate recent placeholder.",
                assistantText: "Acknowledged.",
              },
              claim.sourceTurns.length + index,
            );
          }
          const sourceMutation =
            testCase.fixture.compaction.afterApprovedReview;
          if (sourceMutation) {
            if (!["edit", "delete"].includes(sourceMutation))
              throw new Error("invalid_source_mutation_fixture");
            afterApprovedReview = async () => {
              const query = {
                user: login.user.id,
                conversationId,
                messageId: `${conversationId}-user-0`,
              };
              const mutation =
                sourceMutation === "delete"
                  ? await Message.deleteOne(query)
                  : await Message.updateOne(query, {
                      $set: {
                        text: "Newer accepted source: keep all work paused pending revised instructions.",
                      },
                    });
              result.sourceMutation = {
                kind: sourceMutation,
                affectedCount:
                  mutation.deletedCount || mutation.modifiedCount || 0,
              };
            };
          }
          if (claim.previousSemanticCompaction && !legacyFixture) {
            // A prior-summary fixture is supplied evidence, not a model-created history claim.
            const initial =
              await continuity.claimAcceptedMainCompaction(identity);
            if (initial.status !== "claimed")
              throw new Error(`prior_fixture_claim_${initial.status}`);
            await continuity.rejectAcceptedMainCompaction({
              ...identity,
              leaseId: initial.leaseId,
              reason: "fixture_preparation",
            });
            const prior = {
              ...claim.previousSemanticCompaction,
              sourceDigest: sha(
                JSON.stringify(claim.previousSemanticCompaction),
              ),
              generatedAt: new Date(),
            };
            const seeded = await ViventiumMainContinuityState.updateOne(
              {
                ownerId: login.user.id,
                agentId,
                recordKind: "epoch",
                contextEpoch: identity.stableAuthoritySha256,
              },
              { $set: { semanticCompaction: prior } },
            );
            if (seeded.modifiedCount !== 1)
              throw new Error("prior_fixture_not_persisted");
            result.fixturePriorStateHash = sha(JSON.stringify(prior));
          }
          result.compactionSteps = [];
          let persisted;
          // Each successful prefix can expose the next one; a failed call never gains a retry here.
          const maxSteps = legacyFixture ? legacyReferences.length + 2 : 1;
          for (let step = 0; step < maxSteps; step++) {
            const firstCall = currentCalls.length;
            const acceptance = await executor.ensureAcceptedMainCompaction({
              ...identity,
              req,
              agent: route,
            });
            persisted = await continuity.loadAcceptedMainContext(identity);
            if (!Array.isArray(persisted.pendingCompactionTurns))
              throw new Error("persisted_source_unavailable");
            const digests = currentCalls
              .slice(firstCall)
              .filter((call) => call.instructionsHash === sha(""))
              .flatMap((call) => call.evidence || [])
              .filter(Boolean)
              .map((entry) => entry.sourceDigest);
            const epoch = await ViventiumMainContinuityState.findOne({
              ownerId: login.user.id,
              agentId,
              recordKind: "epoch",
              contextEpoch: identity.stableAuthoritySha256,
            })
              .select(
                "legacySourceOffset legacyStateCursor legacyMessageCursor legacyComplete summarizedThrough",
              )
              .lean();
            result.compactionSteps.push({
              acceptance,
              epoch,
              sourceDigest: persisted.semanticCompaction?.sourceDigest || null,
              invokedSourceDigests: digests,
              digestAgreement:
                acceptance.status === "compacted"
                  ? digests.length >= 2 &&
                    digests.every(
                      (digest) =>
                        digest === persisted.semanticCompaction?.sourceDigest,
                    )
                  : null,
            });
            if (acceptance.status !== "empty" || !result.acceptance)
              result.acceptance = acceptance;
            if (
              !legacyFixture ||
              (!persisted.legacyPending &&
                persisted.pendingCompactionCount === 0)
            )
              break;
            if (!["compacted", "empty"].includes(acceptance.status)) break;
          }
          if (legacyFixture) {
            result.legacyFixture.complete =
              persisted.legacyPending === false &&
              persisted.pendingCompactionCount === 0;
            result.legacyFixture.immutable =
              legacyRecordDigest ===
              sha(
                JSON.stringify(
                  await ViventiumMainContinuityState.findById(legacyRecordId)
                    .select(legacyProjection)
                    .lean(),
                ),
              );
          }
          result.persisted = {
            semanticCompaction: persisted.semanticCompaction,
            pendingCount: persisted.pendingCompactionTurns.length,
            capsule: persisted.capsule,
            actualSourceDigest:
              persisted.semanticCompaction?.sourceDigest || null,
            invokedSourceDigests: currentCalls
              .filter((call) => call.instructionsHash === sha(""))
              .flatMap((call) => call.evidence || [])
              .filter(Boolean)
              .map((entry) => entry.sourceDigest),
          };
          const promoted = result.compactionSteps.filter(
            (step) => step.acceptance.status === "compacted",
          );
          result.sourceDigestAgreement =
            promoted.length > 0 &&
            promoted.every((step) => step.digestAgreement === true);
          result.output = JSON.stringify(persisted.semanticCompaction);
        } else {
          const isReview = testCase.fixture.compaction.mode === "review";
          const prompt = executor.buildCompactionPrompt(
            claim,
            evidence.priorRejection || "",
            evidence.candidate || null,
          );
          result.renderedPromptHash = sha(prompt);
          result.output = await executor.executeForEvaluation({
            claim,
            prompt,
            req,
            agent: route,
            stage: isReview ? "review" : "compaction",
            signal: new AbortController().signal,
          });
        }
        result.status = "completed";
        if (testCase.fixture.compaction.mode === "review") {
          result.expectedApproved =
            testCase.fixture.compaction.expectedApproved;
          const verdict = executor.parseSemanticCompactionOutput(result.output);
          result.labelAgreement = verdict?.approved === result.expectedApproved;
          if (!result.labelAgreement) result.status = "label_mismatch";
        }
        if (result.acceptance) {
          const expectedAcceptance = testCase.fixture.compaction
            .afterApprovedReview
            ? "stale_source"
            : "compacted";
          result.expectedAcceptance = expectedAcceptance;
          if (result.acceptance.status !== expectedAcceptance)
            result.status = "acceptance_failed";
          if (
            expectedAcceptance === "stale_source" &&
            (result.sourceMutation?.affectedCount !== 1 ||
              result.persisted.semanticCompaction ||
              result.persisted.pendingCount < 1)
          )
            result.status = "stale_source_retention_failed";
        }
        if (
          result.acceptance?.status === "compacted" &&
          result.sourceDigestAgreement !== true
        )
          result.status = "source_digest_mismatch";
        if (
          result.legacyFixture &&
          (!result.legacyFixture.complete || !result.legacyFixture.immutable)
        )
          result.status = "legacy_coverage_failed";
      } catch (error) {
        result.status = "failed";
        result.error = String(error.code || error.errorCode || error.message);
      } finally {
        result.durationMs = Date.now() - startedAt;
        checkpoint();
      }
    }
  } finally {
    background.executeCortex = originalExecute;
    globalThis.fetch = originalFetch;
    // Delete only this run's dedicated synthetic source conversations and ledger identities.
    await ViventiumMainContinuityState.deleteMany({
      ownerId: login.user.id,
      agentId: { $in: ledgerIds },
    });
    await Message.deleteMany({
      user: login.user.id,
      conversationId: { $in: sourceConversationIds },
    });
    await Conversation.deleteMany({
      user: login.user.id,
      conversationId: { $in: sourceConversationIds },
    });
    await mongoose.disconnect();
    checkpoint();
  }
  console.log(
    JSON.stringify({
      cases: results.length,
      failed: results.filter((result) => result.status !== "completed").length,
    }),
  );
  process.exitCode = results.some((result) => result.status !== "completed")
    ? 1
    : 0;
}
async function runWithCleanup(options, qaAuth) {
  try {
    return await run(options, qaAuth);
  } finally {
    await requireLC("mongoose").disconnect();
  }
}
module.exports = {
  run: runWithCleanup,
  caseEvidence,
  readSnapshot,
  loadSnapshotPackages,
  selectedPromptRegistry,
};
if (require.main === module) {
  const lease =
    require("./run-exact-model-evals.cjs").acquireExclusiveEvalLease();
  if (!lease.acquired) {
    console.error(JSON.stringify({ error: lease.reason }));
    process.exit(1);
  }
  runWithCleanup(cliOptions)
    .finally(() => lease.release())
    .then(() => process.exit(process.exitCode || 0))
    .catch((error) => {
      console.error(JSON.stringify({ error: error.code || error.message }));
      process.exit(1);
    });
}
