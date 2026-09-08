"use strict";
// Workbench worker-source replay. Shared executeCortex owns native auth, transport and recovery;
// the real mission workspace/app action remains a separate acceptance gate.
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const Module = require("module");
const { execFileSync } = require("child_process");
const root = path.resolve(__dirname, "../../..");
const lc = path.join(root, "viventium_v0_4/LibreChat");
const requireLC = Module.createRequire(path.join(lc, "package.json"));
const sha = (value) => crypto.createHash("sha256").update(value).digest("hex");

function configuredWorkerRoute(slot, env = process.env) {
  if (!["primary", "fallback"].includes(slot)) throw new Error("invalid_worker_route_slot");
  const profile = env[slot === "primary" ? "GLASSHIVE_DEFAULT_WORKER_PROFILE" : "GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE"];
  const fields = {
    "codex-cli": ["WPR_MODEL_CODEX_CLI", "WPR_CODEX_CLI_REASONING_EFFORT"],
    "claude-code": ["WPR_MODEL_CLAUDE_CODE", "WPR_CLAUDE_CODE_EFFORT"],
  }[profile];
  if (!fields || !env[fields[0]] || !env[fields[1]]) throw new Error("configured_native_worker_route_unavailable");
  return { slot, profile, provider: "glasshive-harness", model: `${profile}:${env[fields[0]]}`, nativeModel: env[fields[0]], effort: env[fields[1]], access: "full" };
}

function readWorkerSource(target, bankPath) {
  // Frozen old/proposed input uses the same explicit snapshot convention as compaction evals.
  // A snapshot contains exact source bytes/hashes plus their composed frames, never credentials.
  if (target?.sourceSnapshot) {
    const descriptor = target.sourceSnapshot;
    const filename = path.resolve(path.dirname(bankPath), descriptor.path || "");
    const bytes = fs.readFileSync(filename);
    if (sha(bytes) !== descriptor.sha256) throw new Error("worker_source_snapshot_hash_mismatch");
    const snapshot = JSON.parse(bytes);
    for (const file of snapshot.sources || []) {
      if (!file.path || sha(file.text) !== file.sha256) throw new Error("worker_source_snapshot_lineage_mismatch");
    }
    if (!snapshot.sources?.length) throw new Error("worker_source_snapshot_lineage_missing");
    return { ...snapshot, snapshotSha256: sha(bytes) };
  }
  const gh = path.join(root, "viventium_v0_4/GlassHive/runtime_phase1");
  const script = `import json,hashlib\nfrom pathlib import Path\nfrom workers_projects_runtime import bootstrap as b, profile_runtime as p\nfiles=[Path(b.__file__),Path(p.__file__)]\nprint(json.dumps({'frames':{'harness':p.HOST_NATIVE_HARNESS_PROMPT,'project':b.GLASSHIVE_WORKER_PROJECT_CONTRACT,'agents':p.HOST_DEFAULT_AGENTS_MD,'claude':p.HOST_DEFAULT_CLAUDE_MD,'codex':p.HOST_DEFAULT_CODEX_MD},'sources':[{'path':f.name,'text':f.read_text(),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]}))`;
  const rendered = execFileSync(path.join(gh, ".venv/bin/python"), ["-c", script], {
    encoding: "utf8", maxBuffer: 10 * 1024 * 1024,
    env: { ...process.env, PYTHONPATH: path.join(gh, "src") },
  });
  const snapshot = JSON.parse(rendered);
  return { ...snapshot, snapshotSha256: sha(rendered) };
}

function sourceInstructions(source, profile) {
  const names = ["harness", "project", "agents", profile === "codex-cli" ? "codex" : "claude"];
  if (names.some((name) => typeof source.frames?.[name] !== "string" || !source.frames[name].trim())) {
    throw new Error("worker_source_frame_missing");
  }
  return names.map((name) => source.frames[name].trim()).join("\n\n");
}

