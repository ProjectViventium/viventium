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
       session_id TEXT NOT NULL REFERENCES provider_sessions(session_id),
       run_id TEXT REFERENCES runs(run_id)
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
     CREATE TABLE run_attempts (run_id TEXT REFERENCES runs(run_id));
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
     INSERT INTO provider_requests VALUES ('request-qa', 'session-qa', 'run-qa');
     INSERT INTO provider_activity VALUES ('request-qa');
     INSERT INTO provider_session_visible_admissions VALUES ('session-qa');
     INSERT INTO callback_trace_events VALUES ('run-qa');
     INSERT INTO capacity_attempts VALUES ('run-qa');
     INSERT INTO run_attempts VALUES ('run-qa');
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

  const tables = [
    "projects",
    "workers",
    "provider_sessions",
    "runs",
    "provider_requests",
    "provider_activity",
    "provider_session_visible_admissions",
    "callback_trace_events",
    "capacity_attempts",
    "run_attempts",
    "terminal_callback_reconciliations",
    "work_trace_events",
  ];
  for (const table of tables) {
    const count = sqlite(
      databasePath,
      `SELECT count(*) AS count FROM ${table}`,
      {
        json: true,
      },
    )[0].count;
    assert.equal(count, 0, `${table} must not retain synthetic QA rows`);
  }
  assert.equal(fs.existsSync(workerRoot), false);
  assert.equal(fs.readdirSync(recoveryDirectory).length, 1);
});
