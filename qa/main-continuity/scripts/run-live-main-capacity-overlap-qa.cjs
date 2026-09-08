#!/usr/bin/env node
"use strict";

/**
 * Installed Main-capacity overlap acceptance.
 *
 * This local-only harness creates a disposable Main clone for the configured non-admin QA user,
 * submits four ordinary browser turns, and waits for the resulting stateless continuity compactor
 * to own a real host lease. It then pauses on the visible headed Chrome window so Computer can
 * submit the fifth turn. The result passes only when the fifth reply persists and every native
 * compactor generation releases its lease before interactive Main admission.
 *
 * Raw IDs and screenshots stay under App Support. Stdout contains only synthetic markers, hashes,
 * counts, and booleans. The shared saved-memory cleanup helper owns exact GlassHive cleanup.
 */

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const APP_SUPPORT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
);
const DEFAULT_GLASSHIVE_DB = path.join(
  APP_SUPPORT,
  "state",
  "runtime",
  "isolated",
  "glasshive",
  "runtime_phase1.db",
);
const DEFAULT_API_LOG = path.join(APP_SUPPORT, "logs", "helper-start.log");
const CANDIDATE_IDENTITY = path.join(
  APP_SUPPORT,
  "runtime",
  "parallel-work-artifact-identity.json",
);
const helper = require("../../memory-continuity/scripts/run-live-browser-saved-memory-qa.cjs");

const CAPACITY_SOURCE_FILES = Object.freeze([
  "viventium_v0_4/LibreChat/api/server/services/viventium/ViventiumMainCompactionService.js",
  "viventium_v0_4/LibreChat/api/server/controllers/agents/request.js",
  "viventium_v0_4/LibreChat/api/server/services/BackgroundCortexService.js",
  "viventium_v0_4/LibreChat/api/server/services/viventium/GlassHiveConversationProviderService.js",
  "viventium_v0_4/LibreChat/api/server/controllers/agents/client.js",
  "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/conversation_provider.py",
  "viventium_v0_4/GlassHive/runtime_phase1/src/workers_projects_runtime/store.py",
]);

function hash(value, length = 12) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function parseArgs(argv, env = process.env, now = new Date()) {
  const stamp = timestampSlug(now);
  const args = {
    startedAt: new Date(now),
    stamp,
    apiBase: env.VIVENTIUM_QA_API_BASE || "http://127.0.0.1:3180",
    clientBase: env.VIVENTIUM_QA_CLIENT_BASE || "http://127.0.0.1:3190",
    mainAgentId: String(env.VIVENTIUM_QA_MAIN_AGENT_ID || "").trim(),
    qaUserHash: "",
    timeoutMs: Number(env.VIVENTIUM_QA_TIMEOUT_MS || 300000),
    manualTimeoutMs: Number(env.VIVENTIUM_QA_MANUAL_TIMEOUT_MS || 600000),
    apiLog: env.VIVENTIUM_QA_API_LOG || DEFAULT_API_LOG,
    glassHiveDb: env.VIVENTIUM_QA_GLASSHIVE_DB || DEFAULT_GLASSHIVE_DB,
    privateOutputDir: path.join(
      APP_SUPPORT,
      "private-user-data",
      "qa",
      "main-continuity",
      `capacity-overlap-${stamp}`,
    ),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--main-agent-id") {
      args.mainAgentId = String(next || "").trim();
      index += 1;
    } else if (arg === "--qa-user-hash") {
      args.qaUserHash = String(next || "")
        .trim()
        .toLowerCase();
      index += 1;
    } else if (arg === "--timeout-ms") {
      args.timeoutMs = Number(next);
      index += 1;
    } else if (arg === "--manual-timeout-ms") {
      args.manualTimeoutMs = Number(next);
      index += 1;
    } else if (arg === "--api-log") {
      args.apiLog = path.resolve(String(next || ""));
      index += 1;
    } else {
      throw new Error(`unknown_argument_${String(arg || "empty")}`);
    }
  }
  args.apiBase = requireLocalHttpUrl(args.apiBase, "api_base").replace(
    /\/$/,
    "",
  );
  args.clientBase = requireLocalHttpUrl(args.clientBase, "client_base").replace(
    /\/$/,
    "",
  );
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs < 1000) {
    throw new Error("invalid_timeout_ms");
  }
  if (!Number.isFinite(args.manualTimeoutMs) || args.manualTimeoutMs < 1000) {
    throw new Error("invalid_manual_timeout_ms");
  }
  return args;
}

function requireLocalHttpUrl(value, label = "url") {
  let parsed;
  try {
    parsed = new URL(String(value || ""));
  } catch {
    throw new Error(`${label}_invalid`);
  }
  const localHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);
  if (
    parsed.protocol !== "http:" ||
    !localHosts.has(parsed.hostname) ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error(`${label}_must_be_local_http`);
  }
  return parsed.toString();
}

function assertSyntheticAgentId(value) {
  const id = String(value || "").trim();
  if (!/^agent_qa_main_capacity_[a-f0-9]{12}$/.test(id)) {
    throw new Error("invalid_synthetic_agent_id");
  }
  return id;
}

function assertOwnerId(value) {
  const id = String(value || "").trim();
  if (!/^[a-f0-9]{24}$/i.test(id)) throw new Error("invalid_owner_id");
  return id;
}

function assertRunId(value) {
  const id = String(value || "").trim();
  if (!/^run_[a-f0-9]{10}$/i.test(id)) throw new Error("invalid_run_id");
  return id;
}

function assertConversationId(value) {
  const id = String(value || "").trim();
  if (
    !/^(?:[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}|main-continuity-compaction-[a-f0-9]{24})$/i.test(
      id,
    )
  ) {
    throw new Error("invalid_conversation_id");
  }
  return id;
}

function deriveCompactorIds(domainEpochKey) {
  const key = String(domainEpochKey || "")
    .trim()
    .toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(key)) throw new Error("invalid_domain_epoch_key");
  return {
    conversationId: `main-continuity-compaction-${key.slice(0, 24)}`,
    agentId: `main-continuity-compactor-${key.slice(0, 24)}`,
  };
}

