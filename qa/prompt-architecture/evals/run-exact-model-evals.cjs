#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const childProcess = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const { assertNonOwnerQaSelection } = require(
  path.join(
    REPO_ROOT,
    "qa",
    "background_agents",
    "evals",
    "browser-qa-safety.cjs",
  ),
);
const XAI_TTS_CAPABILITIES = require(
  path.join(LIBRECHAT_ROOT, "shared", "voice", "xai_tts_capabilities.json"),
);
const CARTESIA_TTS_CAPABILITIES = require(
  path.join(
    LIBRECHAT_ROOT,
    "shared",
    "voice",
    "cartesia_sonic3_capabilities.json",
  ),
);
const TTS_PROVIDER_CAPABILITIES = require(
  path.join(
    LIBRECHAT_ROOT,
    "shared",
    "voice",
    "tts_provider_capabilities.json",
  ),
);
const { stripDeliveryControlsForPreview } = require(
  path.join(
    LIBRECHAT_ROOT,
    "api",
    "server",
    "services",
    "viventium",
    "deliveryControls.js",
  ),
);
const CHATTERBOX_INLINE_CONTROLS =
  TTS_PROVIDER_CAPABILITIES.providers.local_chatterbox_turbo_mlx_8bit
    .inline_controls.exact_tokens;
const PROMPT_BANK_PATH = path.join(__dirname, "prompt-bank.json");
const DEFAULT_API_BASE =
  process.env.VIVENTIUM_EVAL_API_BASE || "http://localhost:3180";
const DEFAULT_QA_EMAIL = process.env.VIVENTIUM_QA_EMAIL || "qa@example.com";
const MAIN_AGENT_ID = "agent_viventium_main_95aeb3";
const NO_PARENT = "00000000-0000-0000-0000-000000000000";
const LIVE_RUN_FLAG = "VIVENTIUM_RUN_EXACT_MODEL_EVALS";
const QA_PASSWORD_ENV = "VIVENTIUM_QA_PASSWORD";
const LOCAL_JWT_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_LOCAL_JWT";
const SEMANTIC_JUDGE_FLAG = "VIVENTIUM_EVAL_SEMANTIC_JUDGE";
const DEFAULT_JUDGE_MODEL = process.env.VIVENTIUM_EVAL_JUDGE_MODEL || "gpt-5.4";
const DEFAULT_JUDGE_ROUTE =
  process.env.VIVENTIUM_EVAL_JUDGE_ROUTE || "local-ephemeral";
const STARTER_MORNING_BRIEFING_TEMPLATE_ID = "morning_briefing_default_v1";
const STARTER_MORNING_BRIEFING_BASELINE_PROMPT =
  "Morning orientation: review my memories, calendar, pending tasks, " +
  "and any overnight signals. Prepare a concise morning briefing for the user.";
const BROWSER_USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ViventiumPromptEval/1.0";
const PRIVATE_ROOT =
  process.env.VIVENTIUM_PROMPT_ARCH_PRIVATE_DIR ||
  path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "private-user-data",
  );
const EXACT_MODEL_EVAL_LOCK_PATH = path.join(
  PRIVATE_ROOT,
  "prompt-architecture-evals",
  ".exact-model-eval.lock",
);
const MEMORY_RECALL_BANK_VERSION = "continuity-recall-v1.1.0";
const FROZEN_MEMORY_RECALL_BANK_HASH = "987dfffc5021ba69";

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function parseArgs(argv) {
  const args = {
    apiBase: DEFAULT_API_BASE,
    promptBank: PROMPT_BANK_PATH,
    outputDir: path.join(
      PRIVATE_ROOT,
      "prompt-architecture-evals",
      timestampSlug(),
    ),
    publicReport: path.join(
      REPO_ROOT,
      "qa",
      "prompt-architecture",
      "reports",
      "phase-4-exact-model-eval-baseline.md",
    ),
    qaEmail: DEFAULT_QA_EMAIL,
    runLive: process.env[LIVE_RUN_FLAG] === "1",
    localJwtFallback: process.env.VIVENTIUM_QA_LOCAL_JWT_FALLBACK === "1",
    maxCases: Number.MAX_SAFE_INTEGER,
    timeoutMs: 120_000,
    postCaseObserveMs: Number.parseInt(
      process.env.VIVENTIUM_EVAL_POST_CASE_OBSERVE_MS || "20000",
      10,
    ),
    followUpGraceMs: Number.parseInt(
      process.env.VIVENTIUM_EVAL_FOLLOWUP_GRACE_MS || "30000",
      10,
    ),
    agentId: process.env.VIVENTIUM_EVAL_AGENT_ID || MAIN_AGENT_ID,
    semanticJudge: process.env[SEMANTIC_JUDGE_FLAG] === "1",
    semanticJudgeExplicitlyDisabled: false,
    judgeModel: DEFAULT_JUDGE_MODEL,
    judgeRoute: DEFAULT_JUDGE_ROUTE,
    judgeEndpoint: process.env.VIVENTIUM_EVAL_JUDGE_ENDPOINT || "openAI",
    judgeAgentId:
      process.env.VIVENTIUM_EVAL_JUDGE_AGENT_ID ||
      process.env.VIVENTIUM_EVAL_AGENT_ID ||
      MAIN_AGENT_ID,
    family: "",
    caseId: "",
    caseIds: [],
    surface: "",
    promptId: "",
  };

  for (const arg of argv) {
    if (arg === "--run-live") {
      args.runLive = true;
    } else if (arg === "--no-live") {
      args.runLive = false;
    } else if (arg === "--local-jwt-fallback") {
      args.localJwtFallback = true;
    } else if (arg.startsWith("--api-base=")) {
      args.apiBase = arg.slice("--api-base=".length).replace(/\/$/, "");
    } else if (arg.startsWith("--prompt-bank=")) {
      args.promptBank = path.resolve(arg.slice("--prompt-bank=".length));
    } else if (arg.startsWith("--output-dir=")) {
      args.outputDir = path.resolve(arg.slice("--output-dir=".length));
    } else if (arg.startsWith("--public-report=")) {
      args.publicReport = path.resolve(arg.slice("--public-report=".length));
    } else if (arg.startsWith("--qa-email=")) {
      args.qaEmail = arg.slice("--qa-email=".length).trim();
    } else if (arg.startsWith("--agent-id=")) {
      args.agentId = arg.slice("--agent-id=".length).trim() || MAIN_AGENT_ID;
    } else if (arg.startsWith("--max-cases=")) {
      const parsed = Number.parseInt(arg.slice("--max-cases=".length), 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        args.maxCases = parsed;
      }
    } else if (arg.startsWith("--timeout-ms=")) {
      const parsed = Number.parseInt(arg.slice("--timeout-ms=".length), 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        args.timeoutMs = parsed;
      }
    } else if (arg.startsWith("--post-case-observe-ms=")) {
      const parsed = Number.parseInt(
        arg.slice("--post-case-observe-ms=".length),
        10,
      );
      if (Number.isFinite(parsed) && parsed >= 0) {
        args.postCaseObserveMs = parsed;
      }
    } else if (arg.startsWith("--follow-up-grace-ms=")) {
      const parsed = Number.parseInt(
        arg.slice("--follow-up-grace-ms=".length),
        10,
      );
      if (Number.isFinite(parsed) && parsed >= 0) {
        args.followUpGraceMs = parsed;
      }
    } else if (arg === "--semantic-judge") {
      args.semanticJudge = true;
      args.semanticJudgeExplicitlyDisabled = false;
    } else if (arg === "--no-semantic-judge") {
      args.semanticJudge = false;
      args.semanticJudgeExplicitlyDisabled = true;
    } else if (arg.startsWith("--judge-model=")) {
      args.judgeModel =
        arg.slice("--judge-model=".length).trim() || DEFAULT_JUDGE_MODEL;
    } else if (arg.startsWith("--judge-route=")) {
      const route = arg.slice("--judge-route=".length).trim();
      if (route) {
        args.judgeRoute = route;
      }
    } else if (arg.startsWith("--judge-endpoint=")) {
      args.judgeEndpoint =
        arg.slice("--judge-endpoint=".length).trim() || args.judgeEndpoint;
    } else if (arg.startsWith("--judge-agent-id=")) {
      args.judgeAgentId =
        arg.slice("--judge-agent-id=".length).trim() || args.judgeAgentId;
    } else if (arg.startsWith("--family=")) {
      args.family = arg.slice("--family=".length).trim();
    } else if (arg.startsWith("--case=")) {
      args.caseId = arg.slice("--case=".length).trim();
    } else if (arg.startsWith("--case-ids=")) {
      args.caseIds = normalizeCaseIds(arg.slice("--case-ids=".length));
    } else if (arg.startsWith("--surface=")) {
      args.surface = arg.slice("--surface=".length).trim();
    } else if (arg.startsWith("--prompt-id=")) {
      args.promptId = arg.slice("--prompt-id=".length).trim();
    }
  }

  return args;
}

function normalizeCaseIds(rawCaseIds) {
  const caseIds = Array.isArray(rawCaseIds)
    ? rawCaseIds
    : String(rawCaseIds || "").split(",");
  const normalized = [...new Set(caseIds.map((value) => String(value).trim()).filter(Boolean))];
  if (normalized.length > 100) {
    throw new Error("case_ids_exceed_100");
  }
  if (normalized.some((value) => !/^[A-Za-z0-9_.:-]{1,160}$/.test(value))) {
    throw new Error("invalid_case_id");
  }
  return normalized;
}

function summarizeLatencyMs(values) {
  const sorted = values
    .filter((value) => value != null && value !== "")
    .map(Number)
    .filter((value) => Number.isFinite(value) && value >= 0)
    .sort((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 0
      ? (sorted[middle - 1] + sorted[middle]) / 2
      : sorted[middle];
  return {
    count: sorted.length,
    min: sorted[0],
    mean: sorted.reduce((total, value) => total + value, 0) / sorted.length,
    median,
    p95: sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)],
    max: sorted[sorted.length - 1],
  };
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function processIsAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error?.code === "EPERM";
  }
}

function acquireExclusiveEvalLease(lockPath = EXACT_MODEL_EVAL_LOCK_PATH) {
  ensureDir(path.dirname(lockPath));
  const nonce = crypto.randomUUID();
  const payload = {
    pid: process.pid,
    startedAt: new Date().toISOString(),
    nonce,
  };
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const fd = fs.openSync(lockPath, "wx", 0o600);
      try {
        fs.writeFileSync(fd, `${JSON.stringify(payload)}\n`, "utf8");
      } finally {
        fs.closeSync(fd);
      }
      let released = false;
      return {
        acquired: true,
        reason: null,
        recoveredStaleLease: attempt > 1,
        release() {
          if (released) return;
          released = true;
          try {
            const current = JSON.parse(fs.readFileSync(lockPath, "utf8"));
            if (current?.nonce === nonce) fs.unlinkSync(lockPath);
          } catch (error) {
            if (error?.code !== "ENOENT") throw error;
          }
        },
      };
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      let existing = null;
      try {
        existing = JSON.parse(fs.readFileSync(lockPath, "utf8"));
      } catch (_readError) {
        existing = null;
      }
      if (processIsAlive(Number(existing?.pid))) {
        return {
          acquired: false,
          reason: "exact_model_eval_already_running",
          recoveredStaleLease: false,
          release() {},
        };
      }
      try {
        fs.unlinkSync(lockPath);
      } catch (unlinkError) {
        if (unlinkError?.code !== "ENOENT") throw unlinkError;
      }
    }
  }
  return {
    acquired: false,
    reason: "exact_model_eval_lease_unavailable",
    recoveredStaleLease: false,
    release() {},
  };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) {
    return values;
  }
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const [key, ...rest] = line.split("=");
    let value = rest.join("=").trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key.trim()] = value;
  }
  return values;
}

function loadLocalEnv() {
  const candidates = [
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "runtime.env",
    ),
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "runtime.local.env",
    ),
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "runtime",
      "service-env",
      "librechat.env",
    ),
    path.join(LIBRECHAT_ROOT, ".env"),
  ];
  return candidates.reduce(
    (acc, filePath) => Object.assign(acc, parseEnvFile(filePath)),
    {
      ...process.env,
    },
  );
}

function expandHome(filePath) {
  if (!filePath) {
    return filePath;
  }
  if (filePath === "~") {
    return os.homedir();
  }
  if (filePath.startsWith("~/")) {
    return path.join(os.homedir(), filePath.slice(2));
  }
  return filePath;
}

function sqlQuote(value) {
  return `'${String(value ?? "").replace(/'/g, "''")}'`;
}

function sqliteUpdateStarterPrompt(dbPath, { userId, agentId }) {
  const resolvedPath = expandHome(dbPath);
  if (!resolvedPath || !fs.existsSync(resolvedPath)) {
    return { ok: false, reason: "scheduling_db_missing" };
  }
  const updatedAt = new Date().toISOString();
  const updatedBy = agentId ? `agent:${agentId}` : "agent:qa-fixture";
  const sql = [
    "UPDATE scheduled_tasks",
    `SET prompt = ${sqlQuote(STARTER_MORNING_BRIEFING_BASELINE_PROMPT)},`,
    `updated_at = ${sqlQuote(updatedAt)},`,
    `updated_by = ${sqlQuote(updatedBy)},`,
    "updated_source = 'qa_fixture'",
    `WHERE user_id = ${sqlQuote(userId)}`,
    `AND metadata_json LIKE ${sqlQuote(`%${STARTER_MORNING_BRIEFING_TEMPLATE_ID}%`)};`,
    "SELECT changes();",
  ].join(" ");
  const output = childProcess
    .execFileSync("sqlite3", ["-batch", "-noheader", resolvedPath, sql], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    })
    .trim();
  const changed = Number.parseInt(output.split(/\r?\n/).pop() || "0", 10) || 0;
  return { ok: changed > 0, changed, dbPathHash: hashValue(resolvedPath) };
}

function schedulingDbPathCandidates(env) {
  const profile = env.VIVENTIUM_RUNTIME_PROFILE || "isolated";
  const candidates = [
    env.SCHEDULING_DB_PATH,
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "state",
      "runtime",
      profile,
      "scheduling",
      "schedules.db",
    ),
    path.join(os.homedir(), ".viventium", "scheduling", "schedules.db"),
  ].filter(Boolean);
  return [...new Set(candidates.map(expandHome))];
}

function glassHiveRuntimeDbPathCandidates(env) {
  const profile = env.VIVENTIUM_RUNTIME_PROFILE || "isolated";
  return [
    env.WPR_DB_PATH,
    env.GLASSHIVE_RUNTIME_DB_PATH,
    path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Viventium",
      "state",
      "runtime",
      profile,
      "glasshive",
      "runtime_phase1.db",
    ),
  ]
    .map(expandHome)
    .filter((candidate, index, values) =>
      Boolean(candidate) && values.indexOf(candidate) === index,
    );
}

function queryGlassHiveProviderRun(env, responseMessageId) {
  if (!responseMessageId) return null;
  const sql = [
    "SELECT pr.run_id, r.state, w.worker_id, w.state_dir",
    "FROM provider_requests pr",
    "JOIN runs r ON r.run_id = pr.run_id",
    "JOIN workers w ON w.worker_id = r.worker_id",
    `WHERE pr.message_id = ${sqlQuote(responseMessageId)}`,
    "ORDER BY pr.created_at DESC LIMIT 1;",
  ].join(" ");
  for (const candidate of glassHiveRuntimeDbPathCandidates(env)) {
    if (!fs.existsSync(candidate)) continue;
    try {
      const raw = childProcess.execFileSync(
        "sqlite3",
        ["-batch", "-json", candidate, sql],
        { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      );
      const rows = JSON.parse(raw || "[]");
      if (rows[0]?.run_id && rows[0]?.state_dir) {
        return { ...rows[0], dbPathHash: hashValue(candidate) };
      }
    } catch {
      // Try the next supported runtime location. The audit fails closed below.
    }
  }
  return null;
}

function readGlassHiveRunToolAudit(runRecord, requiredEvidenceFragments = []) {
  if (!runRecord?.run_id || !runRecord?.state_dir) return null;
  const workerRoot = path.dirname(String(runRecord.state_dir));
  const runRoot = path.join(
    workerRoot,
    "home",
    ".glasshive-runs",
    String(runRecord.run_id),
  );
  const stdoutPath = path.join(runRoot, "stdout.log");
  const stderrPath = path.join(runRoot, "stderr.log");
  if (!fs.existsSync(stdoutPath)) return null;
  const events = fs
    .readFileSync(stdoutPath, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line)];
      } catch {
        return [];
      }
    });
  const itemEvents = events
    .filter((event) => event?.item && typeof event.item === "object")
    .map((event) => ({ eventType: event.type, ...event.item }));
  const brokerFileSearchEvents = itemEvents.filter(
    (item) =>
      item.type === "mcp_tool_call" &&
      item.server === "glasshive-user-capabilities" &&
      item.tool === "file_search",
  );
  const nativeExecutionEvents = itemEvents.filter((item) => {
    const type = String(item.type || "");
    return (
      type === "command_execution" ||
      type === "dynamic_tool_call" ||
      type.startsWith("web_search") ||
      type.startsWith("file_change")
    );
  });
  const commandEvents = nativeExecutionEvents.filter(
    (item) => item.type === "command_execution",
  );
  const normalizedEvidenceFragments = requiredEvidenceFragments
    .map(normalizeVisibleEvidence)
    .filter(Boolean);
  const nativeEvidenceSubstitutionEvents = nativeExecutionEvents.filter((item) => {
    if (item.eventType !== "item.completed") return false;
    const output = normalizeVisibleEvidence(
      item.aggregated_output || item.output || item.result || "",
    );
    return (
      output &&
      normalizedEvidenceFragments.some((fragment) => output.includes(fragment))
    );
  });
  const stderr = fs.existsSync(stderrPath)
    ? fs.readFileSync(stderrPath, "utf8")
    : "";
  return {
    runIdHash: hashValue(runRecord.run_id),
    workerIdHash: hashValue(runRecord.worker_id || ""),
    runState: String(runRecord.state || "unknown"),
    brokerFileSearchStartedCount: brokerFileSearchEvents.filter(
      (item) => item.eventType === "item.started",
    ).length,
    brokerFileSearchCompletedCount: brokerFileSearchEvents.filter(
      (item) =>
        item.eventType === "item.completed" &&
        item.status === "completed" &&
        !item.error,
    ).length,
    brokerFileSearchErrorCount: brokerFileSearchEvents.filter(
      (item) => item.error || item.status === "failed",
    ).length,
    nativeCommandExecutionStartedCount: commandEvents.filter(
      (item) => item.eventType === "item.started",
    ).length,
    nativeCommandExecutionCompletedCount: commandEvents.filter(
      (item) => item.eventType === "item.completed",
    ).length,
    nativeEvidenceSubstitutionStartedCount:
      nativeEvidenceSubstitutionEvents.length,
    nativeEvidenceSubstitutionCompletedCount:
      nativeEvidenceSubstitutionEvents.length,
    stderrChars: stderr.length,
    stderrHash: stderr ? hashValue(stderr) : "",
    stdoutHash: hashValue(fs.readFileSync(stdoutPath, "utf8")),
    dbPathHash: runRecord.dbPathHash,
  };
}

