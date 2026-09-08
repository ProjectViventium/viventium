"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const qa = require("./run-live-main-capacity-overlap-qa.cjs");

const domainEpochKey = "a".repeat(64);
const compactor = qa.deriveCompactorIds(domainEpochKey);

function passingProof(overrides = {}) {
  return {
    family: {
      requests: [{ state: "cancelled" }],
      cancelEventCount: 1,
      cancellationPostMatches: true,
      generations: [
        {
          run_state: "interrupted",
          lease_id: "lease-initial",
          lease_status: "released",
          released_at: "2026-09-01T12:00:02.000Z",
        },
        {
          run_state: "cancelled",
          lease_id: "lease-fallback",
          lease_status: "released",
          released_at: "2026-09-01T12:00:03.000Z",
        },
      ],
    },
    interactive: {
      request_state: "completed",
      run_state: "completed",
      run_admitted_at: "2026-09-01T12:00:04.000Z",
      lease_status: "released",
      lease_released_at: "2026-09-01T12:00:05.000Z",
    },
    initialLeaseId: "lease-initial",
    manualUserCreatedAt: "2026-09-01T12:00:01.000Z",
    replay: { state: "cancelled", capacityReleased: true },
    replacementCancellations: [{ state: "cancelled", capacityReleased: true }],
    trustedVisibleManualSubmission: true,
    replyPersisted: true,
    reloadPreserved: true,
    runtime: {
      processStable: true,
      sourceStable: true,
      candidateIdentityStable: true,
      logRotated: false,
      hotReloadDetected: false,
    },
    ...overrides,
  };
}

test("derives only the canonical stateless compactor identities", () => {
  assert.deepEqual(compactor, {
    conversationId: `main-continuity-compaction-${"a".repeat(24)}`,
    agentId: `main-continuity-compactor-${"a".repeat(24)}`,
  });
  assert.throws(
    () => qa.deriveCompactorIds("a".repeat(63)),
    /invalid_domain_epoch_key/,
  );
  assert.doesNotThrow(() => qa.assertConversationId(compactor.conversationId));
  assert.throws(
    () =>
      qa.assertConversationId(`main-continuity-compaction-${"a".repeat(25)}`),
    /invalid_conversation_id/,
  );
});

test("clones Main with the fixture identity across primary-final graph edges", () => {
  const source = {
    _id: "source-object-id",
    id: "agent_main",
    author: "source-owner",
    name: "Main",
    instructions: "Original instructions",
    background_cortices: ["cortex-a"],
    agent_ids: ["agent_main", "agent-a"],
    edges: [
      { from: "agent_main", to: "agent-a", edgeType: "handoff" },
      { from: "agent-a", to: "agent_main", edgeType: "handoff" },
      { from: "agent-a", to: ["agent_main", "agent-b"], edgeType: "handoff" },
    ],
  };
  const now = new Date("2026-09-01T12:00:00.000Z");

  const clone = qa.cloneMainAgentForCapacityQa(source, {
    fixtureObjectId: "fixture-object-id",
    fixtureAgentId: "agent_fixture",
    ownerId: "fixture-owner",
    now,
  });

  assert.equal(clone._id, "fixture-object-id");
  assert.equal(clone.id, "agent_fixture");
  assert.equal(clone.author, "fixture-owner");
  assert.deepEqual(clone.agent_ids, ["agent_fixture", "agent-a"]);
  assert.deepEqual(clone.edges, [
    { from: "agent_fixture", to: "agent-a", edgeType: "handoff" },
    { from: "agent-a", to: "agent_fixture", edgeType: "handoff" },
    { from: "agent-a", to: ["agent_fixture", "agent-b"], edgeType: "handoff" },
  ]);
  assert.equal(clone.instructions, "Follow the user request exactly. Return no extra text.");
  assert.deepEqual(clone.background_cortices, []);
  assert.equal(clone.createdAt, now);
  assert.equal(clone.updatedAt, now);
  assert.equal(source.id, "agent_main");
  assert.equal(source.edges[0].from, "agent_main");
});

test("accepts exact provider families and rejects unsafe cancellation keys", () => {
  assert.equal(
    qa.normalizeIdempotencyBase(
      "main:main-continuity-compactor-abc:message_1:graph:agent_2",
    ),
    "main:main-continuity-compactor-abc:message_1",
  );
  assert.equal(qa.normalizeIdempotencyBase("main:message_1"), "main:message_1");
  for (const invalid of [
    "",
    "main:../../bad",
    "other:message_1",
    "main:a:b:c",
    "main:a:graph:",
  ]) {
    assert.throws(() => qa.normalizeIdempotencyBase(invalid));
  }
});