function cloneMainAgentForCapacityQa(
  mainAgent,
  { fixtureObjectId, fixtureAgentId, ownerId, now },
) {
  const sourceAgentId = String(mainAgent?.id || "").trim();
  if (!sourceAgentId) throw new Error("configured_main_agent_id_missing");
  const remapAgentId = (value) => {
    if (Array.isArray(value)) return value.map(remapAgentId);
    return value === sourceAgentId ? fixtureAgentId : value;
  };
  return {
    ...mainAgent,
    _id: fixtureObjectId,
    id: fixtureAgentId,
    author: ownerId,
    name: "Main capacity overlap QA",
    description: "Disposable local Main-continuity capacity QA Agent",
    instructions: "Follow the user request exactly. Return no extra text.",
    background_cortices: [],
    agent_ids: Array.isArray(mainAgent.agent_ids)
      ? mainAgent.agent_ids.map(remapAgentId)
      : mainAgent.agent_ids,
    edges: Array.isArray(mainAgent.edges)
      ? mainAgent.edges.map((edge) => ({
          ...edge,
          from: remapAgentId(edge?.from),
          to: remapAgentId(edge?.to),
        }))
      : mainAgent.edges,
    createdAt: now,
    updatedAt: now,
  };
}

function normalizeIdempotencyBase(value) {
  const full = String(value || "").trim();
  const graphIndex = full.indexOf(":graph:");
  const base = graphIndex >= 0 ? full.slice(0, graphIndex) : full;
  const parts = base.split(":");
  if (
    ![2, 3].includes(parts.length) ||
    !new Set(["main", "main-fallback"]).has(parts[0]) ||
    !parts.slice(1).every((part) => /^[A-Za-z0-9_-]{1,180}$/.test(part))
  ) {
    throw new Error("invalid_provider_idempotency_key");
  }
  if (
    graphIndex >= 0 &&
    !/^[A-Za-z0-9_.:-]{1,320}$/.test(full.slice(graphIndex + 7))
  ) {
    throw new Error("invalid_provider_graph_suffix");
  }
  return base;
}

function sqlLiteral(value) {
  return `'${String(value || "").replaceAll("'", "''")}'`;
}