function normalizeVisibleEvidence(value) {
  return String(value || "")
    .normalize("NFKC")
    .replace(/[`*_~]+/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase();
}

function auditNativeProviderFileSearch(responseEvents = []) {
  const matchingCalls = [];
  const unexpectedToolNames = [];
  for (const event of responseEvents || []) {
    const stepDetails = event?.data?.stepDetails || {};
    const result = event?.data?.result || {};
    const rawToolCalls = [
      ...(Array.isArray(stepDetails?.tool_calls)
        ? stepDetails.tool_calls
        : stepDetails?.tool_call
          ? [stepDetails.tool_call]
          : []),
      ...(Array.isArray(stepDetails?.toolCalls)
        ? stepDetails.toolCalls
        : stepDetails?.toolCall
          ? [stepDetails.toolCall]
          : []),
      ...(result?.type === "tool_call"
        ? [result?.tool_call || result?.toolCall || result]
        : []),
    ];
    const normalizedToolCalls = rawToolCalls;
    for (const call of normalizedToolCalls) {
      if (!call || typeof call !== "object") continue;
      const toolCall = call.tool_call || call;
      const toolName = String(
        toolCall.name ||
          toolCall.function?.name ||
          call.name ||
          call.function?.name ||
          "",
      ).trim();
      if (!toolName) continue;
      if (toolName !== "file_search") {
        unexpectedToolNames.push(toolName);
        continue;
      }
      matchingCalls.push({
        event: String(event?.event || ""),
        error: Boolean(toolCall.error || call.error),
      });
    }
  }
  return {
    startedCount: matchingCalls.filter((item) => item.event === "on_run_step")
      .length,
    completedCount: matchingCalls.filter(
      (item) => item.event === "on_run_step_completed" && !item.error,
    ).length,
    errorCount: matchingCalls.filter((item) => item.error).length,
    unexpectedToolNameHashes: [...new Set(unexpectedToolNames)].map(hashValue),
  };
}

async function auditConversationRecallExecution({
  env,
  responseMessageId,
  fixture,
  responseText,
  responseEvents = [],
}) {
  if (!fixture) return { evidence: null, failures: [] };
  let runRecord = null;
  if (fixture.requireBrokerHostTool) {
    for (let attempt = 0; attempt < 8 && !runRecord; attempt += 1) {
      runRecord = queryGlassHiveProviderRun(env, responseMessageId);
      if (!runRecord) {
        await new Promise((resolve) => setTimeout(resolve, 125));
      }
    }
  }
  const toolAudit = readGlassHiveRunToolAudit(
    runRecord,
    fixture.requiredResponseFragments,
  );
  const nativeToolAudit = auditNativeProviderFileSearch(responseEvents);
  const normalizedResponse = normalizeVisibleEvidence(responseText);
  const missingRequiredFragmentHashes = fixture.requiredResponseFragments
    .filter(
      (fragment) =>
        !normalizedResponse.includes(normalizeVisibleEvidence(fragment)),
    )
    .map((fragment) => hashValue(fragment));
  const presentForbiddenFragmentHashes = (fixture.forbiddenResponseFragments || [])
    .filter((fragment) =>
      normalizedResponse.includes(normalizeVisibleEvidence(fragment)),
    )
    .map((fragment) => hashValue(fragment));
  const failures = [];
  if (missingRequiredFragmentHashes.length > 0) {
    failures.push("conversation_recall_expected_evidence_missing");
  }
  if (presentForbiddenFragmentHashes.length > 0) {
    failures.push("conversation_recall_forbidden_evidence_present");
  }
  if (fixture.requireBrokerHostTool) {
    if (!toolAudit) {
      failures.push("conversation_recall_execution_audit_missing");
    } else if (toolAudit.brokerFileSearchCompletedCount < 1) {
      failures.push("conversation_recall_broker_file_search_not_completed");
    }
  }
  if (
    fixture.requireNativeHostTool &&
    nativeToolAudit.completedCount < 1
  ) {
    failures.push("conversation_recall_native_file_search_not_completed");
  }
  if (
    fixture.forbidNativeCommandExecution &&
    (Number(toolAudit?.nativeCommandExecutionCompletedCount || 0) > 0 ||
      Number(toolAudit?.nativeEvidenceSubstitutionStartedCount || 0) > 0 ||
      nativeToolAudit.unexpectedToolNameHashes.length > 0)
  ) {
    failures.push("conversation_recall_native_command_substitution_detected");
  }
  return {
    evidence: {
      fixture: "conversation_recall_execution",
      nonceHash: fixture.nonceHash,
      coverageCategory: fixture.coverageCategory || null,
      requiredFragmentHashes: fixture.requiredResponseFragments.map((fragment) =>
        hashValue(fragment),
      ),
      missingRequiredFragmentHashes,
      forbiddenFragmentHashes: (fixture.forbiddenResponseFragments || []).map(
        (fragment) => hashValue(fragment),
      ),
      presentForbiddenFragmentHashes,
      toolAudit,
      nativeFileSearchStartedCount: nativeToolAudit.startedCount,
      nativeFileSearchCompletedCount: nativeToolAudit.completedCount,
      nativeFileSearchErrorCount: nativeToolAudit.errorCount,
      unexpectedNativeToolNameHashes:
        nativeToolAudit.unexpectedToolNameHashes,
    },
    failures,
  };
}

function updateStarterPromptAcrossDbCandidates(env, { userId, agentId }) {
  const attempts = [];
  for (const candidate of schedulingDbPathCandidates(env)) {
    const result = sqliteUpdateStarterPrompt(candidate, { userId, agentId });
    attempts.push(result);
    if (result.ok) {
      return { ok: true, attempts };
    }
  }
  return { ok: false, attempts };
}

function schedulingBaseUrl(env) {
  const raw = (env.SCHEDULING_MCP_URL || "http://localhost:7010").replace(
    /\/$/,
    "",
  );
  return raw.replace(/\/mcp$/i, "");
}

function needsStarterMorningBriefingFixture(testCase) {
  return (
    testCase?.fixture?.starter_morning_briefing === "baseline_without_blockers"
  );
}

function feelingsFixtureFor(testCase) {
  const fixture = testCase?.fixture?.feelings;
  return fixture && typeof fixture === "object" ? fixture : null;
}

function voiceOutputFixtureFor(testCase) {
  const fixture = testCase?.fixture?.voiceOutput;
  if (!fixture || typeof fixture !== "object" || fixture.requested !== true) {
    return null;
  }
  const provider = String(fixture.provider || "")
    .trim()
    .toLowerCase();
  const markerExpectation = String(fixture.markerExpectation || "")
    .trim()
    .toLowerCase();
  if (!provider || !["present", "absent"].includes(markerExpectation)) {
    return null;
  }
  return { requested: true, provider, markerExpectation };
}

function replaceRunNonce(value, runNonce) {
  return String(value || "").replaceAll("{{RUN_NONCE}}", runNonce);
}

function conversationRecallFixtureFor(testCase, runNonce = "") {
  const fixture = testCase?.fixture?.conversationRecall;
  if (!fixture || typeof fixture !== "object" || fixture.enabled !== true) {
    return null;
  }
  const effectiveNonce = runNonce || crypto.randomBytes(8).toString("hex");
  const seedCorpusPrompts = Array.isArray(fixture.seedCorpusPrompts)
    ? fixture.seedCorpusPrompts
        .map((value) => replaceRunNonce(value, effectiveNonce).trim())
        .filter(Boolean)
        .slice(0, 4)
    : [];
  const requiredResponseFragments = Array.isArray(
    fixture.requiredResponseFragments,
  )
    ? fixture.requiredResponseFragments
        .map((value) => replaceRunNonce(value, effectiveNonce).trim())
        .filter(Boolean)
        .slice(0, 8)
    : [];
  const forbiddenResponseFragments = Array.isArray(
    fixture.forbiddenResponseFragments,
  )
    ? fixture.forbiddenResponseFragments
        .map((value) => replaceRunNonce(value, effectiveNonce).trim())
        .filter(Boolean)
        .slice(0, 8)
    : [];
  if (seedCorpusPrompts.length === 0) {
    throw new Error("conversation_recall_fixture_requires_seed_corpus");
  }
  if (requiredResponseFragments.length === 0) {
    throw new Error("conversation_recall_fixture_requires_response_fragments");
  }
  if (
    (fixture.requireBrokerHostTool === true) ===
    (fixture.requireNativeHostTool === true)
  ) {
    throw new Error("conversation_recall_fixture_requires_exactly_one_tool_transport");
  }
  if (fixture.forbidNativeCommandExecution !== true) {
    throw new Error("conversation_recall_fixture_requires_native_substitution_guard");
  }
  return {
    enabled: true,
    seedCorpusPrompts,
    requiredResponseFragments,
    forbiddenResponseFragments,
    requireBrokerHostTool: fixture.requireBrokerHostTool === true,
    requireNativeHostTool: fixture.requireNativeHostTool === true,
    forbidNativeCommandExecution:
      fixture.forbidNativeCommandExecution === true,
    requireSemanticRetrieval: fixture.requireSemanticRetrieval === true,
    coverageCategory: String(fixture.coverageCategory || "").trim() || null,
    nonceHash: hashValue(effectiveNonce),
  };
}

function qaUserSelector(userId) {
  const { ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  if (!ObjectId.isValid(String(userId || ""))) {
    throw new Error("invalid_qa_user_id_for_recall_fixture");
  }
  return { _id: new ObjectId(String(userId)) };
}

async function patchConversationRecallPreference({ args, token, enabled }) {
  const response = await fetchJson(
    `${args.apiBase}/api/memories/preferences`,
    {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
      },
      body: JSON.stringify({ conversation_recall: enabled }),
    },
    20_000,
  );
  if (
    !response.ok ||
    response.body?.preferences?.conversation_recall !== enabled
  ) {
    throw new Error(`conversation_recall_fixture_http_${response.status}`);
  }
  return response.body.preferences;
}

async function applyConversationRecallFixture({
  args,
  token,
  db,
  userId,
  testCase,
}) {
  if (!conversationRecallFixtureFor(testCase)) return null;
  if (!db || !userId) {
    throw new Error("conversation_recall_fixture_db_unavailable");
  }
  const selector = qaUserSelector(userId);
  const user = await db.collection("users").findOne(selector, {
    projection: { "personalization.conversation_recall": 1 },
  });
  if (!user) {
    throw new Error("conversation_recall_fixture_user_missing");
  }
  const originalEnabled = user.personalization?.conversation_recall === true;
  const corpusStateBeforeFixture = await readConversationRecallCorpusState({ db, userId });
  await patchConversationRecallPreference({ args, token, enabled: true });
  return {
    restoreState: { selector, originalEnabled },
    corpusStateBeforeFixture,
    evidence: {
      fixture: "conversation_recall_preference",
      configured: true,
      originalEnabled,
    },
  };
}

async function readConversationRecallCorpusState({ db, userId }) {
  if (!db || !userId) {
    throw new Error("conversation_recall_semantic_fixture_db_unavailable");
  }
  const file = await db.collection("files").findOne(
    {
      user: qaUserSelector(userId)._id,
      file_id: `conversation_recall:${String(userId)}:all`,
    },
    {
      projection: {
        embedded: 1,
        updatedAt: 1,
        "metadata.conversationRecallSourceDigest": 1,
        "metadata.conversationRecallUploadedDigest": 1,
      },
    },
  );
  return {
    exists: Boolean(file),
    embedded: file?.embedded === true,
    updatedAtMs: file?.updatedAt ? new Date(file.updatedAt).getTime() : null,
    sourceDigest: file?.metadata?.conversationRecallSourceDigest || null,
    uploadedDigest: file?.metadata?.conversationRecallUploadedDigest || null,
  };
}

async function waitForConversationRecallCorpusRefresh({
  db,
  userId,
  previousState,
  timeoutMs = 240_000,
  pollMs = 500,
}) {
  const startedAt = Date.now();
  const previousDigest = previousState?.sourceDigest || null;
  while (Date.now() - startedAt < timeoutMs) {
    const current = await readConversationRecallCorpusState({ db, userId });
    const digestAdvanced = current.sourceDigest && current.sourceDigest !== previousDigest;
    if (current.exists && current.embedded && current.uploadedDigest && digestAdvanced) {
      return {
        ...current,
        waitedMs: Date.now() - startedAt,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  throw new Error("conversation_recall_semantic_fixture_not_fresh");
}

async function restoreConversationRecallFixture({
  args,
  token,
  db,
  restoreState,
}) {
  if (!restoreState) return { status: "skipped" };
  await patchConversationRecallPreference({
    args,
    token,
    enabled: restoreState.originalEnabled,
  });
  const restored = await db.collection("users").findOne(restoreState.selector, {
    projection: { "personalization.conversation_recall": 1 },
  });
  if (
    !restored ||
    (restored.personalization?.conversation_recall === true) !==
      restoreState.originalEnabled
  ) {
    throw new Error("conversation_recall_fixture_restore_verification_failed");
  }
  return { status: "restored_exact" };
}

async function insertConversationRecallCorpusFixture({
  db,
  userId,
  agentId,
  prompts,
}) {
  const texts = Array.isArray(prompts) ? prompts.filter(Boolean) : [];
  if (!db || !userId || texts.length === 0) {
    return null;
  }
  const { ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  // Users use ObjectId, but LibreChat conversation/message schemas deliberately persist
  // their `user` foreign key as a string. Writing the fixture as ObjectId makes the raw row
  // exist while every production Mongoose recall query (which casts `user` to String) misses it.
  const userKey = String(userId);
  const conversationId = crypto.randomUUID();
  const createdAt = new Date(Date.now() - 60_000);
  const messageIds = [];
  const messageRows = texts.map((text, index) => {
    const messageId = crypto.randomUUID();
    messageIds.push(messageId);
    return {
      _id: new ObjectId(),
      user: userKey,
      conversationId,
      messageId,
      parentMessageId: index === 0 ? NO_PARENT : messageIds[index - 1],
      sender: "User",
      text,
      isCreatedByUser: true,
      endpoint: "agents",
      model: agentId,
      tokenCount: Math.max(1, Math.ceil(text.length / 4)),
      createdAt: new Date(createdAt.getTime() + index * 1000),
      updatedAt: new Date(createdAt.getTime() + index * 1000),
    };
  });
  await db.collection("conversations").insertOne({
    _id: new ObjectId(),
    user: userKey,
    conversationId,
    endpoint: "agents",
    agent_id: agentId,
    title: "Synthetic continuity fixture",
    createdAt,
    updatedAt: createdAt,
  });
  try {
    await db.collection("messages").insertMany(messageRows);
  } catch (error) {
    await db.collection("conversations").deleteOne({ conversationId });
    throw error;
  }
  return {
    conversationId,
    evidence: {
      fixture: "conversation_recall_corpus",
      conversationCount: 1,
      messageCount: messageRows.length,
      contentHash: hashValue(texts),
    },
  };
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function matchSpans(text, pattern) {
  return [...String(text || "").matchAll(pattern)].map(
    (match) => `${match.index}:${match.index + match[0].length}`,
  );
}

function uniqueSpanCount(spanGroups) {
  return new Set(spanGroups.flat()).size;
}

function collectVoiceMarkerEvidence(text) {
  const value = String(text || "");
  const xaiInlineSpans = (
    XAI_TTS_CAPABILITIES.speech_tags?.inline || []
  ).flatMap((tag) => matchSpans(value, new RegExp(escapeRegExp(tag), "giu")));
  const xaiWrappingSpans = (
    XAI_TTS_CAPABILITIES.speech_tags?.wrapping || []
  ).flatMap((tag) =>
    matchSpans(
      value,
      new RegExp(
        `<${escapeRegExp(tag)}>[\\s\\S]*?<\\/${escapeRegExp(tag)}>`,
        "giu",
      ),
    ),
  );
  const xaiWrappingTokenSpans = (
    XAI_TTS_CAPABILITIES.speech_tags?.wrapping || []
  ).flatMap((tag) =>
    matchSpans(
      value,
      new RegExp(`<\\/?${escapeRegExp(tag)}(?:\\s[^>]*)?>`, "giu"),
    ),
  );
  const xaiMalformedWrapping = Math.max(
    0,
    xaiWrappingTokenSpans.length - xaiWrappingSpans.length * 2,
  );
  const cartesiaValidatedControls = [];
  let cartesiaValidTokenCount = 0;
  const cartesiaValidSpans = [];
  const addCartesiaControls = (pattern, validate, summary, tokenCount = 1) => {
    for (const match of value.matchAll(pattern)) {
      if (!validate(match)) continue;
      cartesiaValidSpans.push(
        `${match.index}:${match.index + match[0].length}`,
      );
      cartesiaValidTokenCount += tokenCount;
      cartesiaValidatedControls.push(summary);
    }
  };
  const allowedCartesiaEmotions = new Set(
    (CARTESIA_TTS_CAPABILITIES.generation_config?.emotion?.values || []).map(
      (emotion) => String(emotion).toLowerCase(),
    ),
  );
  addCartesiaControls(
    /<emotion\s+value=(["'])([^"']+)\1\s*\/>/giu,
    (match) => allowedCartesiaEmotions.has(String(match[2]).toLowerCase()),
    {
      kind: "emotion",
      form: "state_change",
      balanced: true,
      attributeValid: true,
      valueAllowed: true,
    },
  );
  addCartesiaControls(
    /<emotion\s+value=(["'])([^"']+)\1\s*>[\s\S]*?<\/emotion\s*>/giu,
    (match) => allowedCartesiaEmotions.has(String(match[2]).toLowerCase()),
    {
      kind: "emotion",
      form: "scoped",
      balanced: true,
      attributeValid: true,
      valueAllowed: true,
    },
    2,
  );
  for (const kind of ["speed", "volume"]) {
    const range = CARTESIA_TTS_CAPABILITIES.generation_config?.[kind] || {};
    addCartesiaControls(
      new RegExp(`<${kind}\\s+ratio=(["'])([^"']+)\\1\\s*\\/>`, "giu"),
      (match) => {
        const ratio = Number(match[2]);
        return (
          Number.isFinite(ratio) &&
          ratio >= Number(range.min) &&
          ratio <= Number(range.max)
        );
      },
      {
        kind,
        form: "state_change",
        balanced: true,
        attributeValid: true,
        valueAllowed: true,
      },
    );
  }
  addCartesiaControls(
    /<break\s+time=(["'])(\d+(?:\.\d+)?(?:ms|s))\1\s*\/>/giu,
    () => true,
    {
      kind: "break",
      form: "state_change",
      balanced: true,
      attributeValid: true,
      valueAllowed: true,
    },
  );
  addCartesiaControls(
    /<spell>[\s\S]+?<\/spell\s*>/giu,
    () => true,
    {
      kind: "spell",
      form: "scoped",
      balanced: true,
      attributeValid: true,
      valueAllowed: true,
    },
    2,
  );
  const cartesiaTagNames = Object.keys(
    CARTESIA_TTS_CAPABILITIES.ssml_tags || {},
  );
  const cartesiaTagTokenSpans = matchSpans(
    value,
    new RegExp(
      `<\\/?(?:${cartesiaTagNames.map(escapeRegExp).join("|")})(?:\\s+[^<>]*)?\\s*\\/?>`,
      "giu",
    ),
  );
  const cartesiaMalformed = Math.max(
    0,
    cartesiaTagTokenSpans.length - cartesiaValidTokenCount,
  );
  const cartesiaNonverbalSpans = (
    CARTESIA_TTS_CAPABILITIES.nonverbal_markers || []
  ).flatMap((marker) =>
    matchSpans(value, new RegExp(escapeRegExp(marker), "giu")),
  );
  for (let index = 0; index < cartesiaNonverbalSpans.length; index += 1) {
    cartesiaValidatedControls.push({
      kind: "nonverbal",
      form: "exact_marker",
      balanced: true,
      attributeValid: true,
      valueAllowed: true,
    });
  }
  const chatterboxSpans = CHATTERBOX_INLINE_CONTROLS.flatMap((marker) =>
    matchSpans(value, new RegExp(escapeRegExp(marker), "giu")),
  );
  const structuralBracketSpans = matchSpans(
    value,
    /\[\s*\/?\s*[a-z][a-z '-]{2,63}\s*\]/giu,
  );
  const structuralAngleSpans = matchSpans(
    value,
    /<\/?[A-Za-z][A-Za-z0-9_-]*(?:\s+[^<>]*)?\s*\/?>/gu,
  );
  const xaiInline = xaiInlineSpans.length;
  const xaiWrapping = xaiWrappingSpans.length;
  const cartesiaTags = cartesiaValidSpans.length;
  const cartesiaNonverbal = cartesiaNonverbalSpans.length;
  const chatterbox = chatterboxSpans.length;
  return {
    xai: xaiInline + xaiWrapping,
    xaiInline,
    xaiWrapping,
    xaiMalformedWrapping,
    cartesia: cartesiaTags + cartesiaNonverbal,
    cartesiaMalformed,
    cartesiaValidatedControls,
    chatterbox,
    structuralBracket: structuralBracketSpans.length,
    structuralAngle: structuralAngleSpans.length,
    totalKnown:
      uniqueSpanCount([
        xaiInlineSpans,
        xaiWrappingSpans,
        cartesiaValidSpans,
        cartesiaTagTokenSpans,
        cartesiaNonverbalSpans,
        chatterboxSpans,
        structuralBracketSpans,
        structuralAngleSpans,
      ]) + xaiMalformedWrapping + cartesiaMalformed,
  };
}

function validateVoiceMarkerEvidence(testCase, responseText) {
  const fixture = voiceOutputFixtureFor(testCase);
  if (!fixture) return { evidence: null, failures: [] };
  const counts = collectVoiceMarkerEvidence(responseText);
  const providerCount =
    fixture.provider === "xai"
      ? counts.xai
      : fixture.provider === "cartesia"
        ? counts.cartesia
        : fixture.provider.includes("chatterbox")
          ? counts.chatterbox
          : 0;
  const failures = [];
  if (fixture.markerExpectation === "present" && providerCount === 0) {
    failures.push(`voice_${fixture.provider}_supported_marker_missing`);
  }
  if (fixture.markerExpectation === "absent" && counts.totalKnown > 0) {
    failures.push(`voice_${fixture.provider}_unexpected_marker`);
  }
  if (counts.xaiMalformedWrapping > 0) {
    failures.push("voice_xai_malformed_wrapping_marker");
  }
  if (fixture.provider === "cartesia" && counts.cartesiaMalformed > 0) {
    failures.push("voice_cartesia_malformed_marker");
  }
  const malformedProviderMarkerCount =
    fixture.provider === "xai"
      ? counts.xaiMalformedWrapping
      : fixture.provider === "cartesia"
        ? counts.cartesiaMalformed
        : 0;
  return {
    evidence: {
      provider: fixture.provider,
      markerExpectation: fixture.markerExpectation,
      providerMarkerCount: providerCount,
      providerGrammarValid: malformedProviderMarkerCount === 0,
      malformedProviderMarkerCount,
      validatedControls:
        fixture.provider === "cartesia"
          ? counts.cartesiaValidatedControls
          : [],
      counts,
    },
    failures,
  };
}

function feelingsHeaders(token, body = false) {
  return {
    Authorization: `Bearer ${token}`,
    ...(body ? { "Content-Type": "application/json" } : {}),
  };
}

async function readFeelingsFixtureState(args, token) {
  const response = await fetchJson(`${args.apiBase}/api/viventium/feelings`, {
    headers: feelingsHeaders(token),
  });
  if (!response.ok || !response.body?.state) {
    throw new Error(`feelings_fixture_read_http_${response.status}`);
  }
  return response.body;
}

async function patchFeelingsFixture(
  args,
  token,
  pathName,
  expectedVersion,
  update,
) {
  const response = await fetchJson(
    `${args.apiBase}/api/viventium/feelings${pathName}`,
    {
      method: "PATCH",
      headers: feelingsHeaders(token, true),
      body: JSON.stringify({ expectedVersion, ...update }),
    },
    20_000,
  );
  if (!response.ok || !response.body?.state) {
    throw new Error(`feelings_fixture_write_http_${response.status}`);
  }
  return response.body;
}

function publicFeelingsState(state) {
  return {
    version: state.version,
    snapshotHash: state.snapshotHash,
    enabled: state.enabled,
    reactionActivationMode: state.reactionActivationMode,
    trailLength: Array.isArray(state.trail) ? state.trail.length : 0,
    trailCursorTimestamp: Array.isArray(state.trail)
      ? state.trail[state.trail.length - 1]?.timestamp || null
      : null,
    rangePromptOverrideCount: Number(state.rangePromptOverrideCount || 0),
    activeRangePromptOverrideCount: Number(
      state.activeRangePromptOverrideCount || 0,
    ),
    activeRangePromptOverrideChars: Number(
      state.activeRangePromptOverrideChars || 0,
    ),
    bands: Object.fromEntries(
      Object.entries(state.bands || {}).map(([band, value]) => [
        band,
        {
          current: Number(Number(value.current).toFixed(2)),
          nature: Number(Number(value.baseline).toFixed(2)),
        },
      ]),
    ),
  };
}

function buildIsolatedFeelingsFixtureSet({ state, fixture, now = new Date() }) {
  const updatedAt = new Date(now);
  if (!Number.isFinite(updatedAt.getTime())) {
    throw new Error("feelings_fixture_invalid_timestamp");
  }
  const current = fixture?.current || {};
  const nature = fixture?.nature || {};
  const bands = Object.fromEntries(
    Object.entries(state?.bands || {}).map(([band, value]) => {
      const nextCurrent = current[band];
      const nextNature = nature[band];
      return [
        band,
        {
          ...value,
          current:
            nextCurrent != null && Number.isFinite(Number(nextCurrent))
              ? Number(nextCurrent)
              : Number(value.current),
          baseline:
            nextNature != null && Number.isFinite(Number(nextNature))
              ? Number(nextNature)
              : Number(value.baseline),
          updatedAt,
        },
      ];
    }),
  );
  return {
    bands,
    rangePromptOverrides: structuredClone(
      fixture?.rangePromptOverrides || {},
    ),
    trail: [],
    processedStimulusKeys: [],
    innerState: null,
  };
}

async function applyFeelingsFixture({ args, token, testCase }) {
  const fixture = feelingsFixtureFor(testCase);
  if (!fixture) return null;
  const originalPayload = await readFeelingsFixtureState(args, token);
  const restoreState = structuredClone(originalPayload.state);
  let payload = originalPayload;
  const profile = {
    enabled: fixture.enabled !== false,
    reactionActivationMode: fixture.reactionActivationMode || "disabled",
  };
  payload = await patchFeelingsFixture(
    args,
    token,
    "/profile",
    payload.state.version,
    profile,
  );
  const current = fixture.current || {};
  const nature = fixture.nature || {};
  for (const band of (payload.definitions || []).map(
    (definition) => definition.id,
  )) {
    const update = {};
    if (Number.isFinite(Number(current[band])))
      update.current = Number(current[band]);
    if (Number.isFinite(Number(nature[band])))
      update.baseline = Number(nature[band]);
    if (!Object.keys(update).length) continue;
    payload = await patchFeelingsFixture(
      args,
      token,
      `/bands/${band}`,
      payload.state.version,
      update,
    );
  }
  const targetRangePromptOverrides = fixture.rangePromptOverrides || {};
  for (const definition of payload.definitions || []) {
    for (const level of definition.levels || []) {
      const existing =
        payload.state.rangePromptOverrides?.[definition.id]?.[level.id] || "";
      const desired =
        typeof targetRangePromptOverrides?.[definition.id]?.[level.id] ===
        "string"
          ? targetRangePromptOverrides[definition.id][level.id].trim()
          : "";
      if (existing === desired) continue;
      payload = await patchFeelingsFixture(
        args,
        token,
        `/bands/${definition.id}`,
        payload.state.version,
        {
          rangePromptOverride: {
            levelId: level.id,
            instruction: desired || null,
          },
        },
      );
    }
  }
  return {
    restoreState,
    configuredState: payload.state,
    evidence: {
      fixture: "feelings_state",
      configured: publicFeelingsState(payload.state),
    },
  };
}

async function applyFeelingsFixtureWithRetry(params, maxAttempts = 20) {
  let lastError = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await applyFeelingsFixture(params);
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 750));
      }
    }
  }
  throw lastError || new Error("Feelings fixture setup failed");
}

async function restoreFeelingsFixture({ args, token, restoreState }) {
  if (!restoreState) return;
  let payload = await readFeelingsFixtureState(args, token);
  for (const band of (payload.definitions || []).map(
    (definition) => definition.id,
  )) {
    const original = restoreState.bands?.[band];
    if (!original) continue;
    payload = await patchFeelingsFixture(
      args,
      token,
      `/bands/${band}`,
      payload.state.version,
      {
        current: Number(original.current),
        baseline: Number(original.baseline),
        halfLifeMinutes: Number(original.halfLifeMinutes),
        enabled: original.enabled !== false,
      },
    );
  }
  for (const definition of payload.definitions || []) {
    for (const level of definition.levels || []) {
      const existing =
        payload.state.rangePromptOverrides?.[definition.id]?.[level.id] || "";
      const original =
        restoreState.rangePromptOverrides?.[definition.id]?.[level.id] || "";
      if (existing === original) continue;
      payload = await patchFeelingsFixture(
        args,
        token,
        `/bands/${definition.id}`,
        payload.state.version,
        {
          rangePromptOverride: {
            levelId: level.id,
            instruction: original || null,
          },
        },
      );
    }
  }
  await patchFeelingsFixture(args, token, "/profile", payload.state.version, {
    enabled: restoreState.enabled === true,
    reactionActivationMode: restoreState.reactionActivationMode || "always",
    reactionInstruction: restoreState.reactionInstruction,
  });
}

async function restoreFeelingsFixtureWithRetry({
  args,
  token,
  restoreState,
  maxAttempts = 20,
}) {
  let lastError = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      await restoreFeelingsFixture({ args, token, restoreState });
      return attempt;
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 750));
      }
    }
  }
  throw lastError || new Error("Feelings fixture restoration failed");
}