test("allows only local HTTP surfaces", () => {
  assert.equal(
    qa.requireLocalHttpUrl("http://127.0.0.1:3180", "api"),
    "http://127.0.0.1:3180/",
  );
  assert.equal(
    qa.requireLocalHttpUrl("http://localhost:3190", "client"),
    "http://localhost:3190/",
  );
  assert.throws(
    () => qa.requireLocalHttpUrl("https://127.0.0.1:3180", "api"),
    /must_be_local_http/,
  );
  assert.throws(
    () => qa.requireLocalHttpUrl("http://example.test:3180", "api"),
    /must_be_local_http/,
  );
  assert.throws(
    () => qa.requireLocalHttpUrl("http://name:pass@localhost:3180", "api"),
    /must_be_local_http/,
  );
});

test("selects one exact active stateless compactor and rejects ambiguity", () => {
  const expected = {
    ownerId: "b".repeat(24),
    ...compactor,
  };
  const exact = {
    owner_id: expected.ownerId,
    conversation_id: expected.conversationId,
    agent_id: expected.agentId,
    provider_session_mode: "stateless",
    lease_status: "active",
    run_id: "run_" + "1234567890", // Synthetic fixed-width GlassHive identity.
    idempotency_key: "main:message_1",
  };
  assert.equal(qa.selectExactActiveCompactor([exact], expected), exact);
  assert.throws(
    () => qa.selectExactActiveCompactor([exact, { ...exact }], expected),
    /not_unique/,
  );
  assert.throws(
    () =>
      qa.selectExactActiveCompactor(
        [{ ...exact, provider_session_mode: "persistent" }],
        expected,
      ),
    /not_unique/,
  );
});

test("passes only when all generations release before Main admission", () => {
  const result = qa.assessCapacityProof(passingProof());
  assert.equal(result.pass, true);
  assert.deepEqual(result.failures, []);
});

test("fails a retained fallback lease and a late release", () => {
  const activeFallback = passingProof();
  activeFallback.family.generations[1] = {
    ...activeFallback.family.generations[1],
    run_state: "running",
    lease_status: "active",
    released_at: null,
  };
  const activeResult = qa.assessCapacityProof(activeFallback);
  assert.equal(activeResult.pass, false);
  assert.ok(activeResult.failures.includes("generationRunsInterrupted"));
  assert.ok(activeResult.failures.includes("everyGenerationLeaseReleased"));
  assert.ok(activeResult.failures.includes("releasesPrecedeMainAdmission"));

  const late = passingProof();
  late.family.generations[1].released_at = "2026-09-01T12:00:04.001Z";
  const lateResult = qa.assessCapacityProof(late);
  assert.equal(lateResult.pass, false);
  assert.ok(lateResult.failures.includes("releasesPrecedeMainAdmission"));
});

test("fails when the user turn did not overlap or cancellation evidence is duplicated", () => {
  const proof = passingProof({
    manualUserCreatedAt: "2026-09-01T12:00:02.001Z",
  });
  proof.family.cancelEventCount = 2;
  proof.family.cancellationPostMatches = false;
  const result = qa.assessCapacityProof(proof);
  assert.equal(result.pass, false);
  assert.ok(result.failures.includes("manualTurnOverlappedLease"));
  assert.ok(result.failures.includes("exactlyOneCancelledActivity"));
  assert.ok(result.failures.includes("exactCancellationPostAndOwnerFence"));
});

test("fails replay, persistence, cleanup-adjacent runtime, and replacement gates independently", () => {
  const proof = passingProof({
    replay: { state: "cancelled", capacityReleased: false },
    replacementCancellations: [{ state: "cancelled", capacityReleased: false }],
    trustedVisibleManualSubmission: false,
    replyPersisted: false,
    reloadPreserved: false,
    runtime: {
      processStable: false,
      sourceStable: false,
      candidateIdentityStable: false,
      logRotated: true,
      hotReloadDetected: true,
    },
  });
  const result = qa.assessCapacityProof(proof);
  assert.equal(result.pass, false);
  for (const expected of [
    "supportedReplayAcknowledged",
    "replacementCompactorsCancelled",
    "trustedVisibleManualSubmission",
    "exactReplyPersisted",
    "reloadPreserved",
    "apiProcessStable",
    "sourceStable",
    "candidateIdentityStable",
    "noHotReload",
  ]) {
    assert.ok(result.failures.includes(expected));
  }
});

