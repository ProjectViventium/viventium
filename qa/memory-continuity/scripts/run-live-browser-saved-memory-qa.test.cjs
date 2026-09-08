"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  cleanupGlassHiveConversations,
  providerNamesMatch,
  safeError,
  waitForTurn,
} = require("./run-live-browser-saved-memory-qa.cjs");

function sqlite(databasePath, sql, { json = false } = {}) {
  const args = json ? ["-json", databasePath, sql] : [databasePath, sql];
  const output = execFileSync("sqlite3", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
  return json && output ? JSON.parse(output) : output;
}

function createCleanupFixture(databasePath, workerRoot) {
  fs.mkdirSync(path.join(workerRoot, "state"), { recursive: true });
  fs.mkdirSync(path.join(workerRoot, "home"), { recursive: true });
  fs.writeFileSync(path.join(workerRoot, "state", "synthetic.json"), "{}", {
    mode: 0o600,
  });
  sqlite(
    databasePath,
    `PRAGMA foreign_keys=ON;
     CREATE TABLE projects (project_id TEXT PRIMARY KEY);
     CREATE TABLE workers (
       worker_id TEXT PRIMARY KEY,
       project_id TEXT NOT NULL REFERENCES projects(project_id),
       state TEXT NOT NULL,
       pid INTEGER,
       state_dir TEXT NOT NULL,
       workspace_dir TEXT NOT NULL,
       workspace_root TEXT NOT NULL
     );
     CREATE TABLE provider_sessions (
       session_id TEXT PRIMARY KEY,
       conversation_id TEXT NOT NULL,
       project_id TEXT NOT NULL REFERENCES projects(project_id),
       worker_id TEXT NOT NULL REFERENCES workers(worker_id)
     );
     CREATE TABLE runs (
       run_id TEXT PRIMARY KEY,
       worker_id TEXT NOT NULL REFERENCES workers(worker_id),
       state TEXT NOT NULL
     );
     CREATE TABLE provider_requests (
       request_id TEXT PRIMARY KEY,
       tenant_id TEXT NOT NULL DEFAULT 'local',
       owner_id TEXT NOT NULL,
       session_id TEXT NOT NULL REFERENCES provider_sessions(session_id),
       run_id TEXT REFERENCES runs(run_id),
       idempotency_key TEXT NOT NULL
     );
     CREATE TABLE provider_activity (
       request_id TEXT NOT NULL REFERENCES provider_requests(request_id)
     );
     CREATE TABLE provider_account_run_fences (run_id TEXT REFERENCES runs(run_id));
     CREATE TABLE capability_grant_revocations (
       worker_id TEXT REFERENCES workers(worker_id),
       run_id TEXT REFERENCES runs(run_id)
     );
     CREATE TABLE host_run_leases (
       worker_id TEXT REFERENCES workers(worker_id),
       run_id TEXT REFERENCES runs(run_id)
     );
     CREATE TABLE lifecycle_operation_effects (worker_id TEXT REFERENCES workers(worker_id));
     CREATE TABLE run_action_uses (
       worker_id TEXT REFERENCES workers(worker_id),
       source_run_id TEXT REFERENCES runs(run_id),
       new_run_id TEXT REFERENCES runs(run_id)
     );
     CREATE TABLE delegations (
       worker_id TEXT REFERENCES workers(worker_id),
       initial_run_id TEXT REFERENCES runs(run_id),
       current_run_id TEXT REFERENCES runs(run_id)
     );
     CREATE TABLE events (worker_id TEXT REFERENCES workers(worker_id));
     CREATE TABLE callback_outbox (worker_id TEXT REFERENCES workers(worker_id));
     CREATE TABLE scheduled_runs (worker_id TEXT REFERENCES workers(worker_id));
     CREATE TABLE recurring_schedule_definitions (worker_id TEXT REFERENCES workers(worker_id));
     CREATE TABLE provider_session_visible_admissions (
       session_id TEXT NOT NULL REFERENCES provider_sessions(session_id) ON DELETE CASCADE
     );
     CREATE TABLE callback_trace_events (run_id TEXT REFERENCES runs(run_id));
     CREATE TABLE capacity_attempts (run_id TEXT REFERENCES runs(run_id));
     CREATE TABLE run_attempts (
       attempt_id TEXT PRIMARY KEY,
       run_id TEXT REFERENCES runs(run_id)
     );
     CREATE TABLE provider_liveness_events (
       event_ref TEXT PRIMARY KEY,
       run_id TEXT NOT NULL REFERENCES runs(run_id),
       attempt_id TEXT NOT NULL REFERENCES run_attempts(attempt_id),
       kind TEXT NOT NULL,
       failure_class TEXT NOT NULL DEFAULT '',
       runtime TEXT NOT NULL,
       model TEXT NOT NULL,
       source_sequence INTEGER NOT NULL,
       source_digest TEXT NOT NULL,
       observed_at TEXT NOT NULL,
       created_at TEXT NOT NULL
     );
     CREATE TABLE provider_stop_tombstones (
       tenant_id TEXT NOT NULL DEFAULT 'local',
       owner_id TEXT NOT NULL,
       base_idempotency_key TEXT NOT NULL,
       created_at TEXT NOT NULL,
       expires_at TEXT NOT NULL,
       PRIMARY KEY (tenant_id, owner_id, base_idempotency_key)
     );
     CREATE TABLE terminal_callback_reconciliations (run_id TEXT REFERENCES runs(run_id));
     CREATE TABLE work_trace_events (run_id TEXT REFERENCES runs(run_id));
     INSERT INTO projects VALUES ('project-qa');
     INSERT INTO workers VALUES (
       'wrk_qa123',
       'project-qa',
       'ready',
       NULL,
       '${workerRoot.replaceAll("'", "''")}/state',
       '${directorySafeWorkspace(workerRoot).replaceAll("'", "''")}',
       '${directorySafeWorkspace(workerRoot).replaceAll("'", "''")}'
     );
     INSERT INTO provider_sessions VALUES (
       'session-qa',
       '11111111-2222-4333-8444-555555555555',
       'project-qa',
       'wrk_qa123'
     );
     INSERT INTO runs VALUES ('run-qa', 'wrk_qa123', 'completed');
     INSERT INTO provider_requests VALUES (
       'request-qa',
       'local',
       'owner-qa',
       'session-qa',
       'run-qa',
       'qa-family:graph:1'
     );
     INSERT INTO provider_activity VALUES ('request-qa');
     INSERT INTO provider_session_visible_admissions VALUES ('session-qa');
     INSERT INTO callback_trace_events VALUES ('run-qa');
     INSERT INTO capacity_attempts VALUES ('run-qa');
     INSERT INTO run_attempts VALUES ('attempt-qa', 'run-qa');
     INSERT INTO provider_liveness_events VALUES (
       'liveness-qa',
       'run-qa',
       'attempt-qa',
       'retry',
       '',
       'codex_cli',
       'synthetic-model',
       1,
       'digest-qa',
       '2026-01-01T00:00:00Z',
       '2026-01-01T00:00:00Z'
     );
     INSERT INTO provider_stop_tombstones VALUES (
       'local',
       'owner-qa',
       'qa-family',
       '2026-01-01T00:00:00Z',
       '2027-01-01T00:00:00Z'
     );
     INSERT INTO terminal_callback_reconciliations VALUES ('run-qa');
     INSERT INTO work_trace_events VALUES ('run-qa');`,
  );
}

function directorySafeWorkspace(workerRoot) {
  return path.join(path.dirname(path.dirname(workerRoot)), "shared-workspace");
}

test("provider comparison accepts canonical enum casing only", () => {
  assert.equal(providerNamesMatch("openAI", "openai"), true);
  assert.equal(providerNamesMatch(" OpenAI ", "openai"), true);
  assert.equal(providerNamesMatch("anthropic", "openai"), false);
  assert.equal(providerNamesMatch("", "openai"), false);
});

test("public-safe errors redact UUID database identifiers", () => {
  const uuid = "11111111-2222-4333-8444-555555555555";
  const output = safeError(`cleanup failed for ${uuid}`);
  assert.doesNotMatch(output, /11111111/);
  assert.match(output, /<id>/);
});

test("turn tracking captures the user conversation before assistant timeout", async () => {
  const syntheticConversationId = "11111111-2222-4333-8444-555555555555";
  const capturedConversationIds = [];
  const messages = {
    async findOne() {
      return {
        conversationId: syntheticConversationId,
        messageId: "user-message-qa",
      };
    },
    find() {
      return {
        sort() {
          return this;
        },
        limit() {
          return this;
        },
        async toArray() {
          return [];
        },
      };
    },
  };

  await assert.rejects(
    waitForTurn({
      db: { collection: () => messages },
      userId: "user-qa",
      prompt: "synthetic prompt",
      startedAt: new Date(0),
      timeoutMs: 5,
      onUserMessage: (message) => {
        capturedConversationIds.push(message.conversationId);
      },
    }),
    /browser_assistant_message_not_persisted/,
  );
  assert.deepEqual(capturedConversationIds, [syntheticConversationId]);
});

test("exact GlassHive cleanup removes current run dependencies", (t) => {
  const directory = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-memory-cleanup-test-"),
  );
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const databasePath = path.join(directory, "runtime_phase1.db");
  const workerRoot = path.join(
    directory,
    "state",
    "runtime",
    "isolated",
    "glasshive",
    "host_codex_cli_runtime",
    "workers",
    "wrk_qa123",
  );
  const recoveryDirectory = path.join(directory, "private-recovery");
  createCleanupFixture(databasePath, workerRoot);
  sqlite(
    databasePath,
    `INSERT INTO projects VALUES ('project-unrelated');
     INSERT INTO workers VALUES (
       'wrk_unrelated',
       'project-unrelated',
       'ready',
       NULL,
       '/unrelated/state',
       '/unrelated/workspace',
       '/unrelated/workspace'
     );
     INSERT INTO runs VALUES ('run-unrelated', 'wrk_unrelated', 'completed');
     INSERT INTO run_attempts VALUES ('attempt-unrelated', 'run-unrelated');
     INSERT INTO provider_liveness_events VALUES (
       'liveness-unrelated',
       'run-unrelated',
       'attempt-unrelated',
       'retry',
       '',
       'codex_cli',
       'synthetic-model',
       1,
       'digest-unrelated',
       '2026-01-01T00:00:00Z',
       '2026-01-01T00:00:00Z'
     );
     INSERT INTO provider_stop_tombstones VALUES (
       'local',
       'owner-unrelated',
       'unrelated-family',
       '2026-01-01T00:00:00Z',
       '2027-01-01T00:00:00Z'
     );
     INSERT INTO provider_stop_tombstones VALUES
       ('local', 'owner-qa', 'unrelated-family', '2026-01-01', '2027-01-01'),
       ('local', 'owner-unrelated', 'qa-family', '2026-01-01', '2027-01-01'),
       ('other-tenant', 'owner-qa', 'qa-family', '2026-01-01', '2027-01-01');`,
  );

  assert.equal(
    cleanupGlassHiveConversations(["11111111-2222-4333-8444-555555555555"], {
      databasePath,
      runtimeRecoveryDir: recoveryDirectory,
      runtimeRoot: path.join(
        directory,
        "state",
        "runtime",
        "isolated",
        "glasshive",
      ),
    }),
    true,
  );

  const targetCounts = sqlite(
    databasePath,
    `SELECT
       (SELECT count(*) FROM projects WHERE project_id = 'project-qa') AS projects,
       (SELECT count(*) FROM workers WHERE worker_id = 'wrk_qa123') AS workers,
       (SELECT count(*) FROM provider_sessions WHERE session_id = 'session-qa') AS sessions,
       (SELECT count(*) FROM runs WHERE run_id = 'run-qa') AS runs,
       (SELECT count(*) FROM provider_requests WHERE request_id = 'request-qa') AS requests,
       (SELECT count(*) FROM provider_activity WHERE request_id = 'request-qa') AS activity,
       (SELECT count(*) FROM provider_session_visible_admissions WHERE session_id = 'session-qa') AS admissions,
       (SELECT count(*) FROM callback_trace_events WHERE run_id = 'run-qa') AS callback_traces,
       (SELECT count(*) FROM capacity_attempts WHERE run_id = 'run-qa') AS capacity_attempts,
       (SELECT count(*) FROM run_attempts WHERE run_id = 'run-qa') AS run_attempts,
       (SELECT count(*) FROM provider_liveness_events WHERE run_id = 'run-qa') AS liveness,
       (SELECT count(*) FROM provider_stop_tombstones
        WHERE tenant_id = 'local' AND owner_id = 'owner-qa'
          AND base_idempotency_key = 'qa-family') AS tombstones,
       (SELECT count(*) FROM terminal_callback_reconciliations WHERE run_id = 'run-qa') AS reconciliations,
       (SELECT count(*) FROM work_trace_events WHERE run_id = 'run-qa') AS work_traces;`,
    { json: true },
  )[0];
  for (const [table, count] of Object.entries(targetCounts)) {
    assert.equal(count, 0, `${table} must not retain synthetic QA rows`);
  }
  assert.deepEqual(
    sqlite(
      databasePath,
      `SELECT
         (SELECT count(*) FROM provider_liveness_events
          WHERE event_ref = 'liveness-unrelated') AS liveness,
         (SELECT count(*) FROM provider_stop_tombstones
          WHERE tenant_id = 'local' AND owner_id = 'owner-unrelated'
            AND base_idempotency_key = 'unrelated-family') AS tombstones;`,
      { json: true },
    )[0],
    { liveness: 1, tombstones: 1 },
  );
  assert.equal(
    sqlite(databasePath, "SELECT count(*) AS count FROM provider_stop_tombstones", { json: true })[0].count,
    4,
    "cleanup preserves another owner, tenant, and same-owner unrelated family",
  );
  assert.equal(fs.existsSync(workerRoot), false);
  assert.equal(fs.readdirSync(recoveryDirectory).length, 1);
});