async function observeFeelingsReaction({
  args,
  token,
  beforeState,
  forbiddenInnerStateTokens = [],
  timeoutMs = 45_000,
}) {
  const startedAt = Date.now();
  let latest = null;
  while (Date.now() - startedAt < timeoutMs) {
    latest = (await readFeelingsFixtureState(args, token)).state;
    if (
      latest.version > beforeState.version &&
      latest.reactionHealth?.status !== "running" &&
      latest.reactionHealth?.status !== "never"
    ) {
      break;
    }
    if (latest.reactionHealth?.status === "degraded") break;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!latest) return null;
  const bands = Object.fromEntries(
    Object.keys(beforeState.bands || {}).map((band) => {
      const before = beforeState.bands[band];
      const after = latest.bands?.[band];
      return [
        band,
        {
          currentDelta: Number(
            (Number(after?.current) - Number(before?.current)).toFixed(2),
          ),
          natureDelta: Number(
            (Number(after?.baseline) - Number(before?.baseline)).toFixed(2),
          ),
        },
      ];
    }),
  );
  const innerStateText =
    typeof latest.innerState?.text === "string" ? latest.innerState.text : "";
  const normalizedInnerState = innerStateText.toLocaleLowerCase();
  const newestTrail = (latest.trail || []).filter(
    (entry) =>
      new Date(entry.timestamp).getTime() >
      new Date(beforeState.trailCursorTimestamp || 0).getTime(),
  );
  return {
    observedMs: Date.now() - startedAt,
    status: latest.reactionHealth?.status || "unknown",
    lastDurationMs: latest.reactionHealth?.lastDurationMs ?? null,
    fallbackUsed: latest.reactionHealth?.lastFallbackUsed === true,
    usedProvider: latest.reactionHealth?.lastUsedProvider || null,
    usedModel: latest.reactionHealth?.lastUsedModel || null,
    primaryErrorClass: latest.reactionHealth?.lastPrimaryErrorClass || null,
    versionBefore: beforeState.version,
    versionAfter: latest.version,
    natureUnchanged: Object.values(bands).every(
      (band) => Math.abs(band.natureDelta) < 0.01,
    ),
    bands,
    newestCauses: newestTrail.map((entry) => entry.cause).filter(Boolean),
    newestStrengths: newestTrail.map((entry) => entry.strength).filter(Boolean),
    innerStateText,
    innerStateGeneratedAt: latest.innerState?.generatedAt || null,
    innerStateLength: innerStateText.length,
    innerStateSingleLine: !/[\r\n]/u.test(innerStateText),
    innerStateWithinLimit:
      innerStateText.length > 0 && innerStateText.length <= 280,
    innerStateForbiddenTokenMatches: forbiddenInnerStateTokens.filter(
      (token) =>
        typeof token === "string" &&
        token.length > 0 &&
        normalizedInnerState.includes(token.toLocaleLowerCase()),
    ),
  };
}

function validateFeelingsReactionEvidence(feelingsFixture, evidence) {
  if (!feelingsFixture?.observeReaction) return [];
  if (!evidence) return ["feelings_reaction_not_observed"];
  const failures = [];
  if (evidence.status !== "healthy") {
    failures.push(`feelings_reaction_status_${evidence.status || "unknown"}`);
  }
  if (evidence.versionAfter <= evidence.versionBefore) {
    failures.push("feelings_reaction_version_not_advanced");
  }
  if (!evidence.natureUnchanged) {
    failures.push("feelings_reaction_changed_nature");
  }
  if (!evidence.innerStateWithinLimit || !evidence.innerStateSingleLine) {
    failures.push("feelings_inner_state_invalid");
  }
  if (
    feelingsFixture.requireNoForbiddenInnerStateTokens === true &&
    evidence.innerStateForbiddenTokenMatches?.length > 0
  ) {
    failures.push("feelings_inner_state_contains_forbidden_token");
  }
  for (const [band, direction] of Object.entries(
    feelingsFixture.requiredCurrentDirections || {},
  )) {
    const delta = Number(evidence.bands?.[band]?.currentDelta || 0);
    if (
      (direction === "up" && delta <= 0) ||
      (direction === "down" && delta >= 0)
    ) {
      failures.push(`feelings_${band}_did_not_move_${direction}`);
    }
  }
  for (const [band, minimum] of Object.entries(
    feelingsFixture.minimumAbsoluteCurrentDelta || {},
  )) {
    const magnitude = Math.abs(
      Number(evidence.bands?.[band]?.currentDelta || 0),
    );
    if (magnitude < Number(minimum)) {
      failures.push(`feelings_${band}_movement_below_${minimum}`);
    }
  }
  if (feelingsFixture.requireNoCurrentChange === true) {
    const currentChanged = Object.values(evidence.bands || {}).some(
      (band) => Math.abs(Number(band.currentDelta || 0)) >= 0.01,
    );
    if (currentChanged)
      failures.push("feelings_current_changed_for_inert_case");
  }
  if (feelingsFixture.requiredCausesAny?.length > 0) {
    const causes = new Set(evidence.newestCauses || []);
    if (!feelingsFixture.requiredCausesAny.some((cause) => causes.has(cause))) {
      failures.push("feelings_required_cause_missing");
    }
  }
  return failures;
}

async function applyStarterMorningBriefingFixture({
  args,
  env,
  userId,
  agentId,
}) {
  if (!userId) {
    return { ok: false, reason: "missing_qa_user_id" };
  }

  const timezone =
    process.env.VIVENTIUM_EVAL_QA_TIMEZONE ||
    env.VIVENTIUM_DEFAULT_TIMEZONE ||
    "UTC";
  const baseUrl = schedulingBaseUrl(env);
  const bootstrapPayload = {
    user_id: userId,
    template_id: STARTER_MORNING_BRIEFING_TEMPLATE_ID,
    agent_id: agentId || args.agentId,
    channels: null,
    timezone,
    time: process.env.VIVENTIUM_EVAL_MORNING_BRIEFING_TIME || "08:00",
    conversation_policy: "same",
    prompt: STARTER_MORNING_BRIEFING_BASELINE_PROMPT,
    metadata: {
      template_id: STARTER_MORNING_BRIEFING_TEMPLATE_ID,
      bootstrap_source: "prompt_architecture_eval_fixture",
    },
  };

  const bootstrap = await fetchJson(
    `${baseUrl}/internal/bootstrap-schedule`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bootstrapPayload),
    },
    10_000,
  ).catch((error) => ({
    ok: false,
    status: 0,
    body: { reason: error.message },
  }));

  const primaryUpdate = updateStarterPromptAcrossDbCandidates(env, {
    userId,
    agentId: agentId || args.agentId,
  });
  const mirrorUpdate = env.SCHEDULING_DB_MIRROR_PATH
    ? sqliteUpdateStarterPrompt(env.SCHEDULING_DB_MIRROR_PATH, {
        userId,
        agentId: agentId || args.agentId,
      })
    : { ok: true, skipped: true };

  return {
    ok: primaryUpdate.ok,
    fixture: "starter_morning_briefing_baseline_without_blockers",
    bootstrapStatus: bootstrap.status,
    bootstrapBodyStatus: scrubForPublic(
      bootstrap.body?.status || bootstrap.body?.reason || "",
    ),
    primaryUpdate,
    mirrorUpdate,
  };
}