test("detects hot-reload log signals and requires stable process/source identity", () => {
  assert.equal(qa.hotReloadSignals("ordinary request completed").length, 0);
  assert.equal(
    qa.hotReloadSignals("[nodemon] restarting due to changes...").length >= 1,
    true,
  );
  const before = {
    pid: "100",
    processIdentity: "identity-a",
    source: { sha256: "source-a" },
    candidateIdentity: { sha256: "candidate-a" },
    cwd: "/candidate/LibreChat",
    log: { dev: 1, ino: 2, offset: 10, path: "/unused" },
  };
  const stable = qa.assessRuntimeStability(
    before,
    { ...before },
    { rotated: false, text: "" },
  );
  assert.deepEqual(stable, {
    processStable: true,
    sourceStable: true,
    candidateIdentityStable: true,
    logRotated: false,
    hotReloadDetected: false,
    hotReloadSignalCount: 0,
  });
  const changed = qa.assessRuntimeStability(
    before,
    {
      ...before,
      pid: "101",
      source: { sha256: "source-b" },
      candidateIdentity: { sha256: "candidate-b" },
      cwd: "/other/LibreChat",
    },
    { rotated: false, text: "[nodemon] starting `node api/server/index.js`" },
  );
  assert.equal(changed.processStable, false);
  assert.equal(changed.sourceStable, false);
  assert.equal(changed.candidateIdentityStable, false);
  assert.equal(changed.hotReloadDetected, true);
});

test("public summary excludes exact IDs, paths, and raw errors", () => {
  const summary = qa.publicSummary({
    pass: false,
    fixtureAgentId: "agent_qa_main_capacity_123456789abc",
    conversationId: "11111111-1111-1111-1111-111111111111",
    compactorConversationId: `main-continuity-compaction-${"a".repeat(24)}`,
    error:
      "/Users/example/private file user@example.test 11111111-1111-1111-1111-111111111111",
  });
  const serialized = JSON.stringify(summary);
  assert.doesNotMatch(serialized, /agent_qa_main_capacity_123456789abc/);
  assert.doesNotMatch(serialized, /11111111-1111-1111-1111-111111111111/);
  assert.doesNotMatch(serialized, /\/Users\/example/);
  assert.doesNotMatch(serialized, /user@example\.test/);
});

test("argument parser rejects unsupported switches and unsafe timeout values", () => {
  const env = {
    VIVENTIUM_QA_API_BASE: "http://127.0.0.1:3180",
    VIVENTIUM_QA_CLIENT_BASE: "http://127.0.0.1:3190",
  };
  const parsed = qa.parseArgs(
    ["--main-agent-id", "agent_main", "--timeout-ms", "5000"],
    env,
    new Date("2026-09-01T00:00:00.000Z"),
  );
  assert.equal(parsed.mainAgentId, "agent_main");
  assert.equal(parsed.timeoutMs, 5000);
  assert.throws(() => qa.parseArgs(["--headless"], env), /unknown_argument/);
  assert.throws(
    () => qa.parseArgs(["--timeout-ms", "0"], env),
    /invalid_timeout_ms/,
  );
});


test("cleanup preserves unrelated owners, families, tenants and older evidence", () => {
  const fs = require("fs");
  const os = require("os");
  const path = require("path");
  const { execFileSync } = require("child_process");
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "capacity-cleanup-test-"));
  const databasePath = path.join(temporary, "fixture.db");
  const owner = "a".repeat(24);
  const otherOwner = "b".repeat(24);
  const runSql = (sql) => execFileSync("sqlite3", ["-json", databasePath, sql], { encoding: "utf8" });
  try {
    runSql(`CREATE TABLE provider_stop_tombstones (
      label TEXT, tenant_id TEXT, owner_id TEXT, base_idempotency_key TEXT, created_at TEXT);
      INSERT INTO provider_stop_tombstones VALUES
      ('target', 'local', '${owner}', 'main:target', '2026-09-01T12:00:01Z'),
      ('same_owner_other_family', 'local', '${owner}', 'main:unrelated', '2026-09-01T12:00:01Z'),
      ('other_owner_same_family', 'local', '${otherOwner}', 'main:target', '2026-09-01T12:00:01Z'),
      ('other_tenant', 'other', '${owner}', 'main:target', '2026-09-01T12:00:01Z'),
      ('older_evidence', 'local', '${owner}', 'main:target', '2026-09-01T11:59:59Z');`);
    const scope = { databasePath, ownerId: owner, baseIdempotencyKey: "main:target",
      startedAt: new Date("2026-09-01T12:00:00Z") };
    assert.equal(qa.cleanupQaCancellationTombstones(scope), true);
    assert.equal(qa.cleanupQaCancellationTombstones(scope), true);
    assert.deepEqual(JSON.parse(runSql("SELECT label FROM provider_stop_tombstones ORDER BY label;"))
      .map((row) => row.label), ["older_evidence", "other_owner_same_family", "other_tenant", "same_owner_other_family"]);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});