test("exact GlassHive cleanup accepts only the exact overlap conversation ID shape", (t) => {
  const directory = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-overlap-cleanup-test-"),
  );
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const databasePath = path.join(directory, "runtime_phase1.db");
  const workerRoot = path.join(
    directory,
    "state",
    "runtime",
    "isolated",
    "glasshive",
    "host_codex_cli_runtime",
    "workers",
    "wrk_qa123",
  );
  createCleanupFixture(databasePath, workerRoot);
  const exactId = "main-continuity-compaction-A1b2C3d4E5f60718293aBcDe";
  sqlite(
    databasePath,
    `UPDATE provider_sessions
     SET conversation_id = '${exactId}'
     WHERE session_id = 'session-qa';`,
  );

  assert.equal(
    cleanupGlassHiveConversations([exactId], {
      databasePath,
      runtimeRecoveryDir: path.join(directory, "private-recovery"),
      runtimeRoot: path.join(
        directory,
        "state",
        "runtime",
        "isolated",
        "glasshive",
      ),
    }),
    true,
  );
});

test("exact GlassHive cleanup rejects IDs adjacent to the overlap shape", () => {
  const invalidIds = [
    "main-continuity-compaction-1234567890abcdef1234567",
    "main-continuity-compaction-1234567890abcdef123456789",
    "main-continuity-compaction-1234567890abcdef1234567g",
    "main-continuity-compaction--1234567890abcdef12345678",
    "main-continuity-compaction-1234567890abcdef12345678-extra",
    " main-continuity-compaction-1234567890abcdef12345678",
    "main-continuity-compaction-1234567890abcdef12345678 ",
  ];
  for (const invalidId of invalidIds) {
    assert.throws(
      () => cleanupGlassHiveConversations([invalidId]),
      /glasshive_cleanup_refused_invalid_conversation_id/,
      invalidId,
    );
  }
});