function stableStringify(value) {
  return JSON.stringify(value, Object.keys(value || {}).sort());
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function memoryRecallBankFingerprint(promptBank) {
  const family = (promptBank?.families || []).find(
    (candidate) => candidate?.id === "memory_recall",
  );
  if (!family) {
    throw new Error("memory_recall_bank_missing");
  }
  const cases = (family.cases || []).filter(
    (testCase) =>
      typeof testCase?.fixture?.conversationRecall?.coverageCategory === "string",
  );
  const payload = {
    bankVersion: family.bankVersion,
    cases,
  };
  return {
    bankVersion: family.bankVersion,
    bankHash: crypto
      .createHash("sha256")
      .update(canonicalJson(payload))
      .digest("hex")
      .slice(0, 16),
    caseCount: cases.length,
    coverageCategories: cases
      .map((testCase) => testCase.fixture.conversationRecall.coverageCategory)
      .sort(),
  };
}

function validateFrozenMemoryRecallBank(promptBank) {
  const bank = memoryRecallBankFingerprint(promptBank);
  if (bank.bankVersion !== MEMORY_RECALL_BANK_VERSION) {
    throw new Error(
      `Frozen continuity bank version drift: expected ${MEMORY_RECALL_BANK_VERSION}, received ${bank.bankVersion || "missing"}`,
    );
  }
  if (bank.bankHash !== FROZEN_MEMORY_RECALL_BANK_HASH) {
    throw new Error(
      `Frozen continuity bank drift: expected ${FROZEN_MEMORY_RECALL_BANK_HASH}, received ${bank.bankHash}; bump the version and review the new hash before live runs`,
    );
  }
  return bank;
}

function hashValue(value, length = 16) {
  const text = typeof value === "string" ? value : stableStringify(value);
  return crypto
    .createHash("sha256")
    .update(text || "")
    .digest("hex")
    .slice(0, length);
}

function hashFileIfPresent(filePath) {
  try {
    return crypto
      .createHash("sha256")
      .update(fs.readFileSync(filePath))
      .digest("hex")
      .slice(0, 16);
  } catch (_error) {
    return null;
  }
}

function scrubForPublic(value) {
  if (value == null) {
    return "";
  }
  return String(value)
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "[email]")
    .replace(
      /(?:file:\/\/)?(?:\/Users|\/home|\/tmp|\/var\/folders|\/private\/var\/folders|\/opt|\/etc)\/[^\r\n"'`<>]+/g,
      "[local_path]",
    )
    .replace(/~\/[^\r\n"'`<>]+/g, "[local_path]")
    .replace(/\b[A-Za-z]:\\[^\r\n"'`<>]+/g, "[local_path]")
    .replace(/\\\\[A-Za-z0-9_.-]+\\[^\r\n"'`<>]+/g, "[local_path]")
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b/gi, "Bearer [secret]")
    .replace(
      /\b(?:sk|pk|rk|ghp|gho|github_pat|xox[baprs]?)-[A-Za-z0-9_*\-]{8,}\b/g,
      "[secret]",
    )
    .replace(
      /\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret)=([^&\s"'`<>]+)/gi,
      "$1=[secret]",
    )
    .replace(
      /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi,
      "[uuid]",
    )
    .replace(/\b[0-9a-f]{24}\b/gi, "[object_id]")
    .replace(/\b\d{10,}\b/g, "[numeric_id]");
}

function responseTextForJudge(value) {
  return scrubForPublic(stripDeliveryControlsForPreview(value));
}

async function fetchJson(url, options = {}, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "User-Agent": BROWSER_USER_AGENT,
        ...(options.headers || {}),
      },
    });
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch (_error) {
      body = { raw: text.slice(0, 500) };
    }
    return {
      ok: response.ok,
      status: response.status,
      body,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchText(url, options = {}, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return {
      ok: response.ok,
      status: response.status,
      text: await response.text(),
    };
  } finally {
    clearTimeout(timer);
  }
}

function runtimeIdentityVerdict(configResponse) {
  const config = configResponse.body || {};
  const appTitle = String(config.appTitle || "");
  const interfaceConfig = config.interface || {};
  const defaultAgent = String(interfaceConfig.defaultAgent || "");
  const connectedAccountsEnabled =
    config.viventiumConnectedAccountsEnabled === true;
  const hasViventiumTitle = appTitle === "Viventium";
  const hasDefaultAgent = defaultAgent === MAIN_AGENT_ID;
  const ok =
    configResponse.ok &&
    hasViventiumTitle &&
    hasDefaultAgent &&
    connectedAccountsEnabled;
  const reasons = [];

  if (!configResponse.ok) {
    reasons.push(`api_config_http_${configResponse.status}`);
  }
  if (!hasViventiumTitle) {
    reasons.push("app_title_not_viventium");
  }
  if (!hasDefaultAgent) {
    reasons.push("default_agent_not_main_viventium");
  }
  if (!connectedAccountsEnabled) {
    reasons.push("connected_account_mode_not_enabled");
  }

  return {
    ok,
    reasons,
    public: {
      appTitle: scrubForPublic(appTitle || "missing"),
      defaultAgentHash: defaultAgent ? hashValue(defaultAgent) : "missing",
      connectedAccountsEnabled,
    },
  };
}

function loadSourceHashes() {
  const sourceAgent = path.join(
    LIBRECHAT_ROOT,
    "viventium",
    "source_of_truth",
    "local.viventium-agents.yaml",
  );
  const sourceLibreChat = path.join(
    LIBRECHAT_ROOT,
    "viventium",
    "source_of_truth",
    "local.librechat.yaml",
  );
  const compiled = path.join(
    REPO_ROOT,
    ".viventium",
    "runtime",
    "isolated",
    "librechat.generated.yaml",
  );

  return {
    source_agent: hashFileIfPresent(sourceAgent),
    source_librechat: hashFileIfPresent(sourceLibreChat),
    compiled_librechat: hashFileIfPresent(compiled),
  };
}

function debugLocalPromptFrameEnabled() {
  return process.env.VIVENTIUM_PROMPT_FRAME_DEBUG_LOCAL === "1";
}

function promptFrameLogFiles() {
  const root = path.join(PRIVATE_ROOT, "prompt-observability", "frame-logs");
  const files = [];
  if (fs.existsSync(root)) {
    for (const day of fs.readdirSync(root, { withFileTypes: true })) {
      if (!day.isDirectory()) {
        continue;
      }
      const dayDir = path.join(root, day.name);
      for (const entry of fs.readdirSync(dayDir, { withFileTypes: true })) {
        if (entry.isFile() && entry.name.endsWith(".jsonl")) {
          files.push(path.join(dayDir, entry.name));
        }
      }
    }
  }

  // The stable local runtime intentionally keeps the private frame-file transport off by
  // default, while its public-safe metadata still lands in the normal API debug log. Read that
  // real owning log too so an exact-model run cannot silently report zero prompt/Feelings frames.
  const runtimeLogDir =
    String(process.env.VIVENTIUM_EVAL_RUNTIME_LOG_DIR || "").trim() ||
    path.join(LIBRECHAT_ROOT, "api", "logs");
  if (fs.existsSync(runtimeLogDir)) {
    for (const entry of fs.readdirSync(runtimeLogDir, {
      withFileTypes: true,
    })) {
      if (entry.isFile() && /^debug-\d{4}-\d{2}-\d{2}\.log$/.test(entry.name)) {
        files.push(path.join(runtimeLogDir, entry.name));
      }
    }
  }
  return [...new Set(files)].sort();
}

function capturePromptFrameCursor() {
  const cursor = {};
  for (const filePath of promptFrameLogFiles()) {
    try {
      cursor[filePath] = fs.statSync(filePath).size;
    } catch (_error) {
      cursor[filePath] = 0;
    }
  }
  return cursor;
}

function summarizePromptFrameDelta(cursor) {
  const frames = [];
  const truncatedFrames = [];
  const feelingsChunks = new Map();
  const promptField = (line, field) => {
    const match = line.match(new RegExp(`"${field}":"([^"]*)"`));
    return match ? match[1] : "";
  };
  const summarizeFrame = (frame, source) => ({
    prompt_family: scrubForPublic(frame.prompt_family || ""),
    surface: scrubForPublic(frame.surface || ""),
    provider_hash: frame.provider ? hashValue(frame.provider) : "missing",
    model_hash: frame.model ? hashValue(frame.model) : "missing",
    layer_token_estimates: frame.layer_token_estimates || {},
    source_hashes: frame.source_hashes || {},
    mcp_instruction_sources: frame.mcp_instruction_sources || {},
    ...(source ? { source } : {}),
  });
  const feelingEvidenceFields = new Set([
    "enabled",
    "scope",
    "snapshotHash",
    "injected",
    "presentInFinalRun",
    "capsuleOccurrenceCount",
    "placement",
    "trailingInstructionChars",
  ]);
  for (const filePath of promptFrameLogFiles()) {
    let start = cursor[filePath] || 0;
    let end = 0;
    try {
      end = fs.statSync(filePath).size;
    } catch (_error) {
      continue;
    }
    if (end <= start) {
      continue;
    }
    if (start > end) {
      start = 0;
    }
    const fd = fs.openSync(filePath, "r");
    try {
      const buffer = Buffer.alloc(end - start);
      fs.readSync(fd, buffer, 0, buffer.length, start);
      for (const line of buffer.toString("utf8").split(/\r?\n/)) {
        if (!line.trim()) {
          continue;
        }
        const runtimeRoute = line.match(
          /\[PromptFrameRouteTelemetry\]\s+(\{.*\})\s*$/,
        );
        if (runtimeRoute) {
          try {
            const route = JSON.parse(runtimeRoute[1]);
            const routeHash = (value) =>
              /^[0-9a-f]{16}$/.test(String(value || ""))
                ? `h${String(value)}`
                : "missing";
            frames.push({
              prompt_family: scrubForPublic(route.f || ""),
              surface: "",
              provider_hash: routeHash(route.p),
              model_hash: routeHash(route.m),
              layer_token_estimates: {},
              source_hashes: {},
              mcp_instruction_sources: {},
              source: "runtime_route_log",
            });
          } catch (_error) {
            // Ignore a partial line from the active Winston writer.
          }
          continue;
        }
        const runtimePrompt = line.match(/\[PromptFrameTelemetry\]\s+(\{.*)$/);
        if (runtimePrompt) {
          try {
            frames.push(
              summarizeFrame(JSON.parse(runtimePrompt[1]), "runtime_text_log"),
            );
          } catch (_error) {
            const promptFamily = promptField(line, "prompt_family");
            const surface = promptField(line, "surface");
            if (promptFamily || surface) {
              truncatedFrames.push(
                summarizeFrame(
                  { prompt_family: promptFamily, surface },
                  "runtime_text_log_truncated",
                ),
              );
            }
          }
          continue;
        }

        const runtimeFeelings = line.match(
          /\[VIVENTIUM\]\[Feelings\]\s+(\{.*\})\s*$/,
        );
        if (runtimeFeelings) {
          try {
            const chunk = JSON.parse(runtimeFeelings[1]);
            const key = `${chunk.r || ""}:${chunk.i || ""}`;
            const aggregate = feelingsChunks.get(key) || {};
            if (chunk.event) aggregate.event = chunk.event;
            for (const [field, value] of Object.entries(chunk)) {
              if (feelingEvidenceFields.has(field)) aggregate[field] = value;
            }
            feelingsChunks.set(key, aggregate);
          } catch (_error) {
            // Ignore a partial line from the active Winston writer.
          }
          continue;
        }

        if (filePath.endsWith(".jsonl")) {
          try {
            const frame = JSON.parse(line);
            frames.push(summarizeFrame(frame, "private_frame_log"));
          } catch (_error) {
            // Ignore partial lines from an active async writer.
          }
        }
      }
    } finally {
      fs.closeSync(fd);
    }
  }
  for (const truncatedFrame of truncatedFrames) {
    const matchingRouteFrames = frames.filter(
      (frame) =>
        frame.source === "runtime_route_log" &&
        frame.prompt_family === truncatedFrame.prompt_family &&
        (!frame.surface || frame.surface === truncatedFrame.surface),
    );
    if (matchingRouteFrames.length) {
      for (const routeFrame of matchingRouteFrames) {
        if (!routeFrame.surface) routeFrame.surface = truncatedFrame.surface;
      }
    } else {
      frames.push(truncatedFrame);
    }
  }
  const maxLayerTokens = {};
  for (const frame of frames) {
    for (const [layer, tokens] of Object.entries(
      frame.layer_token_estimates || {},
    )) {
      maxLayerTokens[layer] = Math.max(
        maxLayerTokens[layer] || 0,
        Number(tokens) || 0,
      );
    }
  }
  const heavyLayers = Object.entries(maxLayerTokens)
    .filter(([, tokens]) => tokens >= 1000)
    .map(([layer, tokens]) => ({ layer, tokens }))
    .sort((left, right) => right.tokens - left.tokens);
  const feelingsFinalRun = [...feelingsChunks.values()]
    .filter((event) => event.event === "feelings.inject.final_run")
    .map(({ event: _event, ...fields }) => fields)
    .slice(0, 20);
  return scrubForPublic(
    JSON.stringify(
      {
        prompt_frames: frames.slice(0, 20),
        feelings_final_run: feelingsFinalRun,
        prompt_budget_analysis: {
          frame_count: frames.length,
          max_layer_tokens: maxLayerTokens,
          heavy_layers_over_1000_tokens: heavyLayers,
          budget_review_required: heavyLayers.length > 0,
        },
      },
      null,
      2,
    ),
  );
}

function flattenPromptCases(promptBank) {
  return (promptBank.families || []).flatMap((family) =>
    (family.cases || []).map((testCase) => ({
      familyId: family.id,
      familyGoal: family.goal,
      ...testCase,
      decisionQualityContract: {
        ...(family.decisionQualityContract || {}),
        ...(testCase.decisionQualityContract || {}),
      },
      evalIsolation: {
        ...(family.evalIsolation || {}),
        ...(testCase.evalIsolation || {}),
      },
      interCaseDelayMs:
        testCase.interCaseDelayMs ?? family.interCaseDelayMs ?? 0,
      promptRefs: [
        ...new Set([
          ...(family.promptRefs || family.prompt_refs || []).map((item) =>
            String(item),
          ),
          ...(testCase.promptRefs || testCase.prompt_refs || []).map((item) =>
            String(item),
          ),
        ]),
      ],
    })),
  );
}

function runnablePromptCases(promptBank, filters = {}) {
  return flattenPromptCases(promptBank).filter((testCase) =>
    caseMatchesFilters(testCase, filters),
  );
}

function caseMatchesFilters(testCase, filters = {}) {
  if (filters.family && testCase.familyId !== filters.family) {
    return false;
  }
  if (filters.caseId && testCase.id !== filters.caseId) {
    return false;
  }
  if (filters.caseIds?.length && !filters.caseIds.includes(testCase.id)) {
    return false;
  }
  if (filters.surface && (testCase.surface || "web") !== filters.surface) {
    return false;
  }
  if (
    filters.promptId &&
    filters.promptId !== "main.conscious_agent" &&
    !(testCase.promptRefs || []).includes(filters.promptId)
  ) {
    return false;
  }
  return true;
}

function structuredDecisionCaseText(testCase) {
  if (
    !testCase?.question ||
    !testCase?.evidencePacket ||
    Object.keys(testCase.evidencePacket).length === 0
  ) {
    return null;
  }
  const evidenceLines = Object.entries(testCase.evidencePacket).map(
    ([label, value]) => `- ${label}: ${String(value)}`,
  );
  return [
    `User position: ${testCase.userPosition || "No position stated."}`,
    `Question: ${testCase.question}`,
    "Evidence packet:",
    ...evidenceLines,
    `Response instructions: ${testCase.responseInstructions || "Give the strongest conclusion the evidence supports and the best next action."}`,
  ].join("\n");
}

function buildCaseText(testCase, { includeSetup = true } = {}) {
  return [
    testCase.context,
    includeSetup ? testCase.setup : null,
    structuredDecisionCaseText(testCase) || testCase.prompt,
  ]
    .filter(Boolean)
    .join("\n\n");
}

function buildChatPayload(testCase, args, overrides = {}) {
  const messageId = overrides.messageId || crypto.randomUUID();
  const text = overrides.text ?? buildCaseText(testCase);
  const surface = testCase.surface || "web";
  const inputMode =
    surface === "voice" || surface === "wing"
      ? "voice_call"
      : surface === "listen_only"
        ? "listen_only"
        : "text";
  const voiceOutput = voiceOutputFixtureFor(testCase);
  return {
    text,
    sender: "User",
    clientTimestamp: new Date().toISOString(),
    clientTimezone: "UTC",
    isCreatedByUser: true,
    parentMessageId: overrides.parentMessageId || NO_PARENT,
    conversationId: overrides.conversationId || "new",
    messageId,
    responseMessageId: `${messageId}_`,
    endpoint: "agents",
    endpointType: "agents",
    agent_id: args.agentId,
    model: args.agentId,
    viventiumSurface: surface,
    viventiumInputMode: inputMode,
    ...(voiceOutput
      ? {
          voiceMode: surface === "voice",
          voiceProvider: voiceOutput.provider,
          ...(surface === "telegram" ? { telegramAudioRequested: true } : {}),
        }
      : {}),
    viventiumListenOnly: surface === "listen_only",
    isTemporary: overrides.isTemporary ?? true,
    ...(testCase.evalIsolation && Object.keys(testCase.evalIsolation).length > 0
      ? {
          viventiumEvalIsolation: testCase.evalIsolation,
          suppressBackgroundCortices:
            testCase.evalIsolation.backgroundCortices === true,
        }
      : {}),
  };
}

function normalizeSeedPrompts(testCase) {
  if (Array.isArray(testCase.seed_prompts)) {
    return testCase.seed_prompts
      .map((item) => String(item || "").trim())
      .filter(Boolean);
  }
  return [];
}

function parseSseBlock(block) {
  const lines = block.split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  try {
    return JSON.parse(dataLines.join("\n"));
  } catch (_error) {
    return { raw: dataLines.join("\n") };
  }
}

function extractTextFromContent(content) {
  if (typeof content === "string") {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part?.type === "text") {
          if (typeof part.text === "string") {
            return part.text;
          }
          if (typeof part.text?.value === "string") {
            return part.text.value;
          }
        }
        return "";
      })
      .filter(Boolean)
      .join("\n\n");
  }
  if (typeof content?.text === "string") {
    return content.text;
  }
  return "";
}

function extractVisibleText(events) {
  const finalEvent = [...events]
    .reverse()
    .find((event) => event && event.final != null);
  const responseMessage =
    finalEvent?.responseMessage || finalEvent?.message || null;
  const finalText =
    responseMessage?.text ||
    responseMessage?.textOverride ||
    extractTextFromContent(responseMessage?.content);
  if (finalText) {
    return finalText;
  }
  return events
    .map(
      (event) =>
        event?.text ||
        event?.delta ||
        event?.content ||
        event?.response?.text ||
        event?.responseMessage?.text ||
        extractTextFromContent(event?.responseMessage?.content) ||
        "",
    )
    .filter((value) => typeof value === "string")
    .join("");
}

function extractRawStreamedText(events) {
  return (events || [])
    .filter((event) => event?.event === "on_message_delta")
    .map((event) => {
      const delta = event?.data?.delta;
      return (
        extractTextFromContent(delta?.content) ||
        (typeof delta?.text === "string" ? delta.text : "")
      );
    })
    .filter(Boolean)
    .join("");
}

function extractFinalMeta(events) {
  const finalEvent = [...(events || [])]
    .reverse()
    .find((event) => event && event.final != null);
  return {
    conversationId:
      finalEvent?.conversation?.conversationId ||
      finalEvent?.responseMessage?.conversationId ||
      finalEvent?.message?.conversationId ||
      "",
    responseMessageId:
      finalEvent?.responseMessage?.messageId ||
      finalEvent?.message?.messageId ||
      "",
    requestMessageId: finalEvent?.requestMessage?.messageId || "",
  };
}

function contentToText(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part?.type === "text") {
          if (typeof part.text === "string") {
            return part.text;
          }
          if (typeof part.text?.value === "string") {
            return part.text.value;
          }
        }
        if (
          part?.type === "cortex_insight" &&
          typeof part.insight === "string"
        ) {
          return `[${part.cortex_name || "cortex"} insight] ${part.insight}`;
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (typeof value.text === "string") {
    return value.text;
  }
  return "";
}

function hasCortexActivation(events) {
  return (events || []).some((event) => {
    if (event?.event === "on_cortex_update") {
      return true;
    }
    return JSON.stringify(event || {}).includes("cortex_activation");
  });
}

function extractOpenAIOutputText(body) {
  if (typeof body?.output_text === "string") {
    return body.output_text;
  }
  if (Array.isArray(body?.output)) {
    return body.output
      .flatMap((item) => item?.content || [])
      .map((part) => part?.text || part?.content || "")
      .filter(Boolean)
      .join("\n");
  }
  if (typeof body?.choices?.[0]?.message?.content === "string") {
    return body.choices[0].message.content;
  }
  return "";
}

function parseJsonObject(text) {
  try {
    return JSON.parse(text);
  } catch (_error) {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start >= 0 && end > start) {
      return JSON.parse(text.slice(start, end + 1));
    }
    throw _error;
  }
}

function caseAllowsEmptyResponse(testCase) {
  return (
    testCase.expected_surface === "{NTA}" ||
    testCase.expected_decision === "suppress" ||
    testCase.surface === "listen_only" ||
    testCase.surface === "wing"
  );
}

function caseAllowsDuplicateResponse(testCase) {
  return (
    caseAllowsEmptyResponse(testCase) ||
    testCase.allow_duplicate_response_hash === true
  );
}

function caseAllowsUnresolvedAsync(testCase) {
  return testCase.allow_unresolved_async === true;
}

function isPendingCortexStatus(status) {
  return ["activating", "brewing", "running", "pending"].includes(
    String(status || "").trim(),
  );
}

function resultHasResolvedRuntimeHoldEvidence(result) {
  if (!result?.hasRuntimeHold || !result?.hasCortexActivation) {
    return false;
  }
  const evidence = result.postCaseEvidence || {};
  return (
    Number(evidence.delayedMessageCount || 0) > 0 ||
    Number(evidence.cortexInsightCount || 0) > 0
  );
}

function hasRuntimeHold(events) {
  return (events || []).some((event) => {
    if (
      event?.final !== true ||
      !Array.isArray(event.responseMessage?.content)
    ) {
      return false;
    }
    return event.responseMessage.content.some((part) =>
      Boolean(part?.viventium_runtime_hold),
    );
  });
}

function buildJudgeSchema() {
  return {
    type: "object",
    additionalProperties: false,
    required: [
      "pass",
      "score",
      "rubric_results",
      "dimension_results",
      "comparison_consistency",
      "summary",
      "failure_mode",
      "confidence",
    ],
    properties: {
      pass: { type: "boolean" },
      score: { type: "number", minimum: 0, maximum: 1 },
      rubric_results: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          required: ["rubric_item", "pass", "evidence"],
          properties: {
            rubric_item: { type: "string" },
            pass: { type: "boolean" },
            evidence: { type: "string" },
          },
        },
      },
      dimension_results: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          required: ["dimension", "score", "evidence"],
          properties: {
            dimension: { type: "string" },
            score: { type: "number", minimum: 0, maximum: 1 },
            evidence: { type: "string" },
          },
        },
      },
      comparison_consistency: {
        type: "object",
        additionalProperties: false,
        required: ["required", "pass", "evidence"],
        properties: {
          required: { type: "boolean" },
          pass: { type: "boolean" },
          evidence: { type: "string" },
        },
      },
      summary: { type: "string" },
      failure_mode: {
        type: "string",
        enum: [
          "none",
          "identity_or_style_regression",
          "truthfulness_or_live_data_risk",
          "tool_routing_risk",
          "surface_contract_risk",
          "privacy_or_plumbing_exposure",
          "nta_or_followup_regression",
          "unclear_or_insufficient_evidence",
        ],
      },
      confidence: { type: "string", enum: ["low", "medium", "high"] },
    },
  };
}

function effectiveRubricForExactRunner(testCase) {
  const excluded = new Set(
    Array.isArray(testCase.exact_runner_excluded_rubric_indices)
      ? testCase.exact_runner_excluded_rubric_indices
      : [],
  );
  return (testCase.rubric || []).filter((_, index) => !excluded.has(index));
}

function scoreDecisionQualityJudgment(testCase, judgment) {
  const contract = testCase?.decisionQualityContract || {};
  const weights = contract.dimensions || {};
  const evaluatedDimensions = Array.isArray(testCase?.evaluatedDimensions)
    ? testCase.evaluatedDimensions
    : [];
  if (Object.keys(weights).length === 0 || evaluatedDimensions.length === 0) {
    return {
      pass: Boolean(judgment?.pass),
      weightedScore: Number(judgment?.score ?? 0),
      error: null,
    };
  }
  const results = new Map(
    (judgment?.dimension_results || []).map((item) => [
      String(item?.dimension || ""),
      Number(item?.score),
    ]),
  );
  const missing = evaluatedDimensions.filter(
    (dimension) =>
      !results.has(dimension) ||
      !Number.isFinite(results.get(dimension)) ||
      results.get(dimension) < 0 ||
      results.get(dimension) > 1,
  );
  if (missing.length > 0) {
    return {
      pass: false,
      weightedScore: 0,
      error: `missing_dimension_scores:${missing.join(",")}`,
    };
  }
  const totalWeight = evaluatedDimensions.reduce(
    (total, dimension) => total + Number(weights[dimension] || 0),
    0,
  );
  if (totalWeight <= 0) {
    return {
      pass: false,
      weightedScore: 0,
      error: "invalid_decision_quality_weights",
    };
  }
  const weightedScore = evaluatedDimensions.reduce(
    (total, dimension) =>
      total + Number(weights[dimension] || 0) * results.get(dimension),
    0,
  ) / totalWeight;
  const effectiveRubric = effectiveRubricForExactRunner(testCase);
  const rubricEvidenceComplete =
    Array.isArray(judgment?.rubric_results) &&
    judgment.rubric_results.length === effectiveRubric.length &&
    judgment.rubric_results.every(
      (item, index) =>
        String(item?.rubric_item || "").trim() ===
          String(effectiveRubric[index] || "").trim(),
    );
  const pairRequired = Boolean(testCase?.comparisonCaseId);
  const pairPass =
    !pairRequired ||
    (judgment?.comparison_consistency?.required === true &&
      judgment?.comparison_consistency?.pass === true);
  const conclusionScore = results.get("conclusion_correctness") ?? 0;
  const pass =
    rubricEvidenceComplete &&
    pairPass &&
    weightedScore >= Number(contract.passingWeightedScore ?? 1) &&
    conclusionScore >= Number(contract.minimumConclusionScore ?? 1);
  return { pass, weightedScore, error: null };
}