function sqliteRows(databasePath, query) {
  const raw = execFileSync("sqlite3", ["-json", databasePath, query], {
    encoding: "utf8",
    timeout: 10000,
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
  return raw ? JSON.parse(raw) : [];
}

async function waitFor(fn, message, timeoutMs = 300000, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let latest;
  while (Date.now() < deadline) {
    latest = await fn();
    if (latest) return latest;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(message);
}

function visibleText(message) {
  const parts = [
    String(message?.text || ""),
    ...(Array.isArray(message?.content)
      ? message.content
          .filter((part) => part?.type === "text")
          .map((part) =>
            typeof part.text === "string" ? part.text : part.text?.value || "",
          )
      : []),
  ]
    .map((value) => value.trim())
    .filter(Boolean);
  return [...new Set(parts)].join("\n");
}

function dateMs(value) {
  const parsed = Date.parse(
    value instanceof Date ? value.toISOString() : String(value || ""),
  );
  return Number.isFinite(parsed) ? parsed : NaN;
}

function sourceFingerprint(sourceFiles = CAPACITY_SOURCE_FILES) {
  const manifest = sourceFiles.map((relativePath) => {
    const absolutePath = path.join(REPO_ROOT, relativePath);
    const stat = fs.statSync(absolutePath);
    return {
      relativePath,
      size: stat.size,
      mtimeMs: stat.mtimeMs,
      sha256: crypto
        .createHash("sha256")
        .update(fs.readFileSync(absolutePath))
        .digest("hex"),
    };
  });
  return { manifest, sha256: hash(JSON.stringify(manifest), 24) };
}

function apiProcessSnapshot({ apiBase, apiLog }) {
  const port = new URL(apiBase).port || "80";
  const rawPids = execFileSync(
    "/usr/sbin/lsof",
    ["-nP", "-t", `-iTCP:${port}`, "-sTCP:LISTEN"],
    { encoding: "utf8", timeout: 5000 },
  )
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const pids = [...new Set(rawPids)].sort();
  if (pids.length !== 1 || !/^\d+$/.test(pids[0])) {
    throw new Error("api_listener_identity_ambiguous");
  }
  if (!fs.existsSync(apiLog)) throw new Error("api_log_missing");
  const processIdentity = execFileSync(
    "/bin/ps",
    ["-p", pids[0], "-o", "lstart=", "-o", "command="],
    { encoding: "utf8", timeout: 5000 },
  ).trim();
  const cwdLine = execFileSync(
    "/usr/sbin/lsof",
    ["-a", "-p", pids[0], "-d", "cwd", "-Fn"],
    { encoding: "utf8", timeout: 5000 },
  )
    .split(/\r?\n/)
    .find((line) => line.startsWith("n"));
  const cwd = cwdLine ? fs.realpathSync(cwdLine.slice(1)) : "";
  if (!cwd || cwd !== fs.realpathSync(LIBRECHAT_ROOT)) {
    throw new Error("api_listener_not_running_candidate_checkout");
  }
  if (!fs.existsSync(CANDIDATE_IDENTITY)) {
    throw new Error("candidate_identity_receipt_missing");
  }
  const identityBytes = fs.readFileSync(CANDIDATE_IDENTITY);
  const logStat = fs.statSync(apiLog);
  return {
    pid: pids[0],
    cwd,
    processIdentity,
    processHash: hash(`${pids[0]}\0${processIdentity}`, 24),
    log: {
      path: apiLog,
      dev: logStat.dev,
      ino: logStat.ino,
      offset: logStat.size,
    },
    source: sourceFingerprint(),
    candidateIdentity: {
      sha256: crypto.createHash("sha256").update(identityBytes).digest("hex"),
    },
  };
}

function logDelta(before, after) {
  if (
    before.log.dev !== after.log.dev ||
    before.log.ino !== after.log.ino ||
    after.log.offset < before.log.offset
  ) {
    return { rotated: true, text: "" };
  }
  const length = after.log.offset - before.log.offset;
  if (length <= 0) return { rotated: false, text: "" };
  const descriptor = fs.openSync(after.log.path, "r");
  try {
    const buffer = Buffer.alloc(Math.min(length, 4 * 1024 * 1024));
    const bytesRead = fs.readSync(
      descriptor,
      buffer,
      0,
      buffer.length,
      before.log.offset,
    );
    return {
      rotated: false,
      text: buffer.subarray(0, bytesRead).toString("utf8"),
    };
  } finally {
    fs.closeSync(descriptor);
  }
}

function hotReloadSignals(text) {
  const patterns = [
    /\[nodemon\]\s+restarting\b/i,
    /restarting due to changes/i,
    /app crashed - waiting for file changes/i,
    /\[nodemon\]\s+starting\s+/i,
  ];
  return patterns
    .filter((pattern) => pattern.test(String(text || "")))
    .map(String);
}

function assessRuntimeStability(
  before,
  after,
  delta = logDelta(before, after),
) {
  const signals = hotReloadSignals(delta.text);
  return {
    processStable:
      before.pid === after.pid &&
      before.processIdentity === after.processIdentity &&
      before.cwd === after.cwd,
    sourceStable: before.source.sha256 === after.source.sha256,
    candidateIdentityStable:
      before.candidateIdentity.sha256 === after.candidateIdentity.sha256,
    logRotated: delta.rotated,
    hotReloadDetected: delta.rotated || signals.length > 0,
    hotReloadSignalCount: signals.length,
  };
}

function activeCompactorRows({
  databasePath,
  ownerId,
  conversationId,
  agentId,
  startedAt,
}) {
  assertOwnerId(ownerId);
  assertConversationId(conversationId);
  if (!/^main-continuity-compactor-[a-f0-9]{24}$/.test(agentId)) {
    throw new Error("invalid_compactor_agent_id");
  }
  return sqliteRows(
    databasePath,
    `SELECT
       s.session_id, s.owner_id, s.conversation_id, s.agent_id,
       p.request_id, p.idempotency_key, p.state AS request_state,
       p.run_id, p.fallback_from_run_id, p.created_at AS request_created_at,
       json_extract(p.replay_decision_json, '$.provider_session_mode') AS provider_session_mode,
       r.state AS run_state, r.admitted_at AS run_admitted_at,
       l.lease_id, l.status AS lease_status, l.acquired_at, l.released_at
     FROM provider_sessions s
     JOIN provider_requests p ON p.session_id=s.session_id
     JOIN runs r ON r.run_id=p.run_id
     JOIN host_run_leases l ON l.run_id=r.run_id
     WHERE s.tenant_id='local'
       AND s.owner_id=${sqlLiteral(ownerId)}
       AND s.conversation_id=${sqlLiteral(conversationId)}
       AND s.agent_id=${sqlLiteral(agentId)}
       AND julianday(p.created_at)>=julianday(${sqlLiteral(startedAt.toISOString())})
       AND l.status='active'
     ORDER BY p.created_at DESC;`,
  );
}

function selectExactActiveCompactor(rows, expected) {
  const exact = rows.filter(
    (row) =>
      row.owner_id === expected.ownerId &&
      row.conversation_id === expected.conversationId &&
      row.agent_id === expected.agentId &&
      row.provider_session_mode === "stateless" &&
      row.lease_status === "active",
  );
  if (exact.length !== 1)
    throw new Error("exact_active_stateless_compactor_not_unique");
  assertRunId(exact[0].run_id);
  normalizeIdempotencyBase(exact[0].idempotency_key);
  return exact[0];
}

function compactorRequestRows({
  databasePath,
  ownerId,
  conversationId,
  agentId,
  startedAt,
}) {
  return sqliteRows(
    databasePath,
    `SELECT p.*
     FROM provider_requests p
     JOIN provider_sessions s ON s.session_id=p.session_id
     WHERE s.tenant_id='local'
       AND s.owner_id=${sqlLiteral(assertOwnerId(ownerId))}
       AND s.conversation_id=${sqlLiteral(assertConversationId(conversationId))}
       AND s.agent_id=${sqlLiteral(agentId)}
       AND julianday(p.created_at)>=julianday(${sqlLiteral(startedAt.toISOString())})
     ORDER BY p.created_at ASC;`,
  );
}

function collectFamilyEvidence({
  databasePath,
  ownerId,
  baseIdempotencyKey,
  cancellationStartedAt,
}) {
  assertOwnerId(ownerId);
  const base = normalizeIdempotencyBase(baseIdempotencyKey);
  const requests = sqliteRows(
    databasePath,
    `SELECT request_id, state, run_id, fallback_from_run_id, created_at, updated_at
     FROM provider_requests
     WHERE tenant_id='local'
       AND owner_id=${sqlLiteral(ownerId)}
       AND (
         idempotency_key=${sqlLiteral(base)}
         OR substr(idempotency_key, 1, length(${sqlLiteral(base)}) + 7)=
            ${sqlLiteral(`${base}:graph:`)}
       )
     ORDER BY created_at ASC;`,
  );
  const requestIds = requests.map((row) => row.request_id);
  const activity =
    requestIds.length === 0
      ? []
      : sqliteRows(
          databasePath,
          `SELECT request_id, event_type, count(*) AS count
           FROM provider_activity
           WHERE request_id IN (${requestIds.map(sqlLiteral).join(",")})
           GROUP BY request_id, event_type;`,
        );
  const runIds = [];
  for (const request of requests) {
    const current = String(request.run_id || "").trim();
    const fallback = String(request.fallback_from_run_id || "")
      .trim()
      .replace(/^context_recovery:/, "");
    for (const runId of [current, fallback]) {
      if (!runId || runIds.includes(runId)) continue;
      runIds.push(assertRunId(runId));
    }
  }
  const generations =
    runIds.length === 0
      ? []
      : sqliteRows(
          databasePath,
          `SELECT
             r.run_id, r.state AS run_state, r.admitted_at AS run_admitted_at,
             r.ended_at AS run_ended_at, l.lease_id, l.status AS lease_status,
             l.acquired_at, l.released_at, l.release_reason
           FROM runs r
           LEFT JOIN host_run_leases l ON l.run_id=r.run_id
           WHERE r.run_id IN (${runIds.map(sqlLiteral).join(",")})
           ORDER BY r.queued_at ASC;`,
        );
  const cancellationTombstones = cancellationStartedAt
    ? sqliteRows(
        databasePath,
        `SELECT tenant_id, owner_id, base_idempotency_key, created_at, expires_at
         FROM provider_stop_tombstones
         WHERE julianday(created_at)>=julianday(${sqlLiteral(
           cancellationStartedAt.toISOString(),
         )})
         ORDER BY created_at ASC, tenant_id ASC, owner_id ASC, base_idempotency_key ASC;`,
      )
    : [];
  return {
    base,
    requests,
    activity,
    generations,
    cancellationTombstones,
    cancellationPostMatches:
      cancellationTombstones.length === 1 &&
      cancellationTombstones[0].tenant_id === "local" &&
      cancellationTombstones[0].owner_id === ownerId &&
      cancellationTombstones[0].base_idempotency_key === base,
    cancelEventCount: activity
      .filter((row) => row.event_type === "cancelled")
      .reduce((sum, row) => sum + Number(row.count || 0), 0),
  };
}

function cleanupQaCancellationTombstones({
  databasePath,
  ownerId,
  baseIdempotencyKey,
  startedAt,
}) {
  const owner = assertOwnerId(ownerId);
  const base = normalizeIdempotencyBase(baseIdempotencyKey);
  const scope = `tenant_id='local' AND owner_id=${sqlLiteral(owner)}
    AND base_idempotency_key=${sqlLiteral(base)}
    AND julianday(created_at)>=julianday(${sqlLiteral(startedAt.toISOString())})`;
  execFileSync(
    "sqlite3",
    [databasePath, `BEGIN IMMEDIATE;
      DELETE FROM provider_stop_tombstones WHERE ${scope};
      COMMIT;`],
    { stdio: ["ignore", "pipe", "pipe"], timeout: 10000 },
  );
  return sqliteRows(databasePath,
    `SELECT count(*) AS count FROM provider_stop_tombstones WHERE ${scope};`,
  )[0]?.count === 0;
}

function cleanupQaProviderMainContexts({ databasePath, ownerId, agentIds }) {
  const owner = assertOwnerId(ownerId);
  const exactAgentIds = [
    ...new Set(agentIds.map((value) => String(value || "").trim())),
  ];
  if (
    exactAgentIds.length === 0 ||
    !exactAgentIds.every(
      (value) =>
        /^agent_qa_main_capacity_[a-f0-9]{12}$/.test(value) ||
        /^main-continuity-compactor-[a-f0-9]{24}$/.test(value),
    )
  ) {
    throw new Error("unsafe_qa_provider_context_identity");
  }
  const scope = `tenant_id='local' AND owner_id=${sqlLiteral(
    owner,
  )} AND agent_id IN (${exactAgentIds.map(sqlLiteral).join(",")})`;
  execFileSync(
    "sqlite3",
    [
      databasePath,
      `BEGIN IMMEDIATE;
       DELETE FROM provider_main_contexts WHERE ${scope};
       COMMIT;`,
    ],
    { stdio: ["ignore", "pipe", "pipe"], timeout: 10000 },
  );
  return (
    sqliteRows(
      databasePath,
      `SELECT count(*) AS count FROM provider_main_contexts WHERE ${scope};`,
    )[0]?.count === 0
  );
}

function interactiveRequestRows({
  databasePath,
  ownerId,
  conversationId,
  agentId,
  startedAt,
}) {
  return sqliteRows(
    databasePath,
    `SELECT
       p.request_id, p.state AS request_state, p.run_id,
       r.state AS run_state, r.admitted_at AS run_admitted_at, r.ended_at AS run_ended_at,
       l.lease_id, l.status AS lease_status, l.released_at AS lease_released_at
     FROM provider_requests p
     JOIN provider_sessions s ON s.session_id=p.session_id
     JOIN runs r ON r.run_id=p.run_id
     LEFT JOIN host_run_leases l ON l.run_id=r.run_id
     WHERE s.tenant_id='local'
       AND s.owner_id=${sqlLiteral(assertOwnerId(ownerId))}
       AND s.conversation_id=${sqlLiteral(assertConversationId(conversationId))}
       AND s.agent_id=${sqlLiteral(assertSyntheticAgentId(agentId))}
       AND julianday(p.created_at)>=julianday(${sqlLiteral(startedAt.toISOString())})
     ORDER BY p.created_at DESC;`,
  );
}

function assessCapacityProof(input) {
  const family = input.family || {
    requests: [],
    generations: [],
    cancelEventCount: 0,
  };
  const interactive = input.interactive || {};
  const initialGeneration = family.generations.find(
    (generation) => generation.lease_id === input.initialLeaseId,
  );
  const interactiveAdmittedAt = dateMs(interactive.run_admitted_at);
  const manualUserCreatedAt = dateMs(input.manualUserCreatedAt);
  const checks = {
    activeLeaseBelongsToFamily: Boolean(initialGeneration),
    manualTurnOverlappedLease:
      Boolean(initialGeneration) &&
      Number.isFinite(manualUserCreatedAt) &&
      Number.isFinite(dateMs(initialGeneration.released_at)) &&
      manualUserCreatedAt <= dateMs(initialGeneration.released_at),
    compactorFamilyCancelled:
      family.requests.length > 0 &&
      family.requests.every((row) => row.state === "cancelled"),
    exactlyOneCancelledActivity: family.cancelEventCount === 1,
    exactCancellationPostAndOwnerFence: family.cancellationPostMatches === true,
    generationRunsInterrupted:
      family.generations.length > 0 &&
      family.generations.every((row) =>
        ["cancelled", "interrupted"].includes(row.run_state),
      ),
    everyGenerationLeaseReleased:
      family.generations.length > 0 &&
      family.generations.every(
        (row) =>
          Boolean(row.lease_id) &&
          row.lease_status === "released" &&
          Number.isFinite(dateMs(row.released_at)),
      ),
    releasesPrecedeMainAdmission:
      Number.isFinite(interactiveAdmittedAt) &&
      family.generations.length > 0 &&
      family.generations.every(
        (row) =>
          Number.isFinite(dateMs(row.released_at)) &&
          dateMs(row.released_at) <= interactiveAdmittedAt,
      ),
    supportedReplayAcknowledged:
      input.replay?.state === "cancelled" &&
      input.replay?.capacityReleased === true,
    trustedVisibleManualSubmission:
      input.trustedVisibleManualSubmission === true,
    interactiveCompleted:
      interactive.request_state === "completed" &&
      interactive.run_state === "completed",
    interactiveLeaseReleased:
      interactive.lease_status === "released" &&
      Number.isFinite(dateMs(interactive.lease_released_at)),
    exactReplyPersisted: input.replyPersisted === true,
    reloadPreserved: input.reloadPreserved === true,
    replacementCompactorsCancelled: (
      input.replacementCancellations || []
    ).every(
      (row) => row.state === "cancelled" && row.capacityReleased === true,
    ),
    apiProcessStable: input.runtime?.processStable === true,
    sourceStable: input.runtime?.sourceStable === true,
    candidateIdentityStable: input.runtime?.candidateIdentityStable === true,
    noHotReload:
      input.runtime?.hotReloadDetected === false &&
      input.runtime?.logRotated === false,
  };
  const failures = Object.entries(checks)
    .filter(([, passed]) => !passed)
    .map(([name]) => name);
  return { pass: failures.length === 0, checks, failures };
}

async function replayCancel({ env, ownerId, baseIdempotencyKey }) {
  const baseURL = requireLocalHttpUrl(
    String(env.GLASSHIVE_PROVIDER_BASE_URL || ""),
    "glasshive_provider_base_url",
  ).replace(/\/$/, "");
  const apiKey = String(env.GLASSHIVE_PROVIDER_API_KEY || "").trim();
  if (!apiKey) throw new Error("glasshive_provider_api_key_missing");
  const response = await fetch(
    `${baseURL}/requests/by-idempotency/${encodeURIComponent(
      normalizeIdempotencyBase(baseIdempotencyKey),
    )}/cancel`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "X-Viventium-User-Id": assertOwnerId(ownerId),
      },
      signal: AbortSignal.timeout(10000),
    },
  );
  const body = await response.json().catch(() => ({}));
  return {
    statusCode: response.status,
    state: String(body?.state || ""),
    capacityReleased: body?.capacityReleased === true,
    ok: response.ok,
  };
}

async function cancelAllCompactorFamilies({
  env,
  databasePath,
  ownerId,
  conversationId,
  agentId,
  startedAt,
}) {
  const rows = compactorRequestRows({
    databasePath,
    ownerId,
    conversationId,
    agentId,
    startedAt,
  });
  const bases = [
    ...new Set(
      rows.map((row) => normalizeIdempotencyBase(row.idempotency_key)),
    ),
  ];
  const outcomes = [];
  for (const base of bases) {
    outcomes.push({
      base,
      ...(await replayCancel({ env, ownerId, baseIdempotencyKey: base })),
    });
  }
  return outcomes;
}

function publicSummary(result) {
  return {
    pass: result.pass === true,
    fixtureAgentHash: result.fixtureAgentId ? hash(result.fixtureAgentId) : "",
    conversationHash: result.conversationId ? hash(result.conversationId) : "",
    compactorConversationHash: result.compactorConversationId
      ? hash(result.compactorConversationId)
      : "",
    warmupTurnCount: Number(result.warmupTurnCount || 0),
    activeStatelessLeaseObserved: result.activeStatelessLeaseObserved === true,
    manualTurnObserved: result.manualTurnObserved === true,
    trustedVisibleManualSubmission:
      result.trustedVisibleManualSubmission === true,
    exactReplyPersisted: result.exactReplyPersisted === true,
    reloadPreserved: result.reloadPreserved === true,
    familyRequestCount: Number(result.familyRequestCount || 0),
    familyGenerationCount: Number(result.familyGenerationCount || 0),
    replacementFamilyCount: Number(result.replacementFamilyCount || 0),
    capacityProof: result.capacityProof || null,
    cleanupVerified: result.cleanupVerified === true,
    privateEvidenceSaved: result.privateEvidenceSaved === true,
    error: result.error ? helper.safeError(result.error) : "",
  };
}

async function main() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error(
      "local_main_capacity_overlap_qa_forbidden_in_ci_or_production",
    );
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error(
      "local_main_capacity_overlap_qa_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT",
    );
  }
  const args = parseArgs(process.argv.slice(2));
  if (!args.mainAgentId)
    throw new Error("VIVENTIUM_QA_MAIN_AGENT_ID_is_required");
  const env = helper.loadRuntimeEnv();
  const qaEmail = String(env.VIVENTIUM_QA_EMAIL || "")
    .trim()
    .toLowerCase();
  if (!qaEmail && !args.qaUserHash)
    throw new Error("missing_viventium_qa_email");
  if (!env.MONGO_URI) throw new Error("missing_mongo_uri");
  if (!fs.existsSync(args.glassHiveDb))
    throw new Error("glasshive_runtime_database_missing");

  const { MongoClient, ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const { chromium } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
  );
  const mongo = new MongoClient(env.MONGO_URI);
  const fixtureObjectId = new ObjectId();
  const fixtureAgentId = assertSyntheticAgentId(
    `agent_qa_main_capacity_${hash(`${args.stamp}-agent`, 12)}`,
  );
  const nonce = hash(`${args.stamp}-turns`, 10).toUpperCase();
  const warmupExpected = [1, 2, 3, 4].map(
    (index) => `OVERLAP_WARM_${index}_${nonce}`,
  );
  const warmupPrompts = warmupExpected.map(
    (marker) => `Reply exactly ${marker}`,
  );
  const manualMarker = `OVERLAP_MAIN_OK_${nonce}`;
  const manualPrompt = `Reply exactly ${manualMarker}`;
  fs.mkdirSync(args.privateOutputDir, { recursive: true, mode: 0o700 });

  const result = {
    pass: false,
    fixtureAgentId,
    warmupTurnCount: 0,
    activeStatelessLeaseObserved: false,
    manualTurnObserved: false,
    trustedVisibleManualSubmission: false,
    exactReplyPersisted: false,
    reloadPreserved: false,
    familyRequestCount: 0,
    familyGenerationCount: 0,
    replacementFamilyCount: 0,
    cleanupVerified: false,
    privateEvidenceSaved: false,
    error: "",
  };
  const exactEvidence = {
    startedAt: args.startedAt.toISOString(),
    fixtureAgentId,
  };
  let db;
  let qaUser;
  let auth;
  let browser;
  let page;
  let runtimeBefore;
  let conversationId = "";
  let compactorIds = null;
  let initialFamilyBase = "";
  let manualReadyAt = null;
  const conversationIds = [];
  const qaCancellationFamilies = new Set();

  try {
    await mongo.connect();
    db = mongo.db(
      new URL(env.MONGO_URI).pathname.replace(/^\//, "") ||
        "LibreChatViventium",
    );
    const mainAgent = await db
      .collection("agents")
      .findOne({ id: args.mainAgentId });
    if (!mainAgent?._id) throw new Error("configured_main_agent_not_found");
    if (args.qaUserHash) {
      const candidates = await db
        .collection("users")
        .find({ role: { $ne: "ADMIN" } })
        .project({ _id: 1, email: 1, username: 1, provider: 1, role: 1 })
        .toArray();
      qaUser = candidates.find(
        (candidate) => hash(candidate._id) === args.qaUserHash,
      );
    } else {
      qaUser = await db.collection("users").findOne({ email: qaEmail });
    }
    if (!qaUser?._id) throw new Error("configured_qa_user_not_found");
    if (String(qaUser.role || "").toUpperCase() === "ADMIN") {
      throw new Error("configured_qa_user_must_be_non_admin");
    }
    const ownerId = assertOwnerId(qaUser._id);
    exactEvidence.ownerId = ownerId;
    const roles = await db
      .collection("accessroles")
      .find({ accessRoleId: { $in: ["agent_owner", "remoteAgent_owner"] } })
      .toArray();
    const roleById = new Map(roles.map((role) => [role.accessRoleId, role]));
    if (!roleById.get("agent_owner") || !roleById.get("remoteAgent_owner")) {
      throw new Error("main_capacity_overlap_access_roles_missing");
    }

    const now = new Date();
    await db.collection("agents").insertOne(
      cloneMainAgentForCapacityQa(mainAgent, {
        fixtureObjectId,
        fixtureAgentId,
        ownerId: qaUser._id,
        now,
      }),
    );
    await db.collection("aclentries").insertMany(
      [
        ["agent", roleById.get("agent_owner")],
        ["remoteAgent", roleById.get("remoteAgent_owner")],
      ].map(([resourceType, role]) => ({
        principalType: "user",
        principalId: qaUser._id,
        principalModel: "User",
        resourceType,
        resourceId: fixtureObjectId,
        roleId: role._id,
        permBits: role.permBits,
        grantedBy: qaUser._id,
        grantedAt: now,
        createdAt: now,
        updatedAt: now,
        __v: 0,
      })),
    );

    auth = await helper.createQaAuth({ env, db, user: qaUser });
    runtimeBefore = apiProcessSnapshot({
      apiBase: args.apiBase,
      apiLog: args.apiLog,
    });
    exactEvidence.runtimeBefore = runtimeBefore;
    browser = await chromium.launch({ channel: "chrome", headless: false });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 960 },
    });
    await helper.attachAuth({ context, args, auth });
    page = await context.newPage();
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error")
        consoleErrors.push(helper.safeError(message.text()));
    });
    const agentUrl = `${args.clientBase}/c/new?agent_id=${encodeURIComponent(fixtureAgentId)}`;
    await page.goto(agentUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await helper.installAccessToken(page, auth.accessToken);
    await page.goto(agentUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await helper.installAccessToken(page, auth.accessToken);
    const input = page
      .getByLabel("Message input")
      .or(page.getByPlaceholder(/^Message/))
      .last();
    await input.waitFor({ state: "visible", timeout: 60000 });

    for (let index = 0; index < warmupPrompts.length; index += 1) {
      const startedAt = new Date();
      await input.fill(warmupPrompts[index]);
      await page.getByTestId("send-button").last().click({ timeout: 30000 });
      const turn = await helper.waitForTurn({
        db,
        userId: ownerId,
        prompt: warmupPrompts[index],
        startedAt,
        timeoutMs: args.timeoutMs,
        onUserMessage: (message) => {
          if (!conversationId) {
            conversationId = assertConversationId(message.conversationId);
            conversationIds.push(conversationId);
          } else if (message.conversationId !== conversationId) {
            throw new Error("warmup_conversation_changed");
          }
        },
      });
      if (visibleText(turn.assistantMessage) !== warmupExpected[index]) {
        throw new Error(`warmup_${index + 1}_exact_reply_missing`);
      }
      await page
        .getByText(warmupExpected[index], { exact: true })
        .waitFor({ state: "visible", timeout: args.timeoutMs });
      result.warmupTurnCount += 1;
    }
    result.conversationId = conversationId;
    exactEvidence.conversationId = conversationId;

    const continuityState = await waitFor(
      () =>
        db.collection("viventiummaincontinuitystates").findOne({
          ownerId,
          agentId: fixtureAgentId,
          compactionStatus: "running",
        }),
      "running_continuity_compaction_not_observed",
      args.timeoutMs,
    );
    compactorIds = deriveCompactorIds(continuityState.domainEpochKey);
    result.compactorConversationId = compactorIds.conversationId;
    exactEvidence.compactorIds = compactorIds;
    const activeCompactor = await waitFor(
      () => {
        const rows = activeCompactorRows({
          databasePath: args.glassHiveDb,
          ownerId,
          ...compactorIds,
          startedAt: args.startedAt,
        });
        if (rows.length === 0) return null;
        return selectExactActiveCompactor(rows, { ownerId, ...compactorIds });
      },
      "active_stateless_compactor_lease_not_observed",
      args.timeoutMs,
      100,
    );
    result.activeStatelessLeaseObserved = true;
    initialFamilyBase = normalizeIdempotencyBase(
      activeCompactor.idempotency_key,
    );
    qaCancellationFamilies.add(initialFamilyBase);
    exactEvidence.activeCompactor = activeCompactor;
    await page.evaluate((expectedPrompt) => {
      window.__viventiumCapacityManualSubmission = {
        typed: false,
        submitted: false,
      };
      const visibleValue = (target) =>
        String(target?.value ?? target?.textContent ?? "").trim();
      document.addEventListener(
        "input",
        (event) => {
          if (
            event.isTrusted &&
            visibleValue(event.target) === expectedPrompt
          ) {
            window.__viventiumCapacityManualSubmission.typed = true;
          }
        },
        true,
      );
      document.addEventListener(
        "click",
        (event) => {
          const target = event.target;
          if (
            event.isTrusted &&
            window.__viventiumCapacityManualSubmission.typed &&
            target instanceof Element &&
            target.closest('[data-testid="send-button"]')
          ) {
            window.__viventiumCapacityManualSubmission.submitted = true;
          }
        },
        true,
      );
      document.addEventListener(
        "keydown",
        (event) => {
          if (
            event.isTrusted &&
            event.key === "Enter" &&
            !event.shiftKey &&
            window.__viventiumCapacityManualSubmission.typed &&
            visibleValue(event.target) === expectedPrompt
          ) {
            window.__viventiumCapacityManualSubmission.submitted = true;
          }
        },
        true,
      );
    }, manualPrompt);
    await page.bringToFront();
    await page.screenshot({
      path: path.join(args.privateOutputDir, "manual-turn-ready.png"),
      fullPage: true,
    });
    manualReadyAt = new Date();
    process.stdout.write(
      `${JSON.stringify({
        event: "manual_turn_ready",
        prompt: manualPrompt,
        activeStatelessLeaseObserved: true,
      })}\n`,
    );

    const manualTurn = await helper.waitForTurn({
      db,
      userId: ownerId,
      prompt: manualPrompt,
      startedAt: manualReadyAt,
      timeoutMs: args.manualTimeoutMs,
      onUserMessage: (message) => {
        if (message.conversationId !== conversationId) {
          throw new Error("manual_turn_conversation_changed");
        }
        result.manualTurnObserved = true;
      },
    });
    if (visibleText(manualTurn.assistantMessage) !== manualMarker) {
      throw new Error("manual_turn_exact_reply_missing");
    }
    const manualInteraction = await page.evaluate(
      () => window.__viventiumCapacityManualSubmission || {},
    );
    result.trustedVisibleManualSubmission =
      manualInteraction.typed === true && manualInteraction.submitted === true;
    result.exactReplyPersisted = true;
    await page
      .getByText(manualMarker, { exact: true })
      .waitFor({ state: "visible", timeout: args.timeoutMs });

    const interactive = await waitFor(
      () => {
        const rows = interactiveRequestRows({
          databasePath: args.glassHiveDb,
          ownerId,
          conversationId,
          agentId: fixtureAgentId,
          startedAt: manualReadyAt,
        });
        return rows.find(
          (row) =>
            row.request_state === "completed" &&
            row.run_state === "completed" &&
            row.lease_status === "released",
        );
      },
      "interactive_main_completion_not_observed",
      args.timeoutMs,
    );
    const family = await waitFor(
      () => {
        const evidence = collectFamilyEvidence({
          databasePath: args.glassHiveDb,
          ownerId,
          baseIdempotencyKey: initialFamilyBase,
          cancellationStartedAt: manualReadyAt,
        });
        return evidence.requests.length > 0 &&
          evidence.requests.every((row) => row.state === "cancelled") &&
          evidence.generations.length > 0 &&
          evidence.generations.every(
            (row) => row.lease_status === "released",
          ) &&
          evidence.cancellationPostMatches
          ? evidence
          : null;
      },
      "compactor_family_release_not_observed",
      args.timeoutMs,
    );
    const replay = await replayCancel({
      env,
      ownerId,
      baseIdempotencyKey: initialFamilyBase,
    });
    if (!replay.ok)
      throw new Error(`compactor_cancel_replay_http_${replay.statusCode}`);

    const allCancellations = await cancelAllCompactorFamilies({
      env,
      databasePath: args.glassHiveDb,
      ownerId,
      ...compactorIds,
      startedAt: args.startedAt,
    });
    for (const row of allCancellations) qaCancellationFamilies.add(row.base);
    const replacements = allCancellations.filter(
      (row) => row.base !== initialFamilyBase,
    );
    result.replacementFamilyCount = replacements.length;
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page
      .getByText(manualMarker, { exact: true })
      .waitFor({ state: "visible", timeout: args.timeoutMs });
    result.reloadPreserved = true;
    await page.screenshot({
      path: path.join(args.privateOutputDir, "manual-turn-reloaded.png"),
      fullPage: true,
    });

    const runtimeAfter = apiProcessSnapshot({
      apiBase: args.apiBase,
      apiLog: args.apiLog,
    });
    const runtime = assessRuntimeStability(runtimeBefore, runtimeAfter);
    result.familyRequestCount = family.requests.length;
    result.familyGenerationCount = family.generations.length;
    const capacityProof = assessCapacityProof({
      family,
      interactive,
      initialLeaseId: activeCompactor.lease_id,
      manualUserCreatedAt: manualTurn.userMessage.createdAt,
      replay,
      replacementCancellations: replacements,
      trustedVisibleManualSubmission: result.trustedVisibleManualSubmission,
      replyPersisted: result.exactReplyPersisted,
      reloadPreserved: result.reloadPreserved,
      runtime,
    });
    result.capacityProof = capacityProof;
    result.pass = capacityProof.pass && consoleErrors.length === 0;
    exactEvidence.manualTurn = {
      userMessageId: manualTurn.userMessage.messageId,
      assistantMessageId: manualTurn.assistantMessage.messageId,
      createdAt: manualTurn.userMessage.createdAt,
      trustedVisibleManualSubmission: result.trustedVisibleManualSubmission,
    };
    exactEvidence.family = family;
    exactEvidence.interactive = interactive;
    exactEvidence.replay = replay;
    exactEvidence.replacementCancellations = replacements;
    exactEvidence.runtimeAfter = runtimeAfter;
    exactEvidence.runtime = runtime;
    exactEvidence.consoleErrors = consoleErrors;
    exactEvidence.capacityProof = capacityProof;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
    exactEvidence.error = result.error;
  } finally {
    if (db && qaUser && compactorIds) {
      try {
        const finalCancellations = await cancelAllCompactorFamilies({
          env,
          databasePath: args.glassHiveDb,
          ownerId: String(qaUser._id),
          ...compactorIds,
          startedAt: args.startedAt,
        });
        for (const row of finalCancellations) qaCancellationFamilies.add(row.base);
      } catch (error) {
        result.error =
          `${result.error}\npre_cleanup_cancel: ${error?.message || error}`.trim();
        result.pass = false;
      }
    }
    await browser?.close().catch(() => {});
    if (db && qaUser) {
      try {
        const ownerId = String(qaUser._id);
        const ids = [
          ...new Set(conversationIds.filter(Boolean).map(assertConversationId)),
        ];
        if (ids.length > 0) {
          await db.collection("messages").deleteMany({
            user: ownerId,
            conversationId: { $in: ids },
          });
          await db.collection("conversations").deleteMany({
            user: ownerId,
            conversationId: { $in: ids },
          });
        }
        await db.collection("viventiummaincontinuitystates").deleteMany({
          ownerId,
          agentId: fixtureAgentId,
        });
        await db.collection("aclentries").deleteMany({
          resourceId: fixtureObjectId,
          principalId: qaUser._id,
        });
        await db.collection("agents").deleteOne({
          _id: fixtureObjectId,
          id: fixtureAgentId,
          author: qaUser._id,
        });
        if (auth?.sessionId) {
          await db.collection("sessions").deleteOne({ _id: auth.sessionId });
        }
        const glassHiveIds = [
          ...ids,
          ...(compactorIds
            ? [assertConversationId(compactorIds.conversationId)]
            : []),
        ];
        const tombstoneCleanupVerified = [...qaCancellationFamilies].map((base) =>
          cleanupQaCancellationTombstones({
            databasePath: args.glassHiveDb,
            ownerId,
            baseIdempotencyKey: base,
            startedAt: args.startedAt,
          }),
        ).every(Boolean);
        const providerContextCleanupVerified = compactorIds
          ? cleanupQaProviderMainContexts({
              databasePath: args.glassHiveDb,
              ownerId,
              agentIds: [fixtureAgentId, compactorIds.agentId],
            })
          : true;
        const glassHiveClean = helper.cleanupGlassHiveConversations(
          glassHiveIds,
          {
            runtimeRecoveryDir: path.join(
              args.privateOutputDir,
              "glasshive-worker-roots",
            ),
          },
        );
        const residue = await Promise.all([
          db.collection("agents").countDocuments({
            _id: fixtureObjectId,
            id: fixtureAgentId,
          }),
          db
            .collection("aclentries")
            .countDocuments({ resourceId: fixtureObjectId }),
          db.collection("viventiummaincontinuitystates").countDocuments({
            ownerId,
            agentId: fixtureAgentId,
          }),
          ids.length
            ? db.collection("messages").countDocuments({
                user: ownerId,
                conversationId: { $in: ids },
              })
            : 0,
          ids.length
            ? db.collection("conversations").countDocuments({
                user: ownerId,
                conversationId: { $in: ids },
              })
            : 0,
          auth?.sessionId
            ? db.collection("sessions").countDocuments({ _id: auth.sessionId })
            : 0,
        ]);
        result.cleanupVerified =
          tombstoneCleanupVerified &&
          providerContextCleanupVerified &&
          glassHiveClean &&
          residue.every((count) => count === 0);
        exactEvidence.tombstoneCleanupVerified = tombstoneCleanupVerified;
        exactEvidence.providerContextCleanupVerified =
          providerContextCleanupVerified;
        result.pass = result.pass && result.cleanupVerified;
      } catch (error) {
        result.error =
          `${result.error}\ncleanup: ${error?.message || error}`.trim();
        result.pass = false;
      }
    }
    exactEvidence.cleanupVerified = result.cleanupVerified;
    exactEvidence.finishedAt = new Date().toISOString();
    try {
      fs.writeFileSync(
        path.join(args.privateOutputDir, "result.json"),
        `${JSON.stringify(exactEvidence, null, 2)}\n`,
        { encoding: "utf8", mode: 0o600 },
      );
      result.privateEvidenceSaved = true;
    } catch (error) {
      result.error =
        `${result.error}\nevidence: ${error?.message || error}`.trim();
      result.pass = false;
    }
    await mongo.close().catch(() => {});
  }

  process.stdout.write(`${JSON.stringify(publicSummary(result), null, 2)}\n`);
  process.exitCode = result.pass ? 0 : 1;
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${helper.safeError(error?.stack || error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  cleanupQaCancellationTombstones,
  assessCapacityProof,
  assessRuntimeStability,
  assertConversationId,
  cloneMainAgentForCapacityQa,
  assertSyntheticAgentId,
  deriveCompactorIds,
  hotReloadSignals,
  normalizeIdempotencyBase,
  parseArgs,
  publicSummary,
  requireLocalHttpUrl,
  selectExactActiveCompactor,
};