test("exact GlassHive cleanup accepts an idle paused worker with only terminal runs", (t) => {
  const directory = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-memory-paused-cleanup-test-"),
  );
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const databasePath = path.join(directory, "runtime_phase1.db");
  const workerRoot = path.join(
    directory,
    "state",
    "runtime",
    "isolated",
    "glasshive",
    "host_codex_cli_runtime",
    "workers",
    "wrk_qa123",
  );
  const recoveryDirectory = path.join(directory, "private-recovery");
  createCleanupFixture(databasePath, workerRoot);
  sqlite(
    databasePath,
    "UPDATE workers SET state = 'paused', pid = NULL WHERE worker_id = 'wrk_qa123';",
  );

  assert.equal(
    cleanupGlassHiveConversations(["11111111-2222-4333-8444-555555555555"], {
      databasePath,
      runtimeRecoveryDir: recoveryDirectory,
      runtimeRoot: path.join(
        directory,
        "state",
        "runtime",
        "isolated",
        "glasshive",
      ),
    }),
    true,
  );
  assert.equal(
    sqlite(databasePath, "SELECT count(*) AS count FROM workers", {
      json: true,
    })[0].count,
    0,
  );
  assert.equal(fs.existsSync(workerRoot), false);
});

test("exact GlassHive cleanup refuses a paused worker with a nonterminal run", (t) => {
  const directory = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-memory-active-paused-cleanup-test-"),
  );
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const databasePath = path.join(directory, "runtime_phase1.db");
  const workerRoot = path.join(
    directory,
    "state",
    "runtime",
    "isolated",
    "glasshive",
    "host_codex_cli_runtime",
    "workers",
    "wrk_qa123",
  );
  createCleanupFixture(databasePath, workerRoot);
  sqlite(
    databasePath,
    `UPDATE workers SET state = 'paused', pid = NULL WHERE worker_id = 'wrk_qa123';
     UPDATE runs SET state = 'paused' WHERE run_id = 'run-qa';`,
  );

  assert.throws(
    () =>
      cleanupGlassHiveConversations(
        ["11111111-2222-4333-8444-555555555555"],
        {
          databasePath,
          runtimeRecoveryDir: path.join(directory, "private-recovery"),
          runtimeRoot: path.join(
            directory,
            "state",
            "runtime",
            "isolated",
            "glasshive",
          ),
        },
      ),
    /glasshive_cleanup_refused_active_worker/,
  );
  assert.equal(fs.existsSync(workerRoot), true);
  assert.equal(
    sqlite(databasePath, "SELECT count(*) AS count FROM workers", {
      json: true,
    })[0].count,
    1,
  );
});