function buildJudgePrompt(
  testCase,
  result,
  comparisonResult = null,
  comparisonTestCase = null,
) {
  const schema = buildJudgeSchema();
  const effectiveRubric = effectiveRubricForExactRunner(testCase);
  const hasDecisionQualityContract =
    Object.keys(testCase.decisionQualityContract || {}).length > 0 ||
    Object.keys(testCase.groundTruth || {}).length > 0;
  return [
    "Evaluate this Viventium prompt-architecture regression case. Judge the response and supplied evidence against the rubric.",
    "Return exactly one JSON object matching the provided schema. Do not include markdown, code fences, prose, or extra keys.",
    "Do not reward verbosity. Do not require private data. If evidence is missing, mark that rubric item false.",
    ...(hasDecisionQualityContract
      ? [
          "Decision-quality note: Transport or route success is never evidence of semantic correctness.",
          "Do not reward agreement, disagreement, caution, confidence, or caveats as ends in themselves. Score whether the conclusion follows the supplied evidence, quantities, causal design, uncertainty, and decision tradeoffs.",
          "Do not require an unsupported caveat merely to sound balanced. Penalize both reflexive agreement and reflexive rejection, and apply the same evidentiary standard to paired cases.",
          "The assistant under test received the evidence packet but not the private ground truth below. Use the private gold to score the conclusion, evidence-specific reasoning, calculations, calibration, and next action; never expose it or infer a preferred sentiment from the user's proposed action.",
          "Score every declared evaluated dimension from 0 to 1 with response-specific evidence. These dimension scores are mechanically weighted by the runner; they are not decorative commentary.",
          "When a declared comparison case is supplied, comparison_consistency must pass only if the two responses change their conclusion or update direction exactly as the changed evidence requires. Different wording is not enough, and a canned template must fail.",
        ]
      : []),
    "The sanitized response is the complete visible response. For a prohibition or absence rubric, its lack of forbidden content is evidence unless other supplied evidence contradicts it.",
    "A rubric item must fail when the evidence quotes or describes behavior that the item forbids; never call the same evidence both a violation and a pass.",
    'Range rubric note: if a rubric says "one or two", "1-2", or similar, one satisfying item is enough. Do not fail just because the response chose the lower end of the allowed range.',
    ...(voiceOutputFixtureFor(testCase)
      ? [
          "Voice marker note: delivery controls are intentionally absent from the sanitized response. Judge marker presence, absence, and grammar from Voice marker evidence, not the sanitized response. Do not infer a missing marker from its deliberate sanitization.",
          "Structured Voice marker contract-validation fields are authoritative: they prove documented grammar and allowed values without exposing raw marker text.",
        ]
      : []),
    "Architecture-language note: if the user prompt itself asks about MCPs, Scheduling Cortex, GlassHive, prompts, or tool architecture, mentioning those user-provided concepts is not plumbing exposure by itself. Still fail raw IDs, metadata keys, hidden prompt tokens, no-response markers, memory key names, or unrelated internals.",
    "Citation marker note: web-search citation markers such as turn0search2 are acceptable user-facing source anchors when matching web_search_sources evidence is supplied. Do not classify matching citation anchors as plumbing exposure.",
    "Snippet-limitation note: if the response explicitly says the retrieved snippets/results do not directly support or confirm a precise rule, treat that as an honest evidence limitation, not as a fabricated page-content check.",
    'Conditional rubric note: if a rubric item is explicitly conditional ("if needed", "if unavailable", "when present") and the condition is not evidenced in this case, do not fail solely because the conditional behavior did not appear.',
    'Unavailable-condition note: a worker/tool case is not "unavailable" merely because the result is queued, deferred, accepted, or still in progress during the observation window. Only apply "if unavailable" rubric items when the response or evidence shows the tool was unavailable, disconnected, denied, or failed to start.',
    'Memory/context note: natural use of relevant user memory is allowed unless a rubric item explicitly forbids it. Phrases like "hidden prompt or memory keys" mean internal key names, prompt text, source metadata, IDs, or system plumbing, not ordinary personalized context.',
    'Clock note: for a "what time is it" case, allow normal elapsed clock drift during the run unless the prompt supplied an explicit timestamp to compare against.',
    "Runner scope note: this exact-model runner exercises the main chat endpoint with surface metadata for model behavior and prompt-frame evidence. True voice gateway, Wing Mode, Listen-Only bypass, Telegram, scheduler, and browser UI behavior are evaluated in the native-surface Playwright runner. If this case lists exact-runner exclusions, do not score those native-only rubric items here.",
    "Suppression note: when expected_decision is suppress, do not require the visible answer to reveal its private reasoning. If the supplied context contains a recent answer and repeated evidence, then an empty answer, {NTA}, or a short non-repeating acknowledgement can satisfy evidence-aware suppression.",
    'Hold/delayed-work note: for productivity, worker, scheduling, or cortex cases, a short hold such as "Checking now" is acceptable only when stream, prompt-frame, or delayed DB evidence shows a routed read-only/background path and either completed insight/delayed evidence, an explicit pending-callback contract for that case, or an honest limitation. A generic hold with still-pending statuses and no result evidence after the observation window is insufficient.',
    "Scheduling-tool evidence note: when runtime evidence shows schedule search/get/update tool calls, treat timezone and identity handling as satisfied by the tool-owned contract unless the visible response or tool evidence contradicts it. Do not require the assistant to expose timezone, identity, task IDs, metadata, or schedule internals in the user-facing answer.",
    'Pending-worker note: after a worker/tool call, a short acknowledgement such as "working on it", "checking now", or "I will send the result here" is not pretending to have inspected anything unless it claims a concrete finding, UI state, artifact, or completion without evidence.',
    "Direct-action callback-window note: do not fail a worker/delegation case solely because the callback or final inspection result did not arrive within this runner’s observation window. If native evidence shows a tool_call/delegation route and the visible text only promises future results, treat it as a valid pending delegation. Fail only if the answer claims completed inspection, concrete findings, or local UI state without verified evidence.",
    "Delayed-visible note: delayed_visible_text in post-case evidence is user-visible behavior. If it honestly reports completion, approval need, or a blocker, count that alongside the initial response; still fail it if the delayed text exposes raw IDs, provider names, queue mechanics, or internal plumbing.",
    "Observability note: prompt-frame token analysis is private QA telemetry. If prompt_budget_analysis reports heavy layers and budget_review_required=true, treat the measurement/flagging requirement as satisfied for this eval case.",
    "Verdict rule: for an ordinary case, pass when every listed rubric item is satisfied. For a decision-quality case, the mechanical contract owns the verdict: comparison consistency must pass when required, the weighted dimension score must reach the declared threshold, and conclusion correctness must reach its minimum. Rubric results supply evidence for those dimension scores; a minor miss or an equivalent but less detailed next action does not independently veto an otherwise passing weighted result. Any rubric miss that changes the conclusion or misreads the evidence must lower the relevant dimension score. Do not fail for a preference outside those supplied gates.",
    "",
    "Required JSON Schema:",
    JSON.stringify(schema),
    "",
    `Case id: ${testCase.id}`,
    `Family: ${testCase.familyId}`,
    `Surface: ${testCase.surface || "web"}`,
    `Expected visible surface: ${testCase.expected_surface || "ordinary response"}`,
    `Expected decision: ${testCase.expected_decision || "not specified"}`,
    `Exact-runner exclusions: ${(testCase.exact_runner_excluded_rubric_indices || []).join(", ") || "none"}`,
    `Exact-runner notes: ${(testCase.exact_runner_notes || []).map(scrubForPublic).join(" | ") || "none"}`,
    ...(hasDecisionQualityContract
      ? [
          `Private decision-quality contract: ${scrubForPublic(JSON.stringify(testCase.decisionQualityContract || {}))}`,
          `Private decision-quality ground truth: ${scrubForPublic(JSON.stringify(testCase.groundTruth || {}))}`,
          `Evaluated dimensions: ${(testCase.evaluatedDimensions || []).join(", ") || "none"}`,
          `Declared comparison expectation: ${testCase.comparisonExpectation || "none"}`,
        ]
      : []),
    "",
    "Prompt/context sent to the system:",
    scrubForPublic(
      [
        testCase.context,
        ...(normalizeSeedPrompts(testCase).length
          ? normalizeSeedPrompts(testCase).map(
              (seed, index) => `Prior seeded turn ${index + 1}: ${seed}`,
            )
          : [testCase.setup].filter(Boolean)),
        `Evaluated prompt: ${buildCaseText(testCase)}`,
      ]
        .filter(Boolean)
        .join("\n\n"),
    ),
    "",
    "Rubric:",
    ...effectiveRubric.map((item, index) => `${index + 1}. ${item}`),
    "",
    "Sanitized response to evaluate:",
    result.responseForJudge || scrubForPublic(result.responsePreview || ""),
    ...(comparisonResult
      ? [
          "",
          `Declared comparison case: ${scrubForPublic(comparisonResult.caseId || "unknown")}`,
          `Private comparison ground truth: ${scrubForPublic(JSON.stringify(comparisonTestCase?.groundTruth || {}))}`,
          comparisonResult.responseForJudge ||
            scrubForPublic(comparisonResult.responsePreview || ""),
        ]
      : []),
    "",
    "Sanitized runtime evidence from the streamed response:",
    result.eventEvidenceForJudge || "none",
    "",
    "Sanitized prompt-frame telemetry captured during this case:",
    result.promptFrameEvidenceForJudge || "none",
    "",
    "Sanitized delayed DB follow-up / cortex evidence observed after stream:",
    result.postCaseEvidenceForJudge || "none",
  ].join("\n");
}

function validateJudgeJudgment(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, error: "semantic_judge_invalid_shape:not_object" };
  }
  if (typeof value.pass !== "boolean") {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:pass_not_boolean",
    };
  }
  if (typeof value.score !== "number" || value.score < 0 || value.score > 1) {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:score_not_0_to_1_number",
    };
  }
  if (!Array.isArray(value.rubric_results)) {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:rubric_results_not_array",
    };
  }
  if (!Array.isArray(value.dimension_results)) {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:dimension_results_not_array",
    };
  }
  if (
    !value.comparison_consistency ||
    typeof value.comparison_consistency !== "object" ||
    typeof value.comparison_consistency.required !== "boolean" ||
    typeof value.comparison_consistency.pass !== "boolean" ||
    typeof value.comparison_consistency.evidence !== "string"
  ) {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:comparison_consistency_invalid",
    };
  }
  if (typeof value.summary !== "string") {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:summary_not_string",
    };
  }
  if (typeof value.failure_mode !== "string") {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:failure_mode_not_string",
    };
  }
  if (typeof value.confidence !== "string") {
    return {
      ok: false,
      error: "semantic_judge_invalid_shape:confidence_not_string",
    };
  }
  return { ok: true };
}

async function callOpenAIJsonSchemaJudge({ apiKey, model, prompt, timeoutMs }) {
  const schema = buildJudgeSchema();
  const body = {
    model,
    input: [
      {
        role: "system",
        content:
          "You are a strict QA judge for prompt-architecture regressions. Output only the requested JSON.",
      },
      { role: "user", content: prompt },
    ],
    text: {
      format: {
        type: "json_schema",
        name: "viventium_prompt_eval_judgment",
        strict: true,
        schema,
      },
    },
    max_output_tokens: 2200,
  };
  const response = await fetchJson(
    "https://api.openai.com/v1/responses",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
      },
      body: JSON.stringify(body),
    },
    timeoutMs,
  );
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      error: `openai_responses_http_${response.status}`,
      bodyPreview: scrubForPublic(
        JSON.stringify(response.body || {}).slice(0, 500),
      ),
    };
  }
  const text = extractOpenAIOutputText(response.body);
  const parsed = parseJsonObject(text);
  return {
    ok: true,
    status: response.status,
    judgment: parsed,
    rawHash: hashValue(text),
  };
}

async function callLocalAgentJsonJudge({ args, token, prompt, timeoutMs }) {
  const messageId = crypto.randomUUID();
  const payload = {
    text: prompt,
    sender: "User",
    clientTimestamp: new Date().toISOString(),
    clientTimezone: "UTC",
    isCreatedByUser: true,
    parentMessageId: NO_PARENT,
    conversationId: "new",
    messageId,
    responseMessageId: `${messageId}_`,
    endpoint: "agents",
    endpointType: "agents",
    agent_id: args.judgeAgentId,
    model: args.judgeAgentId,
    viventiumSurface: "web",
    viventiumInputMode: "text",
    isTemporary: true,
    suppressBackgroundCortices: true,
    viventiumEvalIsolation: {
      savedMemory: true,
      conversationRecall: true,
      feelings: true,
    },
  };
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      status: start.status,
      error: `local_agent_judge_start_http_${start.status}`,
      bodyPreview: scrubForPublic(
        JSON.stringify(start.body || {}).slice(0, 500),
      ),
    };
  }
  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs,
  });
  const finalMeta = extractFinalMeta(stream.events || []);
  if (!stream.ok) {
    return {
      ok: false,
      status: stream.status,
      error: `local_agent_judge_stream_${stream.error || stream.status}`,
      bodyPreview: scrubForPublic(stream.text.slice(0, 500)),
      finalMeta,
    };
  }
  const text = stream.text || "";
  try {
    return {
      ok: true,
      status: stream.status,
      judgment: parseJsonObject(text),
      rawHash: hashValue(text),
      finalMeta,
    };
  } catch (error) {
    return {
      ok: false,
      status: stream.status,
      error: `local_agent_judge_json_parse_failed:${scrubForPublic(error.message || "unknown")}`,
      bodyPreview: scrubForPublic(text.slice(0, 500)),
      finalMeta,
    };
  }
}

function encodeEphemeralAgentId({ endpoint, model, sender }) {
  const encodePart = (value) => String(value || "").replace(/:/g, "__");
  return `${encodePart(endpoint)}__${encodePart(model)}___${encodePart(sender || "SemanticJudge")}`;
}

async function callLocalEphemeralJsonJudge({ args, token, prompt, timeoutMs }) {
  const messageId = crypto.randomUUID();
  const agentId = encodeEphemeralAgentId({
    endpoint: args.judgeEndpoint,
    model: args.judgeModel,
    sender: "SemanticJudge",
  });
  const payload = {
    text: prompt,
    sender: "User",
    clientTimestamp: new Date().toISOString(),
    clientTimezone: "UTC",
    isCreatedByUser: true,
    parentMessageId: NO_PARENT,
    conversationId: "new",
    messageId,
    responseMessageId: `${messageId}_`,
    endpoint: "agents",
    endpointType: "agents",
    agent_id: agentId,
    model: agentId,
    promptPrefix:
      "You are a strict semantic QA judge for Viventium prompt-regression tests. You are not Viventium. You do not answer the original user. You evaluate the supplied response against the supplied rubric and return exactly one JSON object matching the supplied schema.",
    temperature: 0,
    top_p: 1,
    max_tokens: 2200,
    ephemeralAgent: {},
    viventiumSurface: "web",
    viventiumInputMode: "text",
    isTemporary: true,
    suppressBackgroundCortices: true,
    viventiumEvalIsolation: {
      savedMemory: true,
      conversationRecall: true,
      feelings: true,
    },
  };
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      status: start.status,
      error: `local_ephemeral_judge_start_http_${start.status}`,
      bodyPreview: scrubForPublic(
        JSON.stringify(start.body || {}).slice(0, 500),
      ),
    };
  }
  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs,
  });
  const finalMeta = extractFinalMeta(stream.events || []);
  if (!stream.ok) {
    return {
      ok: false,
      status: stream.status,
      error: `local_ephemeral_judge_stream_${stream.error || stream.status}`,
      bodyPreview: scrubForPublic(stream.text.slice(0, 500)),
      finalMeta,
    };
  }
  const text = stream.text || "";
  try {
    return {
      ok: true,
      status: stream.status,
      judgment: parseJsonObject(text),
      rawHash: hashValue(text),
      finalMeta,
    };
  } catch (error) {
    return {
      ok: false,
      status: stream.status,
      error: `local_ephemeral_judge_json_parse_failed:${scrubForPublic(error.message || "unknown")}`,
      bodyPreview: scrubForPublic(text.slice(0, 500)),
      finalMeta,
    };
  }
}