function verifyNativeRun(record, route, instructions) {
  if (!record || record.state !== "completed") throw new Error("completed_native_worker_evidence_missing");
  const bundle = JSON.parse(record.bootstrap_bundle_json || "{}");
  const observedEffort = bundle.env?.[route.profile === "codex-cli" ? "WPR_CODEX_CLI_REASONING_EFFORT" : "WPR_CLAUDE_CODE_EFFORT"];
  if (record.model_id !== route.model || record.provider_route_model !== route.nativeModel || observedEffort !== route.effort || record.access_mode !== route.access || bundle.provider_capabilities?.native_tools !== true) {
    throw new Error("native_worker_route_mismatch");
  }
  if (String(bundle.application_developer_instructions || bundle.developer_instructions || "") !== instructions
      || String(bundle.developer_instructions || "") !== instructions) {
    throw new Error("native_worker_source_not_observed");
  }
  return { ...route, instructionsSha256: sha(instructions), runIdHash: sha(record.run_id), workerIdHash: sha(record.worker_id), state: record.state, nativeTools: true };
}

async function run(args, bank, cases, qaAuth) {
  if (!qaAuth?.ok || !qaAuth.userId || !qaAuth.token || !process.env.CONFIG_PATH || !process.env.MONGO_URI) throw new Error("isolated_qa_runtime_required");
  const harness = require("./run-exact-model-evals.cjs");
  const familyIds = new Set(cases.map((item) => item.familyId));
  if (familyIds.size !== 1) throw new Error("worker_source_requires_one_family");
  const family = bank.families.find((item) => familyIds.has(item.id));
  const source = readWorkerSource(family.executionTarget, args.promptBank);
  const selected = cases.map((item) => ({ testCase: item, route: configuredWorkerRoute(item.fixture?.workerSource?.route || "primary") }));
  requireLC("module-alias")({ base: path.join(lc, "api") });
  for (const name of ["anthropicOAuthPatch", "anthropicThinkingPatch", "openaiResponsesOutputPatch", "agentSchemaToolBindingPatch"]) require(path.join(lc, "api/server/services/viventium", name));
  const mongoose = requireLC("mongoose");
  await require(path.join(lc, "api/db")).connectDb();
  const { User } = require(path.join(lc, "api/db/models"));
  const user = await User.findById(qaAuth.userId).lean();
  if (!user || user.role !== "USER" || !String(user.email).endsWith(".invalid")) throw new Error("synthetic_user_context_required");
  const config = await require(path.join(lc, "api/server/services/Config")).getAppConfig();
  const { executeCortex, createBackgroundRes } = require(path.join(lc, "api/server/services/BackgroundCortexService"));
  const { HumanMessage } = requireLC("@librechat/agents/langchain/messages");
  let results = [];
  const output = path.join(args.outputDir, "exact-model-eval.json");
  fs.mkdirSync(args.outputDir, { recursive: true });
  const checkpoint = () => {
    const complete = results.length === cases.length && results.every((item) => item.status === "completed");
    const judged = complete && results.every((item) => item.semanticJudge?.status === "judged");
    const passed = judged && results.every((item) => item.semanticJudge.pass === true);
    const artifact = { kind: "worker_source_replay", sourceSnapshotSha256: source.snapshotSha256,
      sourceFiles: source.sources.map(({ path: name, sha256 }) => ({ path: name, sha256 })),
      bankHash: sha(fs.readFileSync(args.promptBank)), sharedExecutionSourceHash: sha(fs.readFileSync(path.join(lc, "api/server/services/BackgroundCortexService.js"))),
      liveResults: results, summary: { status: passed ? "passed" : judged ? "failed" : "partial", resultCount: results.length, completedCount: results.filter((item) => item.status === "completed").length },
      scope: "Composed worker source replay through existing native provider, full native tools. Real mission materialization and app/file action are not exercised.", realUserQa: "not performed" };
    fs.writeFileSync(output, JSON.stringify(artifact, null, 2) + "\n", { mode: 0o600 });
    return artifact;
  };
  try {
    for (const { testCase, route } of selected) {
      const runId = `worker-source-${crypto.randomUUID()}`;
      const conversationId = crypto.randomUUID();
      const agentId = `worker-source-${crypto.randomUUID()}`;
      const instructions = sourceInstructions(source, route.profile);
      const agent = { id: agentId, name: "Worker source evaluation", provider: route.provider, model: route.model,
        model_parameters: { model: route.model, reasoning_effort: route.effort }, instructions,
        agent_ids: [], edges: [], tools: [], mcp: [], tool_resources: {}, tool_options: {}, background_cortices: [], viventiumProviderSessionMode: "stateless" };
      const req = { body: { conversationId }, user: { ...user, id: String(user._id), personalization: { memories: false, conversation_recall: false } }, config,
        headers: { authorization: `Bearer ${qaAuth.token}` }, _viventiumFeelingSnapshot: null };
      req.get = (name) => req.headers[String(name).toLowerCase()];
      const fixture = testCase.fixture.workerSource;
      const messages = [new HumanMessage(`Project context and observed evidence:\n${JSON.stringify(fixture.evidence)}`),
        new HumanMessage(fixture.previousUserRequest), new HumanMessage(testCase.prompt)];
      const row = { caseId: testCase.id, familyId: testCase.familyId, requestedRoute: route,
        executionIdentity: { ownerId: qaAuth.userId, conversationId, agentId, requestMessageId: runId },
        requestIdentityHash: sha(`${qaAuth.userId}:${conversationId}:${agentId}:${runId}`), instructionsSha256: sha(instructions),
        inputSha256: sha(JSON.stringify(messages.map((message) => message.content))), startedAt: new Date().toISOString(), status: "running" };
      results.push(row); checkpoint();
      try {
        const response = await executeCortex({ agent, messages, runId, conversationId, req, res: createBackgroundRes(), contextMode: "minimal", completedResultPolicy: "internal", insightMode: "structured", executionTimeoutMs: args.timeoutMs });
        if (response.error || !response.insight || response.fallbackUsed) throw new Error(response.errorClass || response.error || "worker_source_response_unavailable");
        const native = harness.queryGlassHiveProviderRun(process.env, runId, { ownerId: qaAuth.userId, conversationId, agentId, nativeAuthority: true });
        row.observedRoute = verifyNativeRun(native, route, instructions);
        row.observedRequestIdentityHash = row.requestIdentityHash; // Query above requires every exact owner/session/message binding.
        row.nativeAudit = harness.readGlassHiveRunToolAudit(native);
        if (!row.nativeAudit?.stdoutHash) throw new Error("native_worker_tool_audit_missing");
        const stdoutPath = path.join(path.dirname(native.state_dir), "home/.glasshive-runs", native.run_id, "stdout.log");
        const events = fs.readFileSync(stdoutPath, "utf8").split(/\r?\n/).flatMap((line) => { try { return [JSON.parse(line)]; } catch { return []; } });
        row.nativeCalls = harness.nativeToolAuditItems(events);
        row.responseForJudge = response.insight;
        row.postCaseEvidenceForJudge = harness.scrubForPublic(JSON.stringify({ scope: "read-only worker source replay", nativeAudit: row.nativeAudit, nativeCalls: row.nativeCalls }));
        row.status = "completed";
      } catch (error) { row.status = "failed"; row.error = String(error.message || error); }
      row.endedAt = new Date().toISOString(); checkpoint();
      if (row.status !== "completed") break; // Do not multiply a transport/authority failure.
    }
    if (results.length === cases.length && results.every((row) => row.status === "completed")) {
      const verdict = await harness.judgeLiveResults(args, bank, results, qaAuth.token);
      results = verdict.results;
    }
    const artifact = checkpoint();
    console.log(JSON.stringify(artifact.summary));
    return artifact;
  } finally { await mongoose.disconnect(); }
}

module.exports = { run, configuredWorkerRoute, readWorkerSource, sourceInstructions, verifyNativeRun };