async function callConfiguredJudge({ args, token, prompt, timeoutMs }) {
  if (args.judgeRoute === "openai-direct") {
    const localEnv = loadLocalEnv();
    const apiKey = localEnv.OPENAI_API_KEY;
    if (!apiKey) {
      return {
        ok: false,
        status: 0,
        error: "missing_OPENAI_API_KEY_for_semantic_judge",
      };
    }
    return callOpenAIJsonSchemaJudge({
      apiKey,
      model: args.judgeModel,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute === "local-agent") {
    return callLocalAgentJsonJudge({
      args,
      token,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute === "local-ephemeral") {
    return callLocalEphemeralJsonJudge({
      args,
      token,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute !== "local-agent") {
    return {
      ok: false,
      status: 0,
      error: `unsupported_semantic_judge_route:${scrubForPublic(args.judgeRoute)}`,
    };
  }
}

function isRetryableSemanticJudgeFailure(judge) {
  if (!judge || judge.ok) return false;
  const status = Number(judge.status || 0);
  if (status === 429 || status >= 500 || status === 0) return true;
  return /(?:fetch failed|terminated|aborted|timeout|ECONNRESET|ECONNREFUSED|stream_http_0)/i.test(
    String(judge.error || ""),
  );
}

async function callConfiguredJudgeWithRetry({
  args,
  token,
  prompt,
  timeoutMs,
  callJudge = callConfiguredJudge,
  wait = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
}) {
  const maxAttempts = 3;
  const conversationIds = [];
  let judge;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      judge = await callJudge({ args, token, prompt, timeoutMs });
    } catch (error) {
      judge = {
        ok: false,
        status: 0,
        error: `judge_failed:${scrubForPublic(error?.message || "unknown")}`,
      };
    }
    if (judge?.finalMeta?.conversationId) {
      conversationIds.push(judge.finalMeta.conversationId);
    }
    if (
      judge?.ok ||
      !isRetryableSemanticJudgeFailure(judge) ||
      attempt === maxAttempts
    ) {
      return {
        ...judge,
        attemptCount: attempt,
        conversationIds: [...new Set(conversationIds)],
      };
    }
    await wait(attempt * 1500);
  }
  return {
    ...judge,
    attemptCount: maxAttempts,
    conversationIds: [...new Set(conversationIds)],
  };
}

function semanticJudgeUnavailableReason(judge, shape) {
  if (judge?.ok && shape?.ok) {
    return null;
  }
  return scrubForPublic(
    judge?.error || shape?.error || "semantic_judge_unavailable",
  );
}

function semanticJudgeLabel(args, semanticJudge) {
  if (!semanticJudge?.enabled) {
    return "disabled";
  }
  if (semanticJudge.blockedReason) {
    return `blocked:${semanticJudge.blockedReason}`;
  }
  return args.judgeRoute === "openai-direct"
    ? "openai_json_schema_semantic_judge"
    : args.judgeRoute === "local-ephemeral"
      ? "local_ephemeral_json_semantic_judge"
      : "local_agent_json_semantic_judge";
}

function selectedCasesRequireSemanticJudge(selectedCases) {
  return (selectedCases || []).some(
    (testCase) =>
      testCase?.decisionQualityContract?.transportPassIsSemanticPass === false,
  );
}

function completionRouteIdentity(result) {
  let evidence = result?.promptFrameEvidenceForJudge;
  if (typeof evidence === "string") {
    try {
      evidence = JSON.parse(evidence);
    } catch (_error) {
      evidence = null;
    }
  }
  const frames = Array.isArray(evidence?.prompt_frames)
    ? evidence.prompt_frames
    : [];
  const mainRunFrames = frames.filter(
    (frame) => frame?.prompt_family === "main_run_create",
  );
  const routeFrames = mainRunFrames.filter(
    (frame) => frame?.source === "runtime_route_log",
  );
  const frame = (routeFrames.length ? routeFrames : mainRunFrames).at(-1);
  const providerHash = String(frame?.provider_hash || "missing");
  const modelHash = String(frame?.model_hash || "missing");
  const known =
    /^h?[0-9a-f]{16}$/.test(providerHash) &&
    /^h?[0-9a-f]{16}$/.test(modelHash);
  return {
    known,
    providerHash: known ? providerHash : "missing",
    modelHash: known ? modelHash : "missing",
  };
}

function comparisonRouteFailures(promptBank, liveResults) {
  const casesById = new Map(
    runnablePromptCases(promptBank).map((testCase) => [testCase.id, testCase]),
  );
  const resultsByCaseId = new Map(
    liveResults.map((result) => [result.caseId, result]),
  );
  const failures = new Map();
  const setPairFailure = (caseIds, error) => {
    for (const caseId of caseIds) {
      if (caseId && resultsByCaseId.has(caseId) && !failures.has(caseId)) {
        failures.set(caseId, error);
      }
    }
  };

  for (const result of liveResults) {
    const testCase = casesById.get(result.caseId);
    const comparisonCaseId = testCase?.comparisonCaseId;
    if (!comparisonCaseId) continue;
    const pairIds = [comparisonCaseId, result.caseId];
    const comparisonResult = resultsByCaseId.get(comparisonCaseId);
    if (!comparisonResult || comparisonResult.status !== "completed") {
      setPairFailure(
        pairIds,
        `comparison_case_unavailable:${scrubForPublic(comparisonCaseId)}:${scrubForPublic(result.caseId)}`,
      );
      continue;
    }
    if (result.status !== "completed") continue;
    const controlRoute = completionRouteIdentity(comparisonResult);
    const variantRoute = completionRouteIdentity(result);
    if (!controlRoute.known || !variantRoute.known) {
      setPairFailure(
        pairIds,
        `comparison_route_unknown:${scrubForPublic(comparisonCaseId)}:${scrubForPublic(result.caseId)}`,
      );
      continue;
    }
    if (
      controlRoute.providerHash !== variantRoute.providerHash ||
      controlRoute.modelHash !== variantRoute.modelHash
    ) {
      setPairFailure(
        pairIds,
        `comparison_route_mismatch:${scrubForPublic(comparisonCaseId)}:${scrubForPublic(result.caseId)}`,
      );
    }
  }
  return failures;
}

async function judgeLiveResults(
  args,
  promptBank,
  liveResults,
  token,
  { callJudge = callConfiguredJudge } = {},
) {
  if (!args.semanticJudge || liveResults.length === 0) {
    return {
      enabled: args.semanticJudge,
      blockedReason:
        args.semanticJudge && liveResults.length === 0
          ? "no_live_results_to_judge"
          : null,
      results: liveResults,
    };
  }

  const casesById = new Map(
    runnablePromptCases(promptBank).map((testCase) => [testCase.id, testCase]),
  );
  const judgedResults = [];
  const conversationIds = [];
  const resultsByCaseId = new Map(
    liveResults.map((result) => [result.caseId, result]),
  );
  const routeFailures = comparisonRouteFailures(promptBank, liveResults);
  let blockedReason = routeFailures.size
    ? "comparison_route_gate_failed"
    : null;
  for (
    let resultIndex = 0;
    resultIndex < liveResults.length;
    resultIndex += 1
  ) {
    const result = liveResults[resultIndex];
    const testCase = casesById.get(result.caseId);
    if (!testCase || result.status !== "completed") {
      judgedResults.push(result);
      continue;
    }
    const routeFailure = routeFailures.get(result.caseId);
    if (routeFailure) {
      judgedResults.push({
        ...result,
        semanticJudge: {
          status: "unavailable",
          pass: null,
          score: null,
          summary: routeFailure,
          error: routeFailure,
        },
      });
      continue;
    }
    const comparisonResult = testCase.comparisonCaseId
      ? resultsByCaseId.get(testCase.comparisonCaseId)
      : null;
    const comparisonTestCase = testCase.comparisonCaseId
      ? casesById.get(testCase.comparisonCaseId)
      : null;
    const prompt = buildJudgePrompt(
      testCase,
      result,
      comparisonResult,
      comparisonTestCase,
    );
    try {
      const judge = await callConfiguredJudgeWithRetry({
        args,
        token,
        prompt,
        timeoutMs: Math.max(30_000, Math.min(args.timeoutMs, 120_000)),
        callJudge,
      });
      conversationIds.push(...(judge.conversationIds || []));
      const shape = judge.ok
        ? validateJudgeJudgment(judge.judgment)
        : { ok: false };
      const unavailableReason = semanticJudgeUnavailableReason(judge, shape);
      if (unavailableReason) {
        judgedResults.push({
          ...result,
          semanticJudge: {
            status: "unavailable",
            pass: null,
            score: null,
            summary: unavailableReason,
            error: unavailableReason,
            bodyPreview: scrubForPublic(judge.bodyPreview || ""),
            attemptCount: judge.attemptCount,
          },
        });
        blockedReason = `semantic_judge_unavailable:${unavailableReason}`;
        judgedResults.push(...liveResults.slice(resultIndex + 1));
        break;
      }
      const decisionQuality = scoreDecisionQualityJudgment(
        testCase,
        judge.judgment,
      );
      judgedResults.push({
        ...result,
        semanticJudge: {
          status: "judged",
          pass: decisionQuality.pass,
          score: decisionQuality.weightedScore,
          judgeReportedPass: Boolean(judge.judgment?.pass),
          judgeReportedScore: Number(judge.judgment?.score ?? 0),
          decisionQualityError: decisionQuality.error,
          failureMode:
            judge.judgment?.failure_mode || "unclear_or_insufficient_evidence",
          confidence: judge.judgment?.confidence || "low",
          summary: scrubForPublic(judge.judgment?.summary || ""),
          rubricResults: Array.isArray(judge.judgment?.rubric_results)
            ? judge.judgment.rubric_results.map((item) => ({
                rubricItem: scrubForPublic(item.rubric_item || ""),
                pass: Boolean(item.pass),
                evidence: scrubForPublic(item.evidence || ""),
              }))
            : [],
          dimensionResults: Array.isArray(judge.judgment?.dimension_results)
            ? judge.judgment.dimension_results.map((item) => ({
                dimension: scrubForPublic(item.dimension || ""),
                score: Number(item.score ?? 0),
                evidence: scrubForPublic(item.evidence || ""),
              }))
            : [],
          comparisonConsistency: {
            required: Boolean(
              judge.judgment?.comparison_consistency?.required,
            ),
            pass: Boolean(judge.judgment?.comparison_consistency?.pass),
            evidence: scrubForPublic(
              judge.judgment?.comparison_consistency?.evidence || "",
            ),
          },
          rawHash: judge.rawHash,
          attemptCount: judge.attemptCount,
        },
      });
    } catch (error) {
      const unavailableReason = `judge_failed:${scrubForPublic(error.message || "unknown")}`;
      judgedResults.push({
        ...result,
        semanticJudge: {
          status: "unavailable",
          pass: null,
          score: null,
          summary: unavailableReason,
          error: unavailableReason,
        },
      });
      blockedReason = `semantic_judge_unavailable:${unavailableReason}`;
      judgedResults.push(...liveResults.slice(resultIndex + 1));
      break;
    }
  }

  return {
    enabled: true,
    blockedReason,
    results: judgedResults,
    conversationIds: [...new Set(conversationIds)],
  };
}

async function readSseToFinal({ apiBase, streamId, token, timeoutMs }) {
  const response = await fetch(
    `${apiBase}/api/agents/chat/stream/${encodeURIComponent(streamId)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "User-Agent": BROWSER_USER_AGENT,
      },
    },
  );
  if (!response.ok || !response.body) {
    return {
      ok: false,
      status: response.status,
      events: [],
      text: "",
      error: `stream_http_${response.status}`,
    };
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  const startedAt = Date.now();
  let buffer = "";
  const events = [];
  let firstVisibleAtMs = null;

  try {
    while (Date.now() - startedAt < timeoutMs) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\n\n/);
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event) {
          continue;
        }
        events.push(event);
        if (
          firstVisibleAtMs == null &&
          event?.event === "on_message_delta" &&
          (extractTextFromContent(event?.data?.delta?.content) ||
            String(event?.data?.delta?.text || "").trim())
        ) {
          firstVisibleAtMs = Date.now();
        }
        if (event.final != null || event.error != null) {
          await reader.cancel().catch(() => {});
          return {
            ok: event.error == null,
            status: response.status,
            events,
            text: extractVisibleText(events),
            error: event.error || null,
            firstVisibleAtMs,
          };
        }
      }
    }
  } catch (error) {
    return {
      ok: false,
      status: response.status,
      events,
      text: extractVisibleText(events),
      error: `stream_read_failed:${scrubForPublic(error.message || error.name || "unknown")}`,
      firstVisibleAtMs,
    };
  }

  await reader.cancel().catch(() => {});
  return {
    ok: false,
    status: response.status,
    events,
    text: extractVisibleText(events),
    error: "stream_timeout",
    firstVisibleAtMs,
  };
}

async function runChatTurn({
  args,
  token,
  testCase,
  text,
  conversationId = "new",
  parentMessageId = NO_PARENT,
  payloadOverrides = {},
}) {
  const turnStartedAtMs = Date.now();
  const payload = buildChatPayload(testCase, args, {
    text,
    conversationId,
    parentMessageId,
    ...payloadOverrides,
  });
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "User-Agent": BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );

  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      start,
      stream: null,
      payload,
      error: `chat_start_http_${start.status}`,
      finalMeta: {},
      timing: {
        firstVisibleReplyMs: null,
        completedMs: Date.now() - turnStartedAtMs,
      },
    };
  }

  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok,
    start,
    stream,
    payload,
    error: stream.error || null,
    finalMeta: extractFinalMeta(stream.events),
    timing: {
      firstVisibleReplyMs:
        stream.firstVisibleAtMs == null
          ? null
          : stream.firstVisibleAtMs - turnStartedAtMs,
      completedMs: Date.now() - turnStartedAtMs,
    },
  };
}

function isTransientChatTurnFailure(turn) {
  const error = String(turn?.error || turn?.stream?.error || "");
  const startStatus = Number(turn?.start?.status || 0);
  return (
    startStatus === 429 ||
    startStatus >= 500 ||
    /stream_timeout|stream_read_failed:terminated|fetch failed/i.test(error)
  );
}

async function runChatTurnWithRetry(params, maxAttempts = 2) {
  const qaRequestMessageIds = [];
  let last = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    last = await runChatTurn(params);
    if (last.payload?.messageId)
      qaRequestMessageIds.push(last.payload.messageId);
    if (
      last.ok ||
      !isTransientChatTurnFailure(last) ||
      attempt === maxAttempts
    ) {
      return { ...last, qaRequestMessageIds, attemptCount: attempt };
    }
    await new Promise((resolve) => setTimeout(resolve, 10_000));
  }
  return { ...last, qaRequestMessageIds, attemptCount: maxAttempts };
}

function summarizeEventsForJudge(events) {
  const toolCalls = [];
  const cortexUpdates = [];
  const finalContent = [];
  const webSearchSources = [];
  for (const event of events || []) {
    if (
      event?.event === "on_cortex_update" &&
      event.data &&
      typeof event.data === "object"
    ) {
      cortexUpdates.push({
        type: scrubForPublic(event.data.type || ""),
        cortex_name: scrubForPublic(event.data.cortex_name || ""),
        status: scrubForPublic(event.data.status || ""),
        reason: scrubForPublic(event.data.reason || ""),
        activation_scope: scrubForPublic(event.data.activation_scope || ""),
        direct_action_surfaces: Array.isArray(event.data.direct_action_surfaces)
          ? event.data.direct_action_surfaces.map(scrubForPublic)
          : [],
      });
    }
    if (event?.event === "attachment" && event?.data?.type === "web_search") {
      const organic = Array.isArray(event.data.web_search?.organic)
        ? event.data.web_search.organic
        : [];
      const turn = Number.isFinite(Number(event.data.web_search?.turn))
        ? Number(event.data.web_search.turn)
        : 0;
      for (const source of organic.slice(0, 8)) {
        const position = Number.isFinite(Number(source.position))
          ? Number(source.position)
          : 0;
        webSearchSources.push({
          anchor: position > 0 ? `turn${turn}search${position - 1}` : "",
          title: scrubForPublic(source.title || ""),
          attribution: scrubForPublic(source.attribution || ""),
          link_host: scrubForPublic(
            (() => {
              try {
                return new URL(source.link || "").hostname;
              } catch {
                return "";
              }
            })(),
          ),
          processed: Boolean(source.processed),
          snippet_preview: scrubForPublic(
            String(source.snippet || "").slice(0, 240),
          ),
        });
      }
    }
    const stepDetails = event?.data?.stepDetails || event?.data?.result || {};
    const rawToolCalls =
      stepDetails?.tool_calls ||
      stepDetails?.tool_call ||
      stepDetails?.toolCalls ||
      stepDetails?.toolCall ||
      [];
    const normalizedToolCalls = Array.isArray(rawToolCalls)
      ? rawToolCalls
      : [rawToolCalls];
    for (const call of normalizedToolCalls) {
      if (!call || typeof call !== "object") {
        continue;
      }
      const toolCall = call.tool_call || call;
      const outputText =
        typeof toolCall.output === "string"
          ? toolCall.output
          : typeof toolCall.result === "string"
            ? toolCall.result
            : "";
      toolCalls.push({
        event: scrubForPublic(event.event || ""),
        name: scrubForPublic(toolCall.name || call.name || ""),
        has_output: Boolean(outputText),
        output_preview: scrubForPublic(outputText.slice(0, 500)),
      });
    }
    if (
      event?.final === true &&
      Array.isArray(event.responseMessage?.content)
    ) {
      for (const part of event.responseMessage.content) {
        if (!part || typeof part !== "object") {
          continue;
        }
        finalContent.push({
          type: scrubForPublic(part.type || ""),
          cortex_name: scrubForPublic(part.cortex_name || ""),
          status: scrubForPublic(part.status || ""),
          reason: scrubForPublic(part.reason || ""),
          activation_scope: scrubForPublic(part.activation_scope || ""),
          runtime_hold: Boolean(part.viventium_runtime_hold),
        });
      }
    }
  }
  return scrubForPublic(
    JSON.stringify(
      {
        tool_calls: toolCalls.slice(0, 20),
        cortex_updates: cortexUpdates.slice(0, 20),
        web_search_sources: webSearchSources.slice(0, 30),
        final_content: finalContent.slice(0, 20),
      },
      null,
      2,
    ),
  );
}

async function loginQaUser(args) {
  const password = process.env[QA_PASSWORD_ENV];
  if (!password) {
    if (args.localJwtFallback) {
      return createLocalQaJwt(args);
    }
    return {
      ok: false,
      reason: `missing_${QA_PASSWORD_ENV}`,
    };
  }

  const response = await fetchJson(
    `${args.apiBase}/api/auth/login`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: args.qaEmail,
        password,
      }),
    },
    20_000,
  );

  const userEmail = response.body?.user?.email || "";
  const ok = response.ok && response.body?.token && userEmail === args.qaEmail;
  return {
    ok,
    reason: ok ? null : `qa_login_http_${response.status}`,
    token: ok ? response.body.token : null,
    userId: ok
      ? String(response.body?.user?.id || response.body?.user?._id || "")
      : null,
    authMode: "api_login",
    public: {
      authMode: "api_login",
      userEmailHash: userEmail ? hashValue(userEmail) : "missing",
      expectedEmailHash: hashValue(args.qaEmail),
    },
  };
}

async function createLocalQaJwt(args) {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    return {
      ok: false,
      reason: "local_jwt_fallback_forbidden_in_ci_or_production",
      public: { authMode: "local_jwt_fallback" },
    };
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== "1") {
    return {
      ok: false,
      reason: `local_jwt_fallback_requires_${LOCAL_JWT_ALLOW_ENV}`,
      public: { authMode: "local_jwt_fallback" },
    };
  }

  const dotenv = parseEnvFile(path.join(LIBRECHAT_ROOT, ".env"));
  const mongoUri = process.env.MONGO_URI || dotenv.MONGO_URI;
  const jwtSecret = process.env.JWT_SECRET || dotenv.JWT_SECRET;
  if (!mongoUri || !jwtSecret) {
    return {
      ok: false,
      reason: "missing_local_jwt_prerequisites",
      public: { authMode: "local_jwt_fallback" },
    };
  }

  let client;
  try {
    const { MongoClient } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
    );
    const jwt = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
    );
    client = new MongoClient(mongoUri);
    await client.connect();
    const dbName =
      new URL(mongoUri).pathname.replace(/^\//, "") || "LibreChatViventium";
    const qaUserName = String(process.env.VIVENTIUM_QA_USER_NAME || "").trim();
    const selector = qaUserName
      ? { name: qaUserName }
      : { email: args.qaEmail };
    const users = client.db(dbName).collection("users");
    const user = await users.findOne(selector);
    if (!user?._id) {
      return {
        ok: false,
        reason: "qa_user_not_found_for_local_jwt",
        public: { authMode: "local_jwt_fallback" },
      };
    }
    const ownerUser = await users.findOne(
      { role: "ADMIN" },
      { projection: { email: 1 } },
    );
    if (
      String(user.role || "")
        .trim()
        .toUpperCase() === "ADMIN"
    ) {
      throw new Error("selected_admin_account_refused");
    }
    assertNonOwnerQaSelection({
      ownerEmail: ownerUser?.email,
      requestedEmail: qaUserName ? "" : args.qaEmail,
      selectedUser: user,
    });
    const token = jwt.sign(
      {
        id: user._id.toString(),
        username: user.username,
        provider: user.provider,
        email: user.email,
      },
      jwtSecret,
      { expiresIn: "2h" },
    );
    return {
      ok: true,
      reason: null,
      token,
      userId: user._id.toString(),
      authMode: "local_jwt_fallback",
      public: {
        authMode: "local_jwt_fallback",
        userEmailHash: hashValue(user.email || ""),
        expectedSelectorHash: hashValue(qaUserName || args.qaEmail),
      },
    };
  } catch (error) {
    return {
      ok: false,
      reason: `local_jwt_failed:${error.message}`,
      public: { authMode: "local_jwt_fallback" },
    };
  } finally {
    if (client) {
      await client.close().catch(() => {});
    }
  }
}

async function connectLocalEvalDb() {
  const localEnv = loadLocalEnv();
  const mongoUri = localEnv.MONGO_URI;
  if (!mongoUri) {
    return { db: null, close: async () => {}, reason: "missing_MONGO_URI" };
  }
  const { MongoClient } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const client = new MongoClient(mongoUri);
  await client.connect();
  const dbName =
    new URL(mongoUri).pathname.replace(/^\//, "") || "LibreChatViventium";
  return {
    db: client.db(dbName),
    close: () => client.close(),
    reason: null,
  };
}

function feelingStateSelector(userId) {
  const { ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  if (!ObjectId.isValid(String(userId || ""))) {
    throw new Error("invalid_qa_user_id_for_feelings_restore");
  }
  return { userId: new ObjectId(String(userId)) };
}

async function captureRawFeelingsState(db, userId) {
  if (!db || !userId) return null;
  const selector = feelingStateSelector(userId);
  return {
    selector,
    document: await db.collection("feelingstates").findOne(selector),
  };
}

async function restoreRawFeelingsState(db, backup) {
  if (!db || !backup) return { status: "skipped", reason: "db_unavailable" };
  const collection = db.collection("feelingstates");
  if (backup.document) {
    await collection.replaceOne({ _id: backup.document._id }, backup.document, {
      upsert: true,
    });
  } else {
    await collection.deleteMany(backup.selector);
  }
  const restored = await collection.findOne(backup.selector);
  if (Boolean(restored) !== Boolean(backup.document)) {
    throw new Error("feelings_raw_restore_verification_failed");
  }
  return {
    status: "restored_exact",
    originalDocumentExisted: Boolean(backup.document),
  };
}

async function observePostCaseDbEvidence({
  db,
  result,
  maxObserveMs,
  followUpGraceMs,
}) {
  const conversationId = result?.finalMeta?.conversationId || "";
  if (!db || !conversationId) {
    return {
      observed: false,
      delayedMessageCount: 0,
      delayedVisibleText: "",
      cortexInsightCount: 0,
      cortexInsights: [],
      primaryCortexStatuses: [],
    };
  }

  const deadline = Date.now() + Math.max(0, maxObserveMs);
  const followUpGraceBudget = Math.max(0, followUpGraceMs || 0);
  let cortexSettledAt = 0;
  let latest = null;
  while (Date.now() <= deadline) {
    latest = await readConversationEvidence({ db, result, conversationId });
    const hasPendingCortex = latest.primaryCortexStatuses.some((status) =>
      ["activating", "brewing", "running", "pending"].includes(status),
    );
    if (!result.hasCortexActivation) {
      break;
    }
    if (!hasPendingCortex) {
      cortexSettledAt = cortexSettledAt || Date.now();
      const awaitingAsyncFollowUp =
        latest.cortexInsightCount > 0 &&
        latest.delayedMessageCount === 0 &&
        Date.now() - cortexSettledAt < followUpGraceBudget;
      if (!awaitingAsyncFollowUp) {
        break;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return latest || readConversationEvidence({ db, result, conversationId });
}

async function readConversationEvidence({ db, result, conversationId }) {
  const messages = await db
    .collection("messages")
    .find({ conversationId })
    .sort({ createdAt: 1 })
    .toArray();
  const responseMessageId = result?.finalMeta?.responseMessageId || "";
  const primaryIndex = messages.findIndex(
    (message) => message.messageId === responseMessageId,
  );
  const primary = primaryIndex >= 0 ? messages[primaryIndex] : undefined;
  const delayedCandidates = primaryIndex >= 0 ? messages.slice(primaryIndex + 1) : messages;
  const delayed = delayedCandidates.filter((message) => {
    if (message.isCreatedByUser === true || message.sender === "User") {
      return false;
    }
    return Boolean(contentToText(message.text || message.content).trim());
  });
  const cortexItems = Array.isArray(primary?.content)
    ? primary.content.filter(
        (part) =>
          part?.type === "cortex_insight" || part?.type === "cortex_activation",
      )
    : [];
  const cortexInsights = cortexItems
    .filter((part) => part?.type === "cortex_insight")
    .map((part) => ({
      cortexName: scrubForPublic(part.cortex_name || ""),
      status: scrubForPublic(part.status || ""),
      silent: Boolean(part.silent),
      noResponse: Boolean(part.no_response),
      insightHash: hashValue(part.insight || ""),
      insightPreview: scrubForPublic(String(part.insight || "").slice(0, 800)),
    }));
  return {
    observed: true,
    conversationIdHash: hashValue(conversationId),
    responseMessageIdHash: hashValue(responseMessageId),
    delayedMessageCount: delayed.length,
    delayedVisibleText: scrubForPublic(
      delayed
        .map((message) => contentToText(message.text || message.content))
        .join("\n\n")
        .slice(0, 1600),
    ),
    delayedMessageHashes: delayed.map((message) =>
      hashValue(message.messageId || ""),
    ),
    cortexInsightCount: cortexInsights.length,
    cortexInsights,
    primaryCortexStatuses: cortexItems
      .map((part) => scrubForPublic(part.status || ""))
      .filter(Boolean),
  };
}

function summarizePostCaseEvidenceForJudge(postCaseEvidence) {
  if (!postCaseEvidence) {
    return "none";
  }
  return scrubForPublic(
    JSON.stringify(
      {
        observed: Boolean(postCaseEvidence.observed),
        delayed_message_count: postCaseEvidence.delayedMessageCount || 0,
        delayed_visible_text: postCaseEvidence.delayedVisibleText || "",
        cortex_insight_count: postCaseEvidence.cortexInsightCount || 0,
        cortex_insights: (postCaseEvidence.cortexInsights || []).slice(0, 8),
        primary_cortex_statuses: postCaseEvidence.primaryCortexStatuses || [],
      },
      null,
      2,
    ),
  );
}

async function cleanupConversationIds(db, conversationIds) {
  if (!db) return { status: "skipped", reason: "db_unavailable" };
  const uniqueConversationIds = [
    ...new Set(
      (conversationIds || []).filter(
        (conversationId) => conversationId && conversationId !== "new",
      ),
    ),
  ];
  if (uniqueConversationIds.length === 0) {
    return { status: "complete", conversationCount: 0, messageCount: 0 };
  }
  const messageResult = await db
    .collection("messages")
    .deleteMany({ conversationId: { $in: uniqueConversationIds } });
  const conversationResult = await db
    .collection("conversations")
    .deleteMany({ conversationId: { $in: uniqueConversationIds } });
  return {
    status: "complete",
    conversationCount: conversationResult.deletedCount,
    messageCount: messageResult.deletedCount,
  };
}

async function cleanupEvalConversations(db, results, extraConversationIds = []) {
  if (!db) return { status: "skipped", reason: "db_unavailable" };
  const qaRequestMessageIds = [
    ...new Set(
      results
        .flatMap((result) => result.qaRequestMessageIds || [])
        .filter(Boolean),
    ),
  ];
  const requestRows = qaRequestMessageIds.length
    ? await db
        .collection("messages")
        .find({ messageId: { $in: qaRequestMessageIds } })
        .project({ conversationId: 1 })
        .toArray()
    : [];
  return cleanupConversationIds(db, [
    ...extraConversationIds,
    ...results.map((result) => result.finalMeta?.conversationId),
    ...requestRows.map((row) => row.conversationId),
  ]);
}

async function runLiveCases(args, promptBank, token, db = null, qaAuth = null) {
  const runnableCases = runnablePromptCases(promptBank, args).slice(
    0,
    args.maxCases,
  );
  const results = [];
  const env = loadLocalEnv();
  let feelingsRestoreState = null;
  let feelingsRestoreAttempts = 0;
  let feelingsRestoreError = null;
  let conversationRecallRestoreState = null;
  let conversationRecallRestoreResult = null;
  let conversationRecallRestoreError = null;
  let qaCleanup = null;
  let qaCleanupError = null;
  const fixtureConversationIds = [];

  try {
    for (const [caseIndex, testCase] of runnableCases.entries()) {
      if (caseIndex > 0 && Number(testCase.interCaseDelayMs) > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, Number(testCase.interCaseDelayMs)),
        );
      }
      const startedAt = Date.now();
      const promptFrameCursor = capturePromptFrameCursor();
      const seedPrompts = normalizeSeedPrompts(testCase);
      const conversationRecallFixture = conversationRecallFixtureFor(
        testCase,
        crypto.randomBytes(8).toString("hex"),
      );
      let conversationId = "new";
      let parentMessageId = NO_PARENT;
      const seedEvidence = [];
      const fixtureEvidence = [];
      let failedSeed = null;

      const voiceOutputFixture = voiceOutputFixtureFor(testCase);
      if (voiceOutputFixture) {
        fixtureEvidence.push({
          fixture: "voice_output",
          configured: voiceOutputFixture,
        });
      }

      if (feelingsFixtureFor(testCase)) {
        const fixtureResult = await applyFeelingsFixtureWithRetry({
          args,
          token,
          testCase,
        }).catch((error) => ({
          error: `feelings_fixture_failed:${scrubForPublic(error.message || "unknown")}`,
        }));
        if (fixtureResult?.restoreState && !feelingsRestoreState) {
          feelingsRestoreState = fixtureResult.restoreState;
        }
        if (!fixtureResult?.configuredState) {
          results.push({
            caseId: testCase.id,
            familyId: testCase.familyId,
            surface: testCase.surface || "web",
            status: "failed_to_prepare_fixture",
            durationMs: Date.now() - startedAt,
            error: fixtureResult?.error || "feelings_fixture_failed",
            requestHash: hashValue({ fixture: "feelings_state" }),
            responseHash: "",
            responsePreview: "",
            responseForJudge: "",
            eventEvidenceForJudge: "none",
            promptFrameEvidenceForJudge:
              summarizePromptFrameDelta(promptFrameCursor),
            postCaseEvidenceForJudge: "none",
            eventCount: 0,
            finalMeta: {},
            seedEvidence,
            fixtureEvidence,
            privateEvents: [],
          });
          continue;
        }
        fixtureEvidence.push(fixtureResult.evidence);
      }

      if (conversationRecallFixture) {
        const recallFixture = conversationRecallFixture;
        const fixtureResult = await applyConversationRecallFixture({
          args,
          token,
          db,
          userId: qaAuth?.userId,
          testCase,
        }).catch((error) => ({
          error: `conversation_recall_fixture_failed:${scrubForPublic(error.message || "unknown")}`,
        }));
        if (fixtureResult?.restoreState && !conversationRecallRestoreState) {
          conversationRecallRestoreState = fixtureResult.restoreState;
        }
        if (!fixtureResult?.evidence) {
          results.push({
            caseId: testCase.id,
            familyId: testCase.familyId,
            surface: testCase.surface || "web",
            status: "failed_to_prepare_fixture",
            durationMs: Date.now() - startedAt,
            error: fixtureResult?.error || "conversation_recall_fixture_failed",
            requestHash: hashValue({
              fixture: "conversation_recall_preference",
            }),
            responseHash: "",
            responsePreview: "",
            responseForJudge: "",
            eventEvidenceForJudge: "none",
            promptFrameEvidenceForJudge:
              summarizePromptFrameDelta(promptFrameCursor),
            postCaseEvidenceForJudge: "none",
            eventCount: 0,
            finalMeta: {},
            seedEvidence,
            fixtureEvidence,
            privateEvents: [],
          });
          continue;
        }
        fixtureEvidence.push(fixtureResult.evidence);
        if (recallFixture.seedCorpusPrompts.length > 0) {
          const corpusFixture = await insertConversationRecallCorpusFixture({
            db,
            userId: qaAuth?.userId,
            agentId: args.agentId,
            prompts: recallFixture.seedCorpusPrompts,
          }).catch((error) => ({
            error: `conversation_recall_corpus_fixture_failed:${scrubForPublic(error.message || "unknown")}`,
          }));
          if (!corpusFixture?.conversationId) {
            results.push({
              caseId: testCase.id,
              familyId: testCase.familyId,
              surface: testCase.surface || "web",
              status: "failed_to_prepare_fixture",
              durationMs: Date.now() - startedAt,
              error: corpusFixture?.error || "conversation_recall_corpus_fixture_failed",
              requestHash: hashValue({ fixture: "conversation_recall_corpus" }),
              responseHash: "",
              responsePreview: "",
              responseForJudge: "",
              eventEvidenceForJudge: "none",
              promptFrameEvidenceForJudge: summarizePromptFrameDelta(promptFrameCursor),
              postCaseEvidenceForJudge: "none",
              eventCount: 0,
              finalMeta: {},
              seedEvidence,
              fixtureEvidence,
              privateEvents: [],
            });
            continue;
          }
          fixtureConversationIds.push(corpusFixture.conversationId);
          fixtureEvidence.push(corpusFixture.evidence);
          if (recallFixture.requireSemanticRetrieval) {
            const refreshedCorpus = await (async () => {
              await patchConversationRecallPreference({
                args,
                token,
                enabled: true,
              });
              return waitForConversationRecallCorpusRefresh({
                db,
                userId: qaAuth?.userId,
                previousState: fixtureResult.corpusStateBeforeFixture,
              });
            })().catch((error) => ({
              error: `conversation_recall_semantic_fixture_failed:${scrubForPublic(error.message || "unknown")}`,
            }));
            if (refreshedCorpus?.error) {
              results.push({
                caseId: testCase.id,
                familyId: testCase.familyId,
                surface: testCase.surface || "web",
                status: "failed_to_prepare_fixture",
                durationMs: Date.now() - startedAt,
                error: refreshedCorpus.error,
                requestHash: hashValue({ fixture: "conversation_recall_semantic_index" }),
                responseHash: "",
                responsePreview: "",
                responseForJudge: "",
                eventEvidenceForJudge: "none",
                promptFrameEvidenceForJudge: summarizePromptFrameDelta(promptFrameCursor),
                postCaseEvidenceForJudge: "none",
                eventCount: 0,
                finalMeta: {},
                seedEvidence,
                fixtureEvidence,
                privateEvents: [],
              });
              continue;
            }
            fixtureEvidence.push({
              fixture: "conversation_recall_semantic_index",
              configured: true,
              waitedMs: refreshedCorpus.waitedMs,
              sourceDigestHash: hashValue(refreshedCorpus.sourceDigest),
              uploadedDigestHash: hashValue(refreshedCorpus.uploadedDigest),
            });
          }
        }
      }

      if (needsStarterMorningBriefingFixture(testCase)) {
        const fixtureResult = await applyStarterMorningBriefingFixture({
          args,
          env,
          userId: qaAuth?.userId,
          agentId: args.agentId,
        }).catch((error) => ({
          ok: false,
          reason: `fixture_failed:${scrubForPublic(error.message || "unknown")}`,
        }));
        fixtureEvidence.push(fixtureResult);
        if (!fixtureResult.ok) {
          results.push({
            caseId: testCase.id,
            familyId: testCase.familyId,
            surface: testCase.surface || "web",
            status: "failed_to_prepare_fixture",
            durationMs: Date.now() - startedAt,
            error: fixtureResult.reason || "fixture_failed",
            requestHash: hashValue({
              fixture: fixtureResult.fixture || "starter_morning_briefing",
            }),
            responseHash: "",
            responsePreview: "",
            responseForJudge: "",
            eventEvidenceForJudge: "none",
            promptFrameEvidenceForJudge:
              summarizePromptFrameDelta(promptFrameCursor),
            postCaseEvidenceForJudge: "none",
            eventCount: 0,
            finalMeta: {},
            seedEvidence,
            fixtureEvidence,
            privateEvents: [],
          });
          continue;
        }
      }

      for (const seedText of seedPrompts) {
        const seedResult = await runChatTurn({
          args,
          token,
          testCase,
          text: seedText,
          conversationId,
          parentMessageId,
        });
        seedEvidence.push({
          ok: seedResult.ok,
          requestHash: hashValue(seedResult.payload),
          responseHash: hashValue(seedResult.stream?.text || ""),
          eventCount: seedResult.stream?.events?.length || 0,
        });
        if (
          !seedResult.ok ||
          !seedResult.finalMeta.conversationId ||
          !seedResult.finalMeta.responseMessageId
        ) {
          failedSeed = seedResult;
          break;
        }
        conversationId = seedResult.finalMeta.conversationId;
        parentMessageId = seedResult.finalMeta.responseMessageId;
      }

      if (failedSeed) {
        results.push({
          caseId: testCase.id,
          familyId: testCase.familyId,
          surface: testCase.surface || "web",
          status: "failed_to_seed",
          durationMs: Date.now() - startedAt,
          error: failedSeed.error || "seed_turn_failed",
          requestHash: hashValue(failedSeed.payload || {}),
          responseHash: hashValue(failedSeed.stream?.text || ""),
          responsePreview: responseTextForJudge(
            failedSeed.stream?.text || "",
          ).slice(0, 300),
          responseForJudge: responseTextForJudge(
            failedSeed.stream?.text || "",
          ).slice(0, 4000),
          eventEvidenceForJudge: summarizeEventsForJudge(
            failedSeed.stream?.events || [],
          ),
          promptFrameEvidenceForJudge:
            summarizePromptFrameDelta(promptFrameCursor),
          postCaseEvidenceForJudge: "none",
          eventCount: failedSeed.stream?.events?.length || 0,
          finalMeta: failedSeed.finalMeta || {},
          seedEvidence,
          fixtureEvidence,
          privateEvents: failedSeed.stream?.events || [],
        });
        continue;
      }

      const promptText = buildCaseText(testCase, {
        includeSetup: seedPrompts.length === 0,
      });
      const turn = await runChatTurnWithRetry({
        args,
        token,
        testCase,
        text: promptText,
        conversationId,
        parentMessageId,
      });
      const stream = turn.stream || {
        ok: false,
        events: [],
        text: "",
        error: turn.error,
      };

      const responseText = stream.text || "";
      const visibleResponseText = stripDeliveryControlsForPreview(responseText);
      const emptyResponseAllowed = caseAllowsEmptyResponse(testCase);
      const completed =
        stream.ok && (visibleResponseText.trim() || emptyResponseAllowed);
      const turnEvidence = {
        finalMeta: turn.finalMeta || {},
        hasCortexActivation: hasCortexActivation(stream.events),
      };
      const observeMs = turnEvidence.hasCortexActivation
        ? args.postCaseObserveMs
        : Math.min(args.postCaseObserveMs, 2500);
      const postCaseEvidence = await observePostCaseDbEvidence({
        db,
        result: turnEvidence,
        maxObserveMs: observeMs,
        followUpGraceMs: args.followUpGraceMs,
      });
      const configuredFeelingsState = feelingsFixtureFor(testCase)
        ? fixtureEvidence.find((item) => item.fixture === "feelings_state")
            ?.configured
        : null;
      const feelingsReactionEvidence = feelingsFixtureFor(testCase)
        ?.observeReaction
        ? await observeFeelingsReaction({
            args,
            token,
            forbiddenInnerStateTokens:
              feelingsFixtureFor(testCase)?.forbiddenInnerStateTokens || [],
            beforeState: {
              version: configuredFeelingsState.version,
              trailLength: configuredFeelingsState.trailLength,
              trailCursorTimestamp:
                configuredFeelingsState.trailCursorTimestamp,
              bands: Object.fromEntries(
                Object.entries(configuredFeelingsState.bands).map(
                  ([band, values]) => [
                    band,
                    { current: values.current, baseline: values.nature },
                  ],
                ),
              ),
            },
          })
        : null;
      const eventEvidence = summarizeEventsForJudge(stream.events);
      const rawStreamedText = voiceOutputFixture
        ? extractRawStreamedText(stream.events)
        : "";
      const voiceMarkerValidation = validateVoiceMarkerEvidence(
        testCase,
        rawStreamedText || responseText,
      );
      if (voiceMarkerValidation.evidence) {
        voiceMarkerValidation.evidence.evidenceSource = rawStreamedText
          ? "raw_stream"
          : "visible_final_fallback";
      }
      const eventEvidenceForJudge = [
        eventEvidence,
        feelingsReactionEvidence
          ? `Feelings reaction persistence evidence:\n${JSON.stringify(feelingsReactionEvidence, null, 2)}`
          : "",
        voiceMarkerValidation.evidence
          ? `Voice marker evidence:\n${JSON.stringify(voiceMarkerValidation.evidence, null, 2)}`
          : "",
      ]
        .filter(Boolean)
        .join("\n\n");
      const feelingsDeterministicFailures = validateFeelingsReactionEvidence(
        feelingsFixtureFor(testCase),
        feelingsReactionEvidence,
      );
      const conversationRecallExecution =
        await auditConversationRecallExecution({
          env,
          responseMessageId: turnEvidence.finalMeta?.responseMessageId,
          fixture: conversationRecallFixture,
          responseText: visibleResponseText,
          responseEvents: stream.events,
        });
      if (conversationRecallExecution.evidence) {
        fixtureEvidence.push(conversationRecallExecution.evidence);
      }
      const deterministicFailures = [
        ...feelingsDeterministicFailures,
        ...voiceMarkerValidation.failures,
        ...conversationRecallExecution.failures,
      ];
      const deterministicallyCompleted =
        Boolean(completed) && deterministicFailures.length === 0;

      results.push({
        caseId: testCase.id,
        familyId: testCase.familyId,
        surface: testCase.surface || "web",
        status: deterministicallyCompleted ? "completed" : "failed",
        durationMs: Date.now() - startedAt,
        firstVisibleReplyMs: turn.timing?.firstVisibleReplyMs ?? null,
        error:
          stream.error ||
          deterministicFailures[0] ||
          (completed ? null : "empty_visible_response"),
        requestHash: hashValue(turn.payload || {}),
        responseHash: hashValue(visibleResponseText),
        responsePreview: responseTextForJudge(responseText).slice(0, 300),
        responseForJudge: responseTextForJudge(responseText).slice(0, 4000),
        eventEvidenceForJudge,
        promptFrameEvidenceForJudge:
          summarizePromptFrameDelta(promptFrameCursor),
        postCaseEvidenceForJudge:
          summarizePostCaseEvidenceForJudge(postCaseEvidence),
        eventCount: stream.events.length,
        finalMeta: turnEvidence.finalMeta,
        hasCortexActivation: turnEvidence.hasCortexActivation,
        hasRuntimeHold: hasRuntimeHold(stream.events),
        seedEvidence,
        fixtureEvidence,
        feelingsReactionEvidence,
        feelingsDeterministicFailures,
        postCaseEvidence,
        qaRequestMessageIds: turn.qaRequestMessageIds,
        turnAttemptCount: turn.attemptCount,
        privateEvents: stream.events,
      });
    }
  } finally {
    if (feelingsRestoreState) {
      try {
        feelingsRestoreAttempts = await restoreFeelingsFixtureWithRetry({
          args,
          token,
          restoreState: feelingsRestoreState,
        });
      } catch (error) {
        feelingsRestoreError = `feelings_fixture_restore_failed:${scrubForPublic(error.message || "unknown")}`;
      }
    }
    if (conversationRecallRestoreState) {
      try {
        conversationRecallRestoreResult =
          await restoreConversationRecallFixture({
            args,
            token,
            db,
            restoreState: conversationRecallRestoreState,
          });
      } catch (error) {
        conversationRecallRestoreError = `conversation_recall_fixture_restore_failed:${scrubForPublic(error.message || "unknown")}`;
      }
    }
    try {
      qaCleanup = await cleanupEvalConversations(db, results, fixtureConversationIds);
    } catch (error) {
      qaCleanupError = `qa_conversation_cleanup_failed:${scrubForPublic(error.message || "unknown")}`;
    }
  }

  for (const result of results) {
    if (result.familyId === "feelings_embodiment_and_reaction") {
      result.fixtureRestoration = feelingsRestoreError
        ? { status: "failed", error: feelingsRestoreError }
        : { status: "restored", attempts: feelingsRestoreAttempts };
      result.qaCleanup = qaCleanupError
        ? { status: "failed", error: qaCleanupError }
        : qaCleanup;
    }
    if (
      result.fixtureEvidence?.some(
        (item) => item.fixture === "conversation_recall_preference",
      )
    ) {
      result.fixtureRestoration = conversationRecallRestoreError
        ? { status: "failed", error: conversationRecallRestoreError }
        : conversationRecallRestoreResult;
      result.qaCleanup = qaCleanupError
        ? { status: "failed", error: qaCleanupError }
        : qaCleanup;
    }
  }
  if (feelingsRestoreError) {
    results.push({
      caseId: "feelings_fixture_restore",
      familyId: "feelings_embodiment_and_reaction",
      surface: "web",
      status: "failed_to_restore_fixture",
      durationMs: 0,
      error: feelingsRestoreError,
      requestHash: "",
      responseHash: "",
      responsePreview: "",
      responseForJudge: "",
      eventEvidenceForJudge: "none",
      promptFrameEvidenceForJudge: "none",
      postCaseEvidenceForJudge: "none",
      eventCount: 0,
      finalMeta: {},
      seedEvidence: [],
      fixtureEvidence: [],
      privateEvents: [],
      fixtureRestoration: { status: "failed", error: feelingsRestoreError },
    });
  }
  if (qaCleanupError) {
    results.push({
      caseId: "qa_conversation_cleanup",
      familyId: "feelings_embodiment_and_reaction",
      surface: "web",
      status: "failed_to_clean_qa_conversations",
      durationMs: 0,
      error: qaCleanupError,
      requestHash: "",
      responseHash: "",
      responsePreview: "",
      responseForJudge: "",
      eventEvidenceForJudge: "none",
      promptFrameEvidenceForJudge: "none",
      postCaseEvidenceForJudge: "none",
      eventCount: 0,
      finalMeta: {},
      seedEvidence: [],
      fixtureEvidence: [],
      privateEvents: [],
      qaCleanup: { status: "failed", error: qaCleanupError },
    });
  }
  if (conversationRecallRestoreError) {
    results.push({
      caseId: "conversation_recall_fixture_restore",
      familyId: "memory_recall",
      surface: "voice",
      status: "failed_to_restore_fixture",
      durationMs: 0,
      error: conversationRecallRestoreError,
      requestHash: "",
      responseHash: "",
      responsePreview: "",
      responseForJudge: "",
      eventEvidenceForJudge: "none",
      promptFrameEvidenceForJudge: "none",
      postCaseEvidenceForJudge: "none",
      eventCount: 0,
      finalMeta: {},
      seedEvidence: [],
      fixtureEvidence: [],
      privateEvents: [],
      fixtureRestoration: {
        status: "failed",
        error: conversationRecallRestoreError,
      },
    });
  }

  return results;
}

function casesByIdFromPromptBank(promptBank) {
  return new Map(
    runnablePromptCases(promptBank).map((testCase) => [testCase.id, testCase]),
  );
}

function buildDuplicateResponseQualityFailures(liveResults, promptBank) {
  const casesById = casesByIdFromPromptBank(promptBank);
  const responseHashGroups = liveResults.reduce((acc, result) => {
    if (!result.responseHash || result.status !== "completed") {
      return acc;
    }
    acc[result.responseHash] = acc[result.responseHash] || [];
    acc[result.responseHash].push(result.caseId);
    return acc;
  }, {});
  return Object.entries(responseHashGroups)
    .filter(([, caseIds]) => caseIds.length > 1)
    .map(([responseHash, caseIds]) => {
      const groupedResults = caseIds
        .map((caseId) => liveResults.find((result) => result.caseId === caseId))
        .filter(Boolean);
      const cases = caseIds
        .map((caseId) => casesById.get(caseId))
        .filter(Boolean);
      const allowedByCaseContract =
        cases.length > 0 &&
        cases.every((testCase) => caseAllowsDuplicateResponse(testCase));
      const allowedResolvedHolds =
        groupedResults.length > 0 &&
        groupedResults.every(resultHasResolvedRuntimeHoldEvidence);
      return {
        responseHash,
        caseIds,
        allowed: allowedByCaseContract || allowedResolvedHolds,
      };
    })
    .filter((group) => !group.allowed);
}

function buildUnresolvedAsyncQualityFailures(liveResults, promptBank) {
  const casesById = casesByIdFromPromptBank(promptBank);
  return liveResults.flatMap((result) => {
    const testCase = casesById.get(result.caseId);
    if (
      !testCase ||
      result.status !== "completed" ||
      !result.hasCortexActivation ||
      !result.hasRuntimeHold ||
      caseAllowsEmptyResponse(testCase) ||
      caseAllowsUnresolvedAsync(testCase)
    ) {
      return [];
    }
    const evidence = result.postCaseEvidence || {};
    const pendingStatuses = (evidence.primaryCortexStatuses || []).filter(
      isPendingCortexStatus,
    );
    const hasResolvedUserVisibleOrInsightEvidence =
      Number(evidence.delayedMessageCount || 0) > 0 ||
      Number(evidence.cortexInsightCount || 0) > 0;
    if (
      pendingStatuses.length === 0 ||
      hasResolvedUserVisibleOrInsightEvidence
    ) {
      return [];
    }
    return [
      {
        caseId: result.caseId,
        responseHash: result.responseHash,
        pendingStatuses,
      },
    ];
  });
}

function writeReports({
  args,
  promptBank,
  runtime,
  login,
  sourceHashes,
  liveResults,
  blockedReason,
  semanticJudge,
}) {
  ensureDir(args.outputDir);
  ensureDir(path.dirname(args.publicReport));

  const memoryRecallBank = validateFrozenMemoryRecallBank(promptBank);
  const allCases = flattenPromptCases(promptBank);
  const runnableCases = runnablePromptCases(promptBank, args);
  const selectedCaseCount = Math.min(args.maxCases, runnableCases.length);
  const selectedCaseLimitLabel =
    args.maxCases >= runnableCases.length
      ? `all (${runnableCases.length})`
      : String(args.maxCases);
  const allCompleted =
    liveResults.length > 0 &&
    liveResults.every((result) => result.status === "completed");
  const fullCoverage =
    allCompleted &&
    liveResults.length === allCases.length &&
    liveResults.length === runnableCases.length;
  const responseHashGroups = liveResults.reduce((acc, result) => {
    if (!result.responseHash) {
      return acc;
    }
    acc[result.responseHash] = acc[result.responseHash] || [];
    acc[result.responseHash].push(result.caseId);
    return acc;
  }, {});
  const duplicateResponseHashes = Object.entries(responseHashGroups)
    .filter(([, caseIds]) => caseIds.length > 1)
    .map(([responseHash, caseIds]) => ({ responseHash, caseIds }));
  const duplicateResponseQualityFailures =
    buildDuplicateResponseQualityFailures(liveResults, promptBank);
  const unresolvedAsyncQualityFailures = buildUnresolvedAsyncQualityFailures(
    liveResults,
    promptBank,
  );
  const judgedResults = liveResults.filter(
    (result) => result.semanticJudge?.status === "judged",
  );
  const semanticFailedResults = liveResults.filter(
    (result) =>
      result.semanticJudge?.status === "judged" &&
      result.semanticJudge.pass !== true,
  );
  const semanticUnavailableResults = liveResults.filter(
    (result) => result.semanticJudge?.status === "unavailable",
  );
  const semanticJudgeBlocked = Boolean(semanticJudge?.blockedReason);
  const completionFailed = liveResults.some(
    (result) => result.status !== "completed",
  );
  const qualityFailed =
    duplicateResponseQualityFailures.length > 0 ||
    unresolvedAsyncQualityFailures.length > 0;
  const semanticFailed =
    Boolean(args.semanticJudge) && semanticFailedResults.length > 0;
  const status = blockedReason
    ? "blocked"
    : completionFailed
      ? "failed_completion"
      : semanticJudgeBlocked
        ? "blocked_semantic_judge"
        : semanticFailed
          ? "semantic_failed"
          : qualityFailed
            ? "quality_failed"
            : fullCoverage && args.semanticJudge
              ? "completed_full_semantic_passed"
              : fullCoverage
                ? "completed_full"
                : allCompleted && args.semanticJudge
                  ? "partial_semantic_passed"
                  : allCompleted
                    ? "partial_baseline"
                    : "partial_or_failed";
  const summary = {
    generatedAt: new Date().toISOString(),
    status,
    blockedReason,
    runnerHash: hashFileIfPresent(__filename),
    apiBaseHash: hashValue(args.apiBase),
    runLiveRequested: args.runLive,
    promptBankHash: hashFileIfPresent(args.promptBank),
    memoryRecallBank,
    agentIdHash: hashValue(args.agentId),
    promptFamilies: (promptBank.families || []).length,
    promptCases: allCases.length,
    runnablePromptCases: runnableCases.length,
    filters: {
      family: args.family || null,
      caseId: args.caseId || null,
      caseIds: args.caseIds.length ? args.caseIds : null,
      surface: args.surface || null,
      promptId: args.promptId || null,
    },
    selectedCaseLimit: selectedCaseLimitLabel,
    selectedCaseCount,
    surfacesInBank: [
      ...new Set(allCases.map((testCase) => testCase.surface || "web")),
    ].sort(),
    surfacesRun: [
      ...new Set(liveResults.map((result) => result.surface || "web")),
    ].sort(),
    runtime,
    debugLocalPromptFrameEnabled: debugLocalPromptFrameEnabled(),
    login: login?.public || null,
    sourceHashes,
    resultCount: liveResults.length,
    completedCount: liveResults.filter(
      (result) => result.status === "completed",
    ).length,
    failedCount: liveResults.filter((result) => result.status !== "completed")
      .length,
    deterministicContractPassedCount: liveResults.filter(
      (result) => result.status === "completed",
    ).length,
    deterministicContractFailedCount: liveResults.filter(
      (result) => result.status !== "completed",
    ).length,
    retriedTurnCount: liveResults.filter(
      (result) => Number(result.turnAttemptCount || 1) > 1,
    ).length,
    totalTurnAttempts: liveResults.reduce(
      (total, result) => total + Number(result.turnAttemptCount || 1),
      0,
    ),
    visibleReplyLatencyMs: summarizeLatencyMs(
      liveResults.map((result) => result.firstVisibleReplyMs),
    ),
    completionLatencyMs: summarizeLatencyMs(
      liveResults.map((result) => result.durationMs),
    ),
    behavioralGrading: semanticJudge?.enabled
      ? semanticJudgeLabel(args, semanticJudge)
      : "disabled",
    judgeModelHash: semanticJudge?.enabled
      ? hashValue(
          `${args.judgeRoute}:${args.judgeRoute === "local-agent" ? args.judgeAgentId : `${args.judgeEndpoint}:${args.judgeModel}`}`,
        )
      : null,
    semanticJudgedCount: judgedResults.length,
    semanticPassedCount: judgedResults.filter(
      (result) => result.semanticJudge?.pass === true,
    ).length,
    semanticFailedCount: semanticFailedResults.length,
    semanticJudgeUnavailableCount: semanticUnavailableResults.length,
    semanticJudgeBlockedReason: semanticJudge?.blockedReason || null,
    duplicateResponseHashes,
    duplicateResponseQualityFailures,
    unresolvedAsyncQualityFailures,
  };

  const privateJsonPath = path.join(args.outputDir, "exact-model-eval.json");
  fs.writeFileSync(
    privateJsonPath,
    JSON.stringify(
      {
        summary,
        args: {
          apiBase: args.apiBase,
          promptBank: args.promptBank,
          qaEmailHash: hashValue(args.qaEmail),
          agentIdHash: hashValue(args.agentId),
          family: args.family || null,
          caseId: args.caseId || null,
          caseIds: args.caseIds.length ? args.caseIds : null,
          surface: args.surface || null,
          promptId: args.promptId || null,
          localJwtFallback: args.localJwtFallback,
          maxCases: args.maxCases,
          timeoutMs: args.timeoutMs,
          postCaseObserveMs: args.postCaseObserveMs,
          followUpGraceMs: args.followUpGraceMs,
          semanticJudge: args.semanticJudge,
          judgeRoute: args.judgeRoute,
          judgeModelHash: args.semanticJudge
            ? hashValue(
                `${args.judgeRoute}:${args.judgeRoute === "local-agent" ? args.judgeAgentId : `${args.judgeEndpoint}:${args.judgeModel}`}`,
              )
            : null,
        },
        liveResults,
      },
      null,
      2,
    ),
  );

  const publicLines = [
    "<!-- qa-evidence-exempt: Controlled prompt-registry completion artifact; full-view user-grade acceptance belongs in the owning feature run report. -->",
    "",
    "# Prompt Registry Slice: Exact-Model Completion Baseline",
    "",
    `Generated: ${summary.generatedAt}`,
    "",
    "## Status",
    "",
    `- Status: ${summary.status}`,
    `- Live run requested: ${summary.runLiveRequested ? "yes" : "no"}`,
    `- Blocked reason: ${summary.blockedReason || "none"}`,
    `- Prompt families: ${summary.promptFamilies}`,
    `- Prompt cases: ${summary.promptCases}`,
    `- Frozen continuity bank: ${summary.memoryRecallBank.bankVersion} / ${summary.memoryRecallBank.bankHash} / ${summary.memoryRecallBank.caseCount} cases`,
    `- Agent hash: ${summary.agentIdHash}`,
    `- Runner hash: ${summary.runnerHash || "missing"}`,
    `- Runnable cases for this runner: ${summary.runnablePromptCases}`,
    `- Selected case limit: ${summary.selectedCaseLimit}`,
    `- Post-case observation window ms: ${args.postCaseObserveMs}`,
    `- Async follow-up grace after cortex completion ms: ${args.followUpGraceMs}`,
    `- Result count: ${summary.resultCount}`,
    `- Completed: ${summary.completedCount}`,
    `- Failed/blocked: ${summary.failedCount}`,
    `- Deterministic fixture contracts passed: ${summary.deterministicContractPassedCount}`,
    `- Deterministic fixture contracts failed: ${summary.deterministicContractFailedCount}`,
    `- Retried main turns: ${summary.retriedTurnCount}`,
    `- Total main-turn attempts: ${summary.totalTurnAttempts}`,
    `- Visible-reply latency ms (mean/median/p95/max): ${
      summary.visibleReplyLatencyMs
        ? [
            summary.visibleReplyLatencyMs.mean,
            summary.visibleReplyLatencyMs.median,
            summary.visibleReplyLatencyMs.p95,
            summary.visibleReplyLatencyMs.max,
          ]
            .map((value) => Number(value).toFixed(1))
            .join("/")
        : "not observed"
    }`,
    `- Full-case latency ms (mean/median/p95/max): ${
      summary.completionLatencyMs
        ? [
            summary.completionLatencyMs.mean,
            summary.completionLatencyMs.median,
            summary.completionLatencyMs.p95,
            summary.completionLatencyMs.max,
          ]
            .map((value) => Number(value).toFixed(1))
            .join("/")
        : "not observed"
    }`,
    `- Optional LLM semantic grading: ${summary.behavioralGrading}`,
    `- Semantic judged: ${summary.semanticJudgedCount}`,
    `- Semantic passed: ${summary.semanticPassedCount}`,
    `- Semantic failed: ${summary.semanticFailedCount}`,
    `- Semantic judge unavailable: ${summary.semanticJudgeUnavailableCount}`,
    `- Semantic judge blocked reason: ${summary.semanticJudgeBlockedReason || "none"}`,
    `- Judge model hash: ${summary.judgeModelHash || "not used"}`,
    `- Duplicate response hashes: ${summary.duplicateResponseHashes.length}`,
    `- Duplicate response quality failures: ${summary.duplicateResponseQualityFailures.length}`,
    `- Unresolved async quality failures: ${summary.unresolvedAsyncQualityFailures.length}`,
    `- Surfaces in bank: ${summary.surfacesInBank.join(", ") || "none"}`,
    `- Surface metadata exercised: ${summary.surfacesRun.join(", ") || "none"}`,
    "",
    "## Runtime Gate",
    "",
    `- API base hash: ${summary.apiBaseHash}`,
    `- Runtime identity: ${summary.runtime.identity.ok ? "pass" : "fail"}`,
    `- Runtime reasons: ${summary.runtime.identity.reasons.join(", ") || "none"}`,
    `- App title: ${summary.runtime.identity.public.appTitle}`,
    `- Connected-account mode: ${summary.runtime.identity.public.connectedAccountsEnabled ? "enabled" : "not enabled"}`,
    `- Prompt debug-local gate: ${summary.debugLocalPromptFrameEnabled ? "enabled" : "disabled"}`,
    `- QA auth mode: ${summary.login?.authMode || "not attempted"}`,
    "",
    "## Source Hashes",
    "",
    `- Agent source hash: ${summary.sourceHashes.source_agent || "missing"}`,
    `- LibreChat source hash: ${summary.sourceHashes.source_librechat || "missing"}`,
    `- Compiled LibreChat hash: ${summary.sourceHashes.compiled_librechat || "missing"}`,
    "",
    "## Results",
    "",
    "| Case | Family | Surface | Status | Attempts | Semantic | Visible ms | Duration ms | Response hash | Error |",
    "| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |",
    ...liveResults.map(
      (result) =>
        `| ${scrubForPublic(result.caseId)} | ${scrubForPublic(result.familyId)} | ${scrubForPublic(result.surface)} | ${result.status} | ${Number(result.turnAttemptCount || 1)} | ${
          result.semanticJudge?.status === "unavailable"
            ? "unavailable"
            : result.semanticJudge
              ? result.semanticJudge.pass
                ? `pass ${Number(result.semanticJudge.score || 0).toFixed(2)}`
                : `fail ${Number(result.semanticJudge.score || 0).toFixed(2)} ${scrubForPublic(result.semanticJudge.failureMode || "")}`
              : "not run"
        } | ${result.firstVisibleReplyMs ?? ""} | ${result.durationMs || 0} | ${result.responseHash || ""} | ${scrubForPublic(result.error || result.semanticJudge?.error || "")} |`,
    ),
    "",
    "## Quality Gate Failures",
    "",
    summary.duplicateResponseQualityFailures.length
      ? `- Duplicate non-silent response groups: ${summary.duplicateResponseQualityFailures
          .map(
            (group) =>
              `${group.responseHash} (${group.caseIds.map(scrubForPublic).join(", ")})`,
          )
          .join("; ")}`
      : "- Duplicate non-silent response groups: none",
    summary.unresolvedAsyncQualityFailures.length
      ? `- Unresolved async holds: ${summary.unresolvedAsyncQualityFailures
          .map(
            (failure) =>
              `${scrubForPublic(failure.caseId)} (${failure.pendingStatuses.join(", ")})`,
          )
          .join("; ")}`
      : "- Unresolved async holds: none",
    "",
    "## Notes",
    "",
    "- Raw eval JSON and response previews are private-only.",
    "- Public output stores hashes, counts, statuses, and sanitized errors only.",
    "- Case status always includes local deterministic fixture contracts (required/forbidden response fragments, declared-tool provenance, native-substitution bans, and fixture restoration when configured). Optional LLM semantic grading is an additional fluency/meaning signal, not the deterministic pass gate.",
    "- When semantic judging is enabled, the runner uses a structured JSON judge and validates the returned shape locally. The `openai-direct` judge route uses provider-enforced JSON Schema; local account routes use prompt-constrained JSON plus local schema validation.",
    "- Duplicate response hashes are informational for intentional silence/suppression cases and resolved runtime holds, but fail the run when unrelated non-silent final answers collapse into the same visible answer.",
    "- Runtime-hold responses fail the run when cortex/tool work remains only pending after the observation window and no delayed or insight evidence arrived.",
    "- Semantic judge prompts and raw results are private-only; this public report stores only pass/fail counts, scores, hashes, and sanitized failure modes.",
    "- The harness fails closed on wrong runtime identity before model calls.",
    "- Source YAML and compiled YAML hashes are reported separately and are expected to differ when promptRefs render into plain LibreChat strings.",
    "- Treat prompt-bundle and runtime-config drift checks, not source-vs-compiled YAML hash equality, as the live prompt-registry drift gate.",
    "- `partial_baseline` and `partial_semantic_passed` mean the run completed only the selected subset, not the full prompt bank.",
    "- This completion-baseline runner uses the main chat endpoint with surface metadata; true voice, Telegram, scheduler, Wing, and Listen-Only surface runners remain separate gates.",
    "",
  ];

  fs.writeFileSync(args.publicReport, `${publicLines.join("\n")}\n`);

  return {
    summary,
    privateJsonPath,
    publicReport: args.publicReport,
  };
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const promptBank = readJson(args.promptBank);
  validateFrozenMemoryRecallBank(promptBank);
  const selectedCasesForJudgePolicy = runnablePromptCases(
    promptBank,
    args,
  ).slice(0, args.maxCases);
  const semanticJudgeRequired = selectedCasesRequireSemanticJudge(
    selectedCasesForJudgePolicy,
  );
  if (
    args.runLive &&
    !args.semanticJudgeExplicitlyDisabled &&
    selectedCasesForJudgePolicy.length > 0 &&
    (semanticJudgeRequired ||
      selectedCasesForJudgePolicy.every(
        (testCase) => testCase.familyId === "feelings_embodiment_and_reaction",
      ))
  ) {
    args.semanticJudge = true;
  }
  const sourceHashes = loadSourceHashes();
  const health = await fetchText(`${args.apiBase}/health`, {}, 10_000).catch(
    (error) => ({
      ok: false,
      status: 0,
      text: error.message,
    }),
  );
  const config = await fetchJson(
    `${args.apiBase}/api/config`,
    {},
    10_000,
  ).catch((error) => ({
    ok: false,
    status: 0,
    body: { error: error.message },
  }));
  const identity = runtimeIdentityVerdict(config);
  const runtime = {
    health: {
      ok: health.ok,
      status: health.status,
      bodyHash: hashValue(health.text || ""),
    },
    identity,
  };

  let blockedReason = null;
  let login = null;
  let liveResults = [];
  let semanticJudge = {
    enabled: args.semanticJudge,
    blockedReason: null,
    results: [],
  };
  let dbHandle = null;
  let rawFeelingsBackup = null;
  let rawFeelingsRestore = null;
  let rawFeelingsRestoreError = null;
  let judgeCleanup = null;
  let judgeCleanupError = null;
  let evalLease = null;

  if (!health.ok) {
    blockedReason = `api_health_http_${health.status}`;
  } else if (!identity.ok) {
    blockedReason = `runtime_identity_failed:${identity.reasons.join(",")}`;
  } else if (debugLocalPromptFrameEnabled()) {
    blockedReason = "prompt_frame_debug_local_enabled";
  } else if (semanticJudgeRequired && !args.semanticJudge) {
    blockedReason = "semantic_judge_required_but_disabled";
  } else if (!args.runLive) {
    blockedReason = `live_eval_disabled_set_${LIVE_RUN_FLAG}_or_pass_--run-live`;
  } else {
    login = await loginQaUser(args);
    if (!login.ok) {
      blockedReason = login.reason;
    } else {
      evalLease = acquireExclusiveEvalLease();
      if (!evalLease.acquired) {
        blockedReason = evalLease.reason;
      } else {
        try {
          dbHandle = await connectLocalEvalDb();
        } catch (error) {
          dbHandle = {
            db: null,
            close: async () => {},
            reason: `db_connect_failed:${scrubForPublic(error.message || "unknown")}`,
          };
        }
        try {
        const selectedCases = runnablePromptCases(promptBank, args).slice(
          0,
          args.maxCases,
        );
        if (selectedCases.some((testCase) => feelingsFixtureFor(testCase))) {
          rawFeelingsBackup = await captureRawFeelingsState(
            dbHandle.db,
            login.userId,
          );
        }
        liveResults = await runLiveCases(
          args,
          promptBank,
          login.token,
          dbHandle.db,
          login,
        );
        semanticJudge = await judgeLiveResults(
          args,
          promptBank,
          liveResults,
          login.token,
        );
        liveResults = semanticJudge.results;
        } finally {
        try {
          judgeCleanup = await cleanupConversationIds(
            dbHandle?.db,
            semanticJudge.conversationIds || [],
          );
        } catch (error) {
          judgeCleanupError = `qa_judge_cleanup_failed:${scrubForPublic(error.message || "unknown")}`;
        }
        if (rawFeelingsBackup) {
          try {
            rawFeelingsRestore = await restoreRawFeelingsState(
              dbHandle?.db,
              rawFeelingsBackup,
            );
          } catch (error) {
            rawFeelingsRestoreError = `feelings_exact_restore_failed:${scrubForPublic(error.message || "unknown")}`;
          }
        }
        for (const result of liveResults) {
          if (result.familyId !== "feelings_embodiment_and_reaction") continue;
          if (rawFeelingsBackup) {
            result.fixtureRestoration = rawFeelingsRestoreError
              ? { status: "failed", error: rawFeelingsRestoreError }
              : rawFeelingsRestore;
          }
          const caseCleanup = result.qaCleanup || {
            status: "complete",
            conversationCount: 0,
            messageCount: 0,
          };
          result.qaCleanup = judgeCleanupError
            ? { status: "failed", error: judgeCleanupError }
            : {
                status: "complete",
                conversationCount:
                  Number(caseCleanup.conversationCount || 0) +
                  Number(judgeCleanup?.conversationCount || 0),
                messageCount:
                  Number(caseCleanup.messageCount || 0) +
                  Number(judgeCleanup?.messageCount || 0),
              };
        }
        if (rawFeelingsRestoreError || judgeCleanupError) {
          liveResults.push({
            caseId: rawFeelingsRestoreError
              ? "feelings_fixture_exact_restore"
              : "qa_judge_cleanup",
            familyId: "feelings_embodiment_and_reaction",
            surface: "web",
            status: rawFeelingsRestoreError
              ? "failed_to_restore_fixture"
              : "failed_to_clean_qa_conversations",
            durationMs: 0,
            error: rawFeelingsRestoreError || judgeCleanupError,
            requestHash: "",
            responseHash: "",
            responsePreview: "",
            responseForJudge: "",
            eventEvidenceForJudge: "none",
            promptFrameEvidenceForJudge: "none",
            postCaseEvidenceForJudge: "none",
            eventCount: 0,
            finalMeta: {},
            seedEvidence: [],
            fixtureEvidence: [],
            privateEvents: [],
          });
        }
        semanticJudge.results = liveResults;
          if (dbHandle) {
            await dbHandle.close().catch(() => {});
          }
          evalLease.release();
        }
      }
    }
  }

  const report = writeReports({
    args,
    promptBank,
    runtime,
    login,
    sourceHashes,
    liveResults,
    blockedReason,
    semanticJudge,
  });

  console.log(
    JSON.stringify(
      {
        status: report.summary.status,
        blockedReason: report.summary.blockedReason,
        resultCount: report.summary.resultCount,
        completedCount: report.summary.completedCount,
        failedCount: report.summary.failedCount,
        semanticJudgedCount: report.summary.semanticJudgedCount,
        semanticPassedCount: report.summary.semanticPassedCount,
        semanticFailedCount: report.summary.semanticFailedCount,
        semanticJudgeUnavailableCount:
          report.summary.semanticJudgeUnavailableCount,
        duplicateResponseQualityFailureCount:
          report.summary.duplicateResponseQualityFailures.length,
        unresolvedAsyncQualityFailureCount:
          report.summary.unresolvedAsyncQualityFailures.length,
        publicReport: path.relative(REPO_ROOT, report.publicReport),
        privateJsonPathHash: hashValue(report.privateJsonPath),
        privateJsonWritten: true,
      },
      null,
      2,
    ),
  );

  if (
    blockedReason ||
    liveResults.some((result) => result.status !== "completed") ||
    report.summary.duplicateResponseQualityFailures.length > 0 ||
    report.summary.unresolvedAsyncQualityFailures.length > 0 ||
    (args.semanticJudge &&
      (semanticJudge.blockedReason ||
        liveResults.some((result) => result.semanticJudge?.pass !== true)))
  ) {
    process.exitCode = 1;
  }
}

module.exports = {
  acquireExclusiveEvalLease,
  buildJudgePrompt,
  buildCaseText,
  scoreDecisionQualityJudgment,
  selectedCasesRequireSemanticJudge,
  buildIsolatedFeelingsFixtureSet,
  caseMatchesFilters,
  callConfiguredJudgeWithRetry,
  collectVoiceMarkerEvidence,
  comparisonRouteFailures,
  completionRouteIdentity,
  conversationRecallFixtureFor,
  auditConversationRecallExecution,
  insertConversationRecallCorpusFixture,
  readConversationRecallCorpusState,
  readGlassHiveRunToolAudit,
  waitForConversationRecallCorpusRefresh,
  extractRawStreamedText,
  flattenPromptCases,
  isRetryableSemanticJudgeFailure,
  judgeLiveResults,
  memoryRecallBankFingerprint,
  parseArgs,
  readConversationEvidence,
  responseTextForJudge,
  scrubForPublic,
  semanticJudgeUnavailableReason,
  summarizeLatencyMs,
  summarizePromptFrameDelta,
  validateFeelingsReactionEvidence,
  validateFrozenMemoryRecallBank,
  validateVoiceMarkerEvidence,
  FROZEN_MEMORY_RECALL_BANK_HASH,
  MEMORY_RECALL_BANK_VERSION,
};

if (require.main === module) {
  run().catch((error) => {
    console.error(
      JSON.stringify(
        {
          error: scrubForPublic(error.message),
          stack: scrubForPublic(error.stack),
        },
        null,
        2,
      ),
    );
    process.exit(1);
  });
}
