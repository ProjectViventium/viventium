#!/usr/bin/env node
"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const {
  analyzePersistedTurn,
  armFirstVisibleMainPaintObserver,
  assertHarnessSafety,
  buildPublicSummary,
  bodyContainsAnswer,
  collectVisibleState,
  correlateFirstVisibleMainPaint,
  buildReopenUiReceipt,
  correlatedVisibleAnswerInDocument,
  createAgentChatPostObserver,
  deleteInsertedAuthSession,
  deleteScheduleThroughMcp,
  deriveConversationPreserved,
  deriveSubmitConversationPreserved,
  didVisibleProgressSettle,
  evaluateAcceptance,
  evaluateExactlyOnceToolExecution,
  evaluateReopenAcceptance,
  expandVisibleDetails,
  findCorrelatedQaUserMessage,
  installAccessToken,
  installReopenChatPostGuard,
  isAgentChatSubmissionPath,
  loadSelectedRuntimeEnv,
  parseArgs,
  prepareExpectedScheduleLifecycle,
  preflightSelectedRuntime,
  readSchedulingState,
  resolveSelectedSchedulingRuntimeBinding,
  finalizeExpectedScheduleLifecycle,
  reopenLineageFingerprint,
  revalidateReopenLineage,
  scrollTerminalMessageViewportInDocument,
  summarizeMessages,
  validateReopenPersistedConversation,
  verifyAgentApiAccess,
  verifySchedulingMcpHealth,
  waitForCorrelatedVisibleAnswer,
  waitForVisibleBackgroundSettlement,
  withQaRequestMetadata,
} = require("./run-one-web-prompt-qa.cjs");

const REPO_ROOT = path.resolve(__dirname, "../../..");

test("agent chat matcher includes the real modular submission path and excludes control routes", () => {
  assert.equal(isAgentChatSubmissionPath("/api/agents/chat/agents"), true);
  assert.equal(isAgentChatSubmissionPath("/api/agents/chat"), true);
  assert.equal(isAgentChatSubmissionPath("/api/agents/chat/abort"), false);
  assert.equal(
    isAgentChatSubmissionPath("/api/agents/chat/status/example"),
    false,
  );
  assert.equal(
    isAgentChatSubmissionPath("/api/agents/chat/stream/example"),
    false,
  );
});

test("agent API access probe uses the signed-in QA bearer token", async () => {
  const sentinelToken = "selected-refresh-token-sentinel";
  const originalFetch = global.fetch;
  global.fetch = async (url, options) => {
    assert.equal(url, "/api/agents/agent_synthetic_main");
    assert.deepEqual(options, {
      headers: { Authorization: `Bearer ${sentinelToken}` },
    });
    return {
      status: 200,
      ok: true,
      json: async () => ({
        id: "agent_synthetic_main",
        name: "Synthetic Main",
      }),
    };
  };
  const page = {
    evaluate: async (callback, payload) => callback(payload),
  };

  try {
    const receipt = await verifyAgentApiAccess(
      page,
      { id: "agent_synthetic_main", name: "Synthetic Main" },
      sentinelToken,
    );
    assert.equal(receipt.pass, true);
    assert.equal(JSON.stringify(receipt).includes(sentinelToken), false);
  } finally {
    global.fetch = originalFetch;
  }
});

test("browser installs and returns the exact refreshed token, with fallback only when refresh fails", async () => {
  async function exercise(refreshResult, fallbackToken, expectedToken) {
    const dispatched = [];
    let call = 0;
    const page = {
      evaluate: async (_callback, value) => {
        call += 1;
        if (call === 1) return refreshResult;
        dispatched.push(value);
        return undefined;
      },
      waitForTimeout: async () => {},
    };
    const selected = await installAccessToken(page, fallbackToken);
    assert.equal(selected, expectedToken);
    assert.deepEqual(dispatched, [expectedToken]);
  }

  await exercise(
    { ok: true, token: "selected-refresh-token" },
    "minted-fallback-token",
    "selected-refresh-token",
  );
  await exercise(
    { ok: false, token: "" },
    "minted-fallback-token",
    "minted-fallback-token",
  );
});

function requiredArgs(
  outputDir,
  runtimeRoot = path.join(os.tmpdir(), "qa-runtime", "runtime"),
) {
  return [
    "--client=http://localhost:3190",
    "--api=http://127.0.0.1:3180",
    "--qa-email=qa@example.com",
    "--agent=agent_synthetic_main",
    "--prompt=Evaluate this synthetic reversible decision.",
    "--case=ANTI-SYNTHETIC",
    `--output=${outputDir}`,
    `--runtime-root=${runtimeRoot}`,
  ];
}

test("parseArgs requires the complete reusable run contract", () => {
  const outputDir = path.join(os.tmpdir(), "viventium-private-qa-parse");
  const parsed = parseArgs(requiredArgs(outputDir));

  assert.equal(parsed.clientBase, "http://localhost:3190");
  assert.equal(parsed.apiBase, "http://127.0.0.1:3180");
  assert.equal(parsed.qaEmail, "qa@example.com");
  assert.equal(parsed.agentId, "agent_synthetic_main");
  assert.equal(parsed.caseId, "ANTI-SYNTHETIC");
  assert.equal(parsed.outputDir, outputDir);
  assert.equal(
    parsed.runtimeRoot,
    path.join(os.tmpdir(), "qa-runtime", "runtime"),
  );
  assert.match(parsed.qaRunId, /^ANTI-SYNTHETIC-[0-9TZ-]+-[a-f0-9]{12}$/);
  assert.notEqual(parsed.qaRunId, parseArgs(requiredArgs(outputDir)).qaRunId);

  assert.throws(
    () =>
      parseArgs(
        requiredArgs(outputDir).filter((arg) => !arg.startsWith("--prompt=")),
      ),
    /missing_required_argument_prompt/,
  );
});

test("parseArgs requires an explicit prompt-correlated nonce for the scheduling effect gate", () => {
  const outputDir = path.join(os.tmpdir(), "viventium-private-qa-tool");
  const nonce = "ANTI012-effect-public-123";
  const args = requiredArgs(outputDir).map((arg) =>
    arg.startsWith("--prompt=")
      ? `--prompt=Create one future synthetic reminder labeled ${nonce}.`
      : arg,
  );
  const parsed = parseArgs([
    ...args,
    "--expect-tool=schedule_create_mcp_scheduling-cortex",
    `--expect-schedule-nonce=${nonce}`,
  ]);

  assert.equal(
    parsed.expectedToolName,
    "schedule_create_mcp_scheduling-cortex",
  );
  assert.equal(parsed.expectedScheduleNonce, nonce);
  assert.throws(
    () =>
      parseArgs([
        ...args,
        "--expect-tool=schedule_create_mcp_scheduling-cortex",
      ]),
    /expect_schedule_nonce_required_for_scheduling_gate/,
  );
  assert.throws(
    () => parseArgs([...requiredArgs(outputDir), "--expect-tool=../unsafe"]),
    /expect_tool_must_be_a_structured_tool_name/,
  );
});

test("exact-tool receipt passes only one successful persisted call in the submitted turn", () => {
  const messages = [
    {
      messageId: "user-turn",
      isCreatedByUser: true,
      content: [{ type: "text", text: "synthetic reminder request" }],
    },
    {
      messageId: "assistant-turn",
      parentMessageId: "user-turn",
      isCreatedByUser: false,
      content: [
        {
          type: "tool_call",
          status: "completed",
          tool_call: {
            name: "schedule_create_mcp_scheduling-cortex",
            output: { success: true, task: { id: "private-task-id" } },
          },
        },
        { type: "text", text: "The synthetic reminder is scheduled." },
      ],
    },
  ];

  assert.deepEqual(
    evaluateExactlyOnceToolExecution({
      messages,
      originatingUserMessageId: "user-turn",
      expectedToolName: "schedule_create_mcp_scheduling-cortex",
    }),
    {
      required: true,
      pass: true,
      callCount: 1,
      successfulCallCount: 1,
      failedCallCount: 0,
    },
  );
});

test("exact-tool receipt accepts one safe broker completion in persisted harness activity", () => {
  const messages = [
    { messageId: "user-turn", isCreatedByUser: true },
    {
      messageId: "assistant-turn",
      parentMessageId: "user-turn",
      isCreatedByUser: false,
      content: [
        {
          type: "harness_activity",
          harness_activity: {
            event: "reasoning-summary",
            summary: [
              "The harness completed a reasoning step.",
              "Connected tool completed: schedule create.",
            ].join("\n"),
          },
        },
        { type: "text", text: "The synthetic reminder is scheduled." },
      ],
    },
  ];

  assert.deepEqual(
    evaluateExactlyOnceToolExecution({
      messages,
      originatingUserMessageId: "user-turn",
      expectedToolName: "schedule_create_mcp_scheduling-cortex",
    }),
    {
      required: true,
      pass: true,
      callCount: 1,
      successfulCallCount: 1,
      failedCallCount: 0,
    },
  );
});

test("exact-tool receipt rejects duplicate and non-terminal broker activity", () => {
  const evaluate = (summary) =>
    evaluateExactlyOnceToolExecution({
      messages: [
        { messageId: "user-turn", isCreatedByUser: true },
        {
          messageId: "assistant-turn",
          parentMessageId: "user-turn",
          isCreatedByUser: false,
          content: [
            {
              type: "harness_activity",
              harness_activity: { event: "reasoning-summary", summary },
            },
          ],
        },
      ],
      originatingUserMessageId: "user-turn",
      expectedToolName: "schedule_create_mcp_scheduling-cortex",
    });

  assert.equal(
    evaluate(
      "Connected tool completed: schedule create.\nConnected tool completed: schedule create.",
    ).pass,
    false,
  );
  assert.equal(
    evaluate("Connected tool invoked: schedule create.").pass,
    false,
  );
  assert.deepEqual(evaluate("Connected tool failed: schedule create."), {
    required: true,
    pass: false,
    callCount: 1,
    successfulCallCount: 0,
    failedCallCount: 1,
  });
  assert.equal(evaluate("The harness used a connected tool.").callCount, 0);
});

test("visible answer matcher tolerates markdown rendering without accepting partial answers", () => {
  const persisted = [
    "## Result",
    "- Alpha item",
    "- Beta item",
    "",
    "| Check | State |",
    "| --- | --- |",
    "| Persistence | Passed |",
    "",
    "See [the evidence](https://example.invalid/a_(b)) for the durable result.",
  ].join("\n");
  const rendered = [
    "Result",
    "• Alpha item",
    "• Beta item",
    "Check State",
    "Persistence Passed",
    "See the evidence for the durable result.",
  ].join("\n");

  assert.equal(bodyContainsAnswer(rendered, persisted), true);
  assert.equal(
    bodyContainsAnswer("Result Alpha item Beta item", persisted),
    false,
  );
  assert.equal(
    bodyContainsAnswer(
      "Result Alpha item Beta item Check State See the evidence for the durable result",
      persisted,
    ),
    false,
  );
  assert.equal(
    bodyContainsAnswer(
      "See the evidence for the durable result Persistence Passed Result Alpha item Beta item Check State",
      persisted,
    ),
    false,
  );
  assert.equal(
    bodyContainsAnswer(
      "Result Alpha item Beta item unrelated words Persistence Passed See the evidence for the durable result",
      persisted,
    ),
    false,
  );

  const longAnswer = Array.from(
    { length: 30 },
    (_, index) => `token${index + 1}`,
  ).join(" ");
  const disjointAnchors = [
    ...Array.from({ length: 10 }, (_, index) => `token${index + 1}`),
    ...Array.from({ length: 10 }, (_, index) => `token${index + 21}`),
  ].join(" ");
  assert.equal(bodyContainsAnswer(disjointAnchors, longAnswer), false);
});

test("visible answer proof is scoped to the correlated assistant message and agent part", async () => {
  const persisted = "Result Alpha item Beta item Persistence Passed";
  const targetMainPart = {
    dataset: { viventiumAgentId: "agent_synthetic_main" },
    textContent: "Result Alpha item",
  };
  const messages = [
    {
      id: "message_unrelated",
      querySelector: () => ({}),
      querySelectorAll: () => [
        {
          dataset: { viventiumAgentId: "agent_synthetic_main" },
          textContent: persisted,
        },
      ],
    },
    {
      id: "message_target",
      querySelector: () => ({}),
      querySelectorAll: () => [
        targetMainPart,
        {
          dataset: { viventiumAgentId: "agent_other" },
          textContent: persisted,
        },
      ],
    },
  ];
  const originalDocument = global.document;
  const originalWindow = global.window;
  global.document = {
    body: { innerText: persisted },
    querySelectorAll: (selector) =>
      selector === ".message-render" ? messages : [],
  };
  global.window = { location: { href: "http://localhost/c/synthetic" } };
  const page = {
    evaluate: async (callback, payload) => callback(payload),
  };

  try {
    const partial = await collectVisibleState(page, [], {
      messageId: "message_target",
      agentId: "agent_synthetic_main",
    });
    assert.equal(partial.answerContainerMatched, true);
    assert.equal(partial.answerContainerText, "Result Alpha item");
    assert.equal(
      bodyContainsAnswer(partial.answerContainerText, persisted),
      false,
    );

    targetMainPart.textContent = persisted;
    const complete = await collectVisibleState(page, [], {
      messageId: "message_target",
      agentId: "agent_synthetic_main",
    });
    assert.equal(
      bodyContainsAnswer(complete.answerContainerText, persisted),
      true,
    );
  } finally {
    global.document = originalDocument;
    global.window = originalWindow;
  }
});

test("visible background settlement waits for streamed progress to leave its active state", async () => {
  let waitCalled = false;
  const page = {
    waitForFunction: async (predicate, argument, options) => {
      assert.equal(typeof predicate, "function");
      assert.equal(argument, undefined);
      assert.deepEqual(options, { timeout: 12_345 });
      waitCalled = true;
    },
  };

  assert.equal(await waitForVisibleBackgroundSettlement(page, 12_345), true);
  assert.equal(waitCalled, true);

  const delayed = {
    waitForFunction: async () => {
      throw new Error("synthetic timeout");
    },
  };
  assert.equal(await waitForVisibleBackgroundSettlement(delayed, 10), false);
  assert.equal(didVisibleProgressSettle(true, true), true);
  assert.equal(didVisibleProgressSettle(false, true), false);
  assert.equal(didVisibleProgressSettle(true, false), false);
});

test("exact-tool receipt rejects duplicate, failed, and foreign-turn calls", () => {
  const expectedToolName = "schedule_create_mcp_scheduling-cortex";
  const toolPart = (status, output) => ({
    type: "tool_call",
    status,
    tool_call: { name: expectedToolName, output },
  });
  const messages = [
    { messageId: "older-user", isCreatedByUser: true },
    {
      messageId: "older-assistant",
      parentMessageId: "older-user",
      isCreatedByUser: false,
      content: [toolPart("completed", { success: true })],
    },
    { messageId: "user-turn", isCreatedByUser: true },
    {
      messageId: "assistant-turn",
      parentMessageId: "user-turn",
      isCreatedByUser: false,
      content: [
        toolPart("completed", { success: true }),
        toolPart("completed", { success: true }),
      ],
    },
  ];

  assert.deepEqual(
    evaluateExactlyOnceToolExecution({
      messages,
      originatingUserMessageId: "user-turn",
      expectedToolName,
    }),
    {
      required: true,
      pass: false,
      callCount: 2,
      successfulCallCount: 2,
      failedCallCount: 0,
    },
  );

  messages[3].content = [toolPart("failed", { success: false })];
  assert.deepEqual(
    evaluateExactlyOnceToolExecution({
      messages,
      originatingUserMessageId: "user-turn",
      expectedToolName,
    }),
    {
      required: true,
      pass: false,
      callCount: 1,
      successfulCallCount: 0,
      failedCallCount: 1,
    },
  );
});

test("exactly-once acceptance names an executable Main scheduling create/delete seam", () => {
  const libreChatRoot = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
  const source = fs.readFileSync(
    path.join(
      libreChatRoot,
      "viventium",
      "source_of_truth",
      "local.viventium-agents.yaml",
    ),
    "utf8",
  );
  const mainAgentBlock = source.slice(
    source.indexOf("\nmainAgent:"),
    source.indexOf("\nbackgroundAgents:"),
  );
  for (const toolName of [
    "schedule_create_mcp_scheduling-cortex",
    "schedule_search_mcp_scheduling-cortex",
    "schedule_delete_mcp_scheduling-cortex",
  ]) {
    assert.equal(mainAgentBlock.includes(`    - ${toolName}`), true);
  }

  const server = fs.readFileSync(
    path.join(
      libreChatRoot,
      "viventium",
      "MCPs",
      "scheduling-cortex",
      "scheduling_cortex",
      "server.py",
    ),
    "utf8",
  );
  assert.match(server, /def schedule_create\(args: CreateScheduleArgs\)/);
  assert.match(server, /def schedule_search\(args: SearchScheduleArgs\)/);
  assert.match(server, /def schedule_delete\(args: DeleteScheduleArgs\)/);
});

test("scheduling effect binding is the exact selected isolated runtime state and loopback MCP", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-binding-"),
  );
  const runtimeRoot = path.join(fixtureRoot, "synthetic-qa", "runtime");
  const stateRoot = path.join(
    fixtureRoot,
    "synthetic-qa",
    "state",
    "runtime",
    "isolated",
  );
  const dbPath = path.join(stateRoot, "scheduling", "schedules.db");
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  fs.mkdirSync(runtimeRoot, { recursive: true });
  fs.writeFileSync(dbPath, "");

  assert.deepEqual(
    resolveSelectedSchedulingRuntimeBinding({
      env: {
        SCHEDULING_MCP_URL: "http://127.0.0.1:18091/mcp",
        VIVENTIUM_SCHEDULING_MCP_PORT: "18091",
      },
      runtimeRoot,
      repoRoot: REPO_ROOT,
    }),
    {
      dbPath: fs.realpathSync(dbPath),
      mcpUrl: "http://127.0.0.1:18091/mcp",
      stateRoot: fs.realpathSync(stateRoot),
      port: 18091,
    },
  );

  assert.throws(
    () =>
      resolveSelectedSchedulingRuntimeBinding({
        env: {
          SCHEDULING_DB_PATH: path.join(fixtureRoot, "shared-schedules.db"),
          SCHEDULING_MCP_URL: "http://127.0.0.1:18091/mcp",
          VIVENTIUM_SCHEDULING_MCP_PORT: "18091",
        },
        runtimeRoot,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_scheduling_db_binding_mismatch/,
  );
});

test("scheduling binding rejects a selected state-root symlink that escapes its dev environment", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-state-escape-"),
  );
  const environmentRoot = path.join(fixtureRoot, "synthetic-qa");
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const foreignStateRoot = path.join(fixtureRoot, "foreign-state");
  const foreignDbPath = path.join(
    foreignStateRoot,
    "runtime",
    "isolated",
    "scheduling",
    "schedules.db",
  );
  fs.mkdirSync(runtimeRoot, { recursive: true });
  fs.mkdirSync(path.dirname(foreignDbPath), { recursive: true });
  fs.writeFileSync(foreignDbPath, "");
  fs.symlinkSync(foreignStateRoot, path.join(environmentRoot, "state"), "dir");

  assert.throws(
    () =>
      resolveSelectedSchedulingRuntimeBinding({
        env: {
          SCHEDULING_MCP_URL: "http://127.0.0.1:18091/mcp",
          VIVENTIUM_SCHEDULING_MCP_PORT: "18091",
        },
        runtimeRoot,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_scheduling_state_root_escape/,
  );
});

test("scheduling binding rejects a ledger symlink that escapes the selected state root", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-ledger-escape-"),
  );
  const environmentRoot = path.join(fixtureRoot, "synthetic-qa");
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const stateRoot = path.join(environmentRoot, "state", "runtime", "isolated");
  const foreignSchedulingRoot = path.join(fixtureRoot, "foreign-scheduling");
  fs.mkdirSync(runtimeRoot, { recursive: true });
  fs.mkdirSync(stateRoot, { recursive: true });
  fs.mkdirSync(foreignSchedulingRoot, { recursive: true });
  fs.writeFileSync(path.join(foreignSchedulingRoot, "schedules.db"), "");
  fs.symlinkSync(
    foreignSchedulingRoot,
    path.join(stateRoot, "scheduling"),
    "dir",
  );

  assert.throws(
    () =>
      resolveSelectedSchedulingRuntimeBinding({
        env: {
          SCHEDULING_MCP_URL: "http://127.0.0.1:18091/mcp",
          VIVENTIUM_SCHEDULING_MCP_PORT: "18091",
        },
        runtimeRoot,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_scheduling_db_path_escape/,
  );
});

test("scheduling health proves the exact selected loopback service and ledger without exposing a path", async () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-health-"),
  );
  const dbPath = path.join(fixtureRoot, "schedules.db");
  fs.writeFileSync(dbPath, "");
  const expectedDbPathSha256 = crypto
    .createHash("sha256")
    .update(fs.realpathSync(dbPath))
    .digest("hex");
  const receipt = await verifySchedulingMcpHealth(
    {
      mcpUrl: "http://127.0.0.1:18091/mcp",
      dbPath,
    },
    {
      fetchImpl: async (url) => {
        assert.equal(url, "http://127.0.0.1:18091/health");
        return {
          ok: true,
          status: 200,
          json: async () => ({
            status: "ok",
            service: "scheduling-cortex",
            db_path_sha256: expectedDbPathSha256,
          }),
        };
      },
    },
  );

  assert.deepEqual(receipt.publicMetrics, {
    checkCount: 1,
    pass: true,
    reachable: true,
    httpOk: true,
    statusOk: true,
    serviceMatch: true,
    dbPathMatch: true,
    dbPathSha256: expectedDbPathSha256,
  });
  assert.equal(
    JSON.stringify(receipt.publicMetrics).includes(fixtureRoot),
    false,
  );
  assert.equal(
    receipt.privateReceipt.expectedDbPathSha256,
    expectedDbPathSha256,
  );
});

test("scheduling health rejects a wrong service identity", async () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-health-service-"),
  );
  const dbPath = path.join(fixtureRoot, "schedules.db");
  fs.writeFileSync(dbPath, "");
  const expectedDbPathSha256 = crypto
    .createHash("sha256")
    .update(fs.realpathSync(dbPath))
    .digest("hex");
  const receipt = await verifySchedulingMcpHealth(
    { mcpUrl: "http://127.0.0.1:18091/mcp", dbPath },
    {
      fetchImpl: async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ok",
          service: "foreign-service",
          db_path_sha256: expectedDbPathSha256,
        }),
      }),
    },
  );
  assert.equal(receipt.publicMetrics.pass, false);
  assert.equal(receipt.publicMetrics.serviceMatch, false);
});

test("scheduling health rejects a wrong ledger identity", async () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-health-ledger-"),
  );
  const dbPath = path.join(fixtureRoot, "schedules.db");
  fs.writeFileSync(dbPath, "");
  const receipt = await verifySchedulingMcpHealth(
    { mcpUrl: "http://127.0.0.1:18091/mcp", dbPath },
    {
      fetchImpl: async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ok",
          service: "scheduling-cortex",
          db_path_sha256: "f".repeat(64),
        }),
      }),
    },
  );
  assert.equal(receipt.publicMetrics.pass, false);
  assert.equal(receipt.publicMetrics.dbPathMatch, false);
});

test("scheduling health fails closed when the selected service is unavailable", async () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-health-unavailable-"),
  );
  const dbPath = path.join(fixtureRoot, "schedules.db");
  fs.writeFileSync(dbPath, "");
  const receipt = await verifySchedulingMcpHealth(
    { mcpUrl: "http://127.0.0.1:18091/mcp", dbPath },
    {
      fetchImpl: async () => {
        throw new Error("synthetic unavailable");
      },
    },
  );
  assert.equal(receipt.publicMetrics.pass, false);
  assert.equal(receipt.publicMetrics.reachable, false);
});

test("scheduling lifecycle preflight checks health before reading the selected ledger", async () => {
  let ledgerRead = false;
  await assert.rejects(
    async () =>
      prepareExpectedScheduleLifecycle(
        {
          binding: {
            dbPath: "/private/runtime/schedules.db",
            mcpUrl: "http://127.0.0.1:18091/mcp",
          },
          userId: "qa-user",
          nonce: "ANTI012-effect-public-123",
        },
        {
          verifyHealth: async () => ({ publicMetrics: { pass: false } }),
          readState: () => {
            ledgerRead = true;
            return { matchingRowCount: 0 };
          },
        },
      ),
    /selected_scheduling_mcp_health_mismatch/,
  );
  assert.equal(ledgerRead, false);
});

test("scheduling state inspection scopes the nonce to the exact QA owner and fingerprints protected rows", () => {
  const { DatabaseSync } = require("node:sqlite");
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "anti-012-scheduling-db-"),
  );
  const dbPath = path.join(fixtureRoot, "schedules.db");
  const db = new DatabaseSync(dbPath);
  db.exec(`
    CREATE TABLE scheduled_tasks (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      prompt TEXT NOT NULL,
      metadata_json TEXT,
      active INTEGER NOT NULL
    )
  `);
  const insert = db.prepare(
    "INSERT INTO scheduled_tasks (id, user_id, prompt, metadata_json, active) VALUES (?, ?, ?, ?, ?)",
  );
  insert.run(
    "protected-task",
    "qa-user",
    "Existing protected reminder",
    "{}",
    1,
  );
  insert.run(
    "effect-task",
    "qa-user",
    "Synthetic reminder ANTI012-effect-public-123",
    "{}",
    1,
  );
  insert.run(
    "foreign-task",
    "another-user",
    "Synthetic reminder ANTI012-effect-public-123",
    "{}",
    1,
  );
  db.close();

  const state = readSchedulingState({
    dbPath,
    userId: "qa-user",
    nonce: "ANTI012-effect-public-123",
  });
  assert.equal(state.matchingRowCount, 1);
  assert.equal(state.activeMatchingRowCount, 1);
  assert.deepEqual(state.matchingTaskIds, ["effect-task"]);
  assert.equal(state.protectedRowCount, 2);
  assert.match(state.protectedFingerprint, /^[a-f0-9]{64}$/);
  assert.equal(
    JSON.stringify(state).includes("Existing protected reminder"),
    false,
  );
});

test("supported scheduling cleanup checks health before opening an MCP client", async () => {
  let clientOpened = false;
  const result = await deleteScheduleThroughMcp(
    {
      mcpUrl: "http://127.0.0.1:18091/mcp",
      dbPath: "/private/runtime/schedules.db",
      userId: "qa-user-id",
      agentId: "agent-main",
      taskId: "task-private-id",
    },
    {
      verifyHealth: async () => ({ publicMetrics: { pass: false } }),
      transportFactory: () => ({ marker: "transport" }),
      clientFactory() {
        clientOpened = true;
        return {
          async connect() {},
          async callTool() {
            return { structuredContent: { success: true } };
          },
          async close() {},
        };
      },
    },
  );
  assert.equal(clientOpened, false);
  assert.equal(result.pass, false);
});

test("supported scheduling cleanup calls exact MCP delete with structural identity headers", async () => {
  const calls = [];
  const transport = { marker: "transport" };
  const health = {
    publicMetrics: { pass: true, checkCount: 1, dbPathSha256: "a".repeat(64) },
  };
  const result = await deleteScheduleThroughMcp(
    {
      mcpUrl: "http://127.0.0.1:18091/mcp",
      dbPath: "/private/runtime/schedules.db",
      userId: "qa-user-id",
      agentId: "agent-main",
      taskId: "task-private-id",
    },
    {
      verifyHealth: async () => health,
      transportFactory(url, options) {
        assert.equal(url.toString(), "http://127.0.0.1:18091/mcp");
        assert.deepEqual(options.requestInit.headers, {
          "x-viventium-user-id": "qa-user-id",
          "x-viventium-agent-id": "agent-main",
        });
        return transport;
      },
      clientFactory() {
        return {
          async connect(selectedTransport) {
            assert.equal(selectedTransport, transport);
          },
          async callTool(request) {
            calls.push(request);
            return { structuredContent: { success: true } };
          },
          async close() {},
        };
      },
    },
  );

  assert.deepEqual(calls, [
    {
      name: "schedule_delete",
      arguments: { args: { task_id: "task-private-id" } },
    },
  ]);
  assert.deepEqual(result, { pass: true, health });
});

test("scheduling lifecycle fails closed unless one row is created, deleted through MCP, and protected baseline stays unchanged", async () => {
  const baseline = {
    matchingRowCount: 0,
    activeMatchingRowCount: 0,
    matchingTaskIds: [],
    protectedRowCount: 6,
    protectedFingerprint: "a".repeat(64),
    health: {
      publicMetrics: {
        pass: true,
        checkCount: 1,
        dbPathSha256: "b".repeat(64),
      },
    },
  };
  const states = [
    {
      matchingRowCount: 1,
      activeMatchingRowCount: 1,
      matchingTaskIds: ["effect-task"],
      protectedRowCount: 6,
      protectedFingerprint: "a".repeat(64),
    },
    {
      matchingRowCount: 0,
      activeMatchingRowCount: 0,
      matchingTaskIds: [],
      protectedRowCount: 6,
      protectedFingerprint: "a".repeat(64),
    },
  ];
  const deleted = [];
  const receipt = await finalizeExpectedScheduleLifecycle(
    {
      baseline,
      binding: {
        dbPath: "/private/runtime/schedules.db",
        mcpUrl: "http://127.0.0.1:18091/mcp",
      },
      userId: "qa-user",
      agentId: "agent-main",
      nonce: "ANTI012-effect-public-123",
    },
    {
      readState: () => states.shift(),
      deleteSchedule: async ({ taskId }) => {
        deleted.push(taskId);
        return {
          pass: true,
          health: { publicMetrics: { pass: true, checkCount: 1 } },
        };
      },
    },
  );

  assert.deepEqual(deleted, ["effect-task"]);
  assert.deepEqual(receipt.publicMetrics, {
    required: true,
    pass: true,
    preflightMatchingRowCount: 0,
    postRunMatchingRowCount: 1,
    cleanupAttemptCount: 1,
    cleanupSuccessCount: 1,
    postCleanupMatchingRowCount: 0,
    protectedBaselineStable: true,
    schedulingHealthCheckCount: 2,
    schedulingHealthSuccessCount: 2,
    schedulingPreflightHealthVerified: true,
    schedulingCleanupHealthVerified: true,
    schedulingDbPathSha256: "b".repeat(64),
  });

  const failed = await finalizeExpectedScheduleLifecycle(
    {
      baseline,
      binding: {
        dbPath: "/private/runtime/schedules.db",
        mcpUrl: "http://127.0.0.1:18091/mcp",
      },
      userId: "qa-user",
      agentId: "agent-main",
      nonce: "ANTI012-effect-public-123",
    },
    {
      readState: (() => {
        const sequence = [statesForFailure(true), statesForFailure(true)];
        return () => sequence.shift();
      })(),
      deleteSchedule: async () => ({
        pass: false,
        health: { publicMetrics: { pass: true, checkCount: 1 } },
      }),
    },
  );
  assert.equal(failed.publicMetrics.pass, false);
  assert.equal(failed.publicMetrics.cleanupSuccessCount, 0);
  assert.equal(failed.publicMetrics.postCleanupMatchingRowCount, 1);

  function statesForFailure(withMatch) {
    return {
      matchingRowCount: withMatch ? 1 : 0,
      activeMatchingRowCount: withMatch ? 1 : 0,
      matchingTaskIds: withMatch ? ["effect-task"] : [],
      protectedRowCount: 6,
      protectedFingerprint: "a".repeat(64),
    };
  }
});

test("scheduling lifecycle preflight refuses a dirty owner-and-nonce baseline before submit", async () => {
  const healthy = async () => ({
    publicMetrics: {
      pass: true,
      checkCount: 1,
      dbPathSha256: "a".repeat(64),
    },
  });
  const clean = await prepareExpectedScheduleLifecycle(
    {
      binding: { dbPath: "/private/runtime/schedules.db" },
      userId: "qa-user",
      nonce: "ANTI012-effect-public-123",
    },
    {
      verifyHealth: healthy,
      readState: () => ({
        matchingRowCount: 0,
        activeMatchingRowCount: 0,
        matchingTaskIds: [],
        protectedRowCount: 6,
        protectedFingerprint: "a".repeat(64),
      }),
    },
  );
  assert.equal(clean.matchingRowCount, 0);

  await assert.rejects(
    async () =>
      prepareExpectedScheduleLifecycle(
        {
          binding: { dbPath: "/private/runtime/schedules.db" },
          userId: "qa-user",
          nonce: "ANTI012-effect-public-123",
        },
        {
          verifyHealth: healthy,
          readState: () => ({ matchingRowCount: 1 }),
        },
      ),
    /expected_schedule_nonce_not_clean_before_submit/,
  );
});

test("parseArgs accepts a strict reopen-only conversation identifier without relaxing the run contract", () => {
  const outputDir = path.join(os.tmpdir(), "viventium-private-qa-reopen");
  const parsed = parseArgs([
    ...requiredArgs(outputDir),
    "--reopen-conversation=conversation_synthetic-123",
  ]);

  assert.equal(parsed.runMode, "reopen");
  assert.equal(parsed.reopenConversationId, "conversation_synthetic-123");
  assert.equal(parsed.prompt, "Evaluate this synthetic reversible decision.");
  assert.throws(
    () =>
      parseArgs([
        ...requiredArgs(outputDir),
        "--reopen-conversation=../foreign-conversation",
      ]),
    /reopen_conversation_must_be_a_safe_identifier/,
  );
});

test("reopen observer records agent chat POSTs without intercepting or injecting requests", () => {
  const listeners = new Map();
  const page = {
    on(event, listener) {
      listeners.set(event, listener);
    },
    off(event, listener) {
      assert.equal(listeners.get(event), listener);
      listeners.delete(event);
    },
  };
  const observer = createAgentChatPostObserver(page);
  const emit = (method, url) =>
    listeners.get("request")?.({ method: () => method, url: () => url });

  emit("GET", "http://localhost:3180/api/agents/chat/agents");
  emit("POST", "http://localhost:3180/api/auth/refresh");
  assert.equal(observer.count(), 0);
  emit("POST", "http://localhost:3180/api/agents/chat/agents");
  assert.equal(observer.count(), 1);
  observer.stop();
  assert.equal(listeners.has("request"), false);
});

test("reopen chat guard blocks accidental agent submissions without rewriting any request", async () => {
  let handler;
  const page = {
    async route(pattern, callback) {
      assert.equal(pattern, "**/api/agents/chat**");
      handler = callback;
    },
  };
  await installReopenChatPostGuard(page);
  const actions = [];
  const makeRoute = (method, url) => ({
    request: () => ({ method: () => method, url: () => url }),
    abort: async (reason) => actions.push(["abort", reason]),
    continue: async (...args) => actions.push(["continue", args]),
  });

  await handler(
    makeRoute("POST", "http://localhost:3180/api/agents/chat/agents"),
  );
  await handler(
    makeRoute("GET", "http://localhost:3180/api/agents/chat/status/run"),
  );
  assert.deepEqual(actions, [
    ["abort", "blockedbyclient"],
    ["continue", []],
  ]);
});

test("reopen settlement scrolls the structural message viewport before requiring the correlated terminal Main answer", () => {
  let terminalContentMounted = false;
  const viewport = {
    parentElement: null,
    scrollHeight: 2400,
    clientHeight: 600,
    scrollTop: 0,
    scrollTo({ top }) {
      this.scrollTop = Math.min(top, this.scrollHeight - this.clientHeight);
    },
  };
  const content = { parentElement: viewport };
  const terminal = {
    parentElement: content,
    scrollIntoView() {
      terminalContentMounted = true;
    },
  };
  const mainPart = {
    dataset: { viventiumAgentId: "agent-main" },
    textContent: "Final Main answer with complete synthetic evidence.",
  };
  const assistantMessage = {
    id: "assistant-terminal",
    querySelector(selector) {
      return selector === ".agent-turn" ? {} : null;
    },
    querySelectorAll(selector) {
      return selector === ".message-content" ? [mainPart] : [];
    },
  };
  const documentFixture = {
    getElementById(id) {
      return id === "messages-end" ? terminal : null;
    },
    querySelectorAll(selector) {
      if (selector !== ".message-render" || !terminalContentMounted) return [];
      return [assistantMessage];
    },
  };
  const expected = {
    messageId: "assistant-terminal",
    agentId: "agent-main",
    answerText: "Final Main answer with complete synthetic evidence.",
  };
  const getStyle = (element) => ({
    overflowY: element === viewport ? "auto" : "visible",
  });

  assert.equal(
    correlatedVisibleAnswerInDocument(expected, documentFixture),
    false,
    "terminal answer is not observable before the message viewport settles",
  );
  const receipt = scrollTerminalMessageViewportInDocument(
    documentFixture,
    getStyle,
  );
  assert.deepEqual(receipt, {
    found: true,
    atBottom: true,
    scrollHeight: 2400,
    clientHeight: 600,
  });
  assert.equal(viewport.scrollTop, 1800);
  assert.equal(
    correlatedVisibleAnswerInDocument(expected, documentFixture),
    true,
  );
  assert.equal(
    correlatedVisibleAnswerInDocument(
      { ...expected, agentId: "agent-consultant" },
      documentFixture,
    ),
    false,
  );
  assert.equal(
    correlatedVisibleAnswerInDocument(
      { ...expected, messageId: "assistant-stale" },
      documentFixture,
    ),
    false,
  );
});

test("reopen settlement keeps the structural viewport at the true bottom when terminal alignment leaves trailing space", () => {
  const operations = [];
  const viewport = {
    parentElement: null,
    scrollHeight: 1457,
    clientHeight: 955,
    scrollTop: 0,
    scrollTo({ top }) {
      operations.push("scrollTo");
      this.scrollTop = Math.min(top, this.scrollHeight - this.clientHeight);
    },
  };
  const content = { parentElement: viewport };
  const terminal = {
    parentElement: content,
    scrollIntoView() {
      operations.push("scrollIntoView");
      viewport.scrollTop = 467;
    },
  };
  const documentFixture = {
    getElementById: (id) => (id === "messages-end" ? terminal : null),
  };
  const getStyle = (element) => ({
    overflowY: element === viewport ? "auto" : "visible",
  });

  assert.deepEqual(
    scrollTerminalMessageViewportInDocument(documentFixture, getStyle),
    {
      found: true,
      atBottom: true,
      scrollHeight: 1457,
      clientHeight: 955,
    },
  );
  assert.deepEqual(operations, ["scrollIntoView", "scrollTo"]);
  assert.equal(viewport.scrollTop, 502);
});

test("reopen settlement re-scrolls when terminal content grows after the first structural scroll", async () => {
  let scrollCount = 0;
  const viewport = {
    parentElement: null,
    scrollHeight: 1800,
    clientHeight: 600,
    scrollTop: 0,
    scrollTo({ top }) {
      scrollCount += 1;
      this.scrollTop = Math.min(top, this.scrollHeight - this.clientHeight);
      if (scrollCount === 1) this.scrollHeight = 3000;
    },
  };
  const content = { parentElement: viewport };
  const terminal = {
    parentElement: content,
    scrollIntoView() {},
  };
  const mainPart = {
    dataset: { viventiumAgentId: "agent-main" },
    textContent: "Final Main answer after the terminal layout settles.",
  };
  const assistantMessage = {
    id: "assistant-terminal",
    querySelector: (selector) => (selector === ".agent-turn" ? {} : null),
    querySelectorAll: (selector) =>
      selector === ".message-content" ? [mainPart] : [],
  };
  const documentFixture = {
    getElementById: (id) => (id === "messages-end" ? terminal : null),
    querySelectorAll: (selector) =>
      selector === ".message-render" ? [assistantMessage] : [],
  };
  const expected = {
    messageId: "assistant-terminal",
    agentId: "agent-main",
    answerText: "Final Main answer after the terminal layout settles.",
  };
  const getStyle = (element) => ({
    overflowY: element === viewport ? "auto" : "visible",
  });
  const evaluatedFunctions = [];
  const page = {
    locator(selector) {
      assert.equal(selector, "#messages-end");
      return {
        waitFor: async (options) =>
          assert.deepEqual(options, { state: "attached", timeout: 15_000 }),
      };
    },
    async evaluate(pageFunction, argument) {
      evaluatedFunctions.push(pageFunction);
      if (pageFunction === scrollTerminalMessageViewportInDocument) {
        return pageFunction(documentFixture, getStyle);
      }
      if (pageFunction === correlatedVisibleAnswerInDocument) {
        return pageFunction(argument, documentFixture);
      }
      throw new Error("unexpected_page_function");
    },
    async waitForTimeout() {},
  };

  const receipt = await waitForCorrelatedVisibleAnswer(page, expected, 15_000);
  assert.deepEqual(receipt, {
    found: true,
    atBottom: true,
    scrollHeight: 3000,
    clientHeight: 600,
  });
  assert.equal(viewport.scrollTop, 2400);
  assert.equal(scrollCount, 2);
  assert.deepEqual(evaluatedFunctions, [
    scrollTerminalMessageViewportInDocument,
    correlatedVisibleAnswerInDocument,
    scrollTerminalMessageViewportInDocument,
    correlatedVisibleAnswerInDocument,
  ]);
  const browserGlobals = {
    document: documentFixture,
    expected,
    window: { getComputedStyle: getStyle },
  };
  assert.equal(
    vm.runInNewContext(
      `(${String(scrollTerminalMessageViewportInDocument)})().found`,
      browserGlobals,
    ),
    true,
  );
  assert.equal(
    vm.runInNewContext(
      `(${String(correlatedVisibleAnswerInDocument)})(expected)`,
      browserGlobals,
    ),
    true,
  );
});

test("loadSelectedRuntimeEnv cannot inherit canonical production DB state over the selected QA runtime", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-binding-"),
  );
  const runtimeName = "synthetic-qa";
  const runtimeRoot = path.join(fixtureRoot, runtimeName, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.writeFileSync(
    sharedEnvPath,
    "MONGO_URI=mongodb://canonical-prod.invalid/prod\nJWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  const runtimeEnvPath = path.join(runtimeRoot, "runtime.env");
  const runtimeEnvText = [
    "VIVENTIUM_DEV_ENV_ENABLED=true",
    `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
    "VIVENTIUM_RUNTIME_PROFILE=isolated",
    "VIVENTIUM_LC_API_PORT=5180",
    "VIVENTIUM_LC_FRONTEND_PORT=5190",
    "VIVENTIUM_LOCAL_MONGO_PORT=29117",
    "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
    "",
  ].join("\n");
  fs.writeFileSync(runtimeEnvPath, runtimeEnvText);
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic\n",
  );
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot).map((arg) =>
      arg
        .replace("http://localhost:3190", "http://localhost:5190")
        .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180"),
    ),
  );
  const selected = loadSelectedRuntimeEnv(args, {
    processEnv: {
      MONGO_URI: "mongodb://process-prod.invalid/prod",
      VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
      VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    },
    sharedEnvPath,
    repoRoot: REPO_ROOT,
  });

  assert.equal(
    selected.env.MONGO_URI,
    "mongodb://127.0.0.1:29117/ViventiumQaSynthetic",
  );
  assert.equal(selected.env.JWT_SECRET, "shared-jwt");
  assert.equal(selected.runtimeIdentity, runtimeName);
  assert.equal(selected.apiPort, 5180);
  assert.equal(selected.clientPort, 5190);
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(
        { ...args, apiBase: "http://localhost:3180" },
        { processEnv: {}, sharedEnvPath, repoRoot: REPO_ROOT },
      ),
    /selected_runtime_api_port_mismatch/,
  );

  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://canonical-prod.invalid/prod\n",
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: { MONGO_URI: "mongodb://process-prod.invalid/prod" },
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_service_mongo_matches_shared/,
  );

  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://127.0.0.1:27017/ViventiumQaSynthetic\n",
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {},
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_service_mongo_outside_isolated_runtime/,
  );

  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic\n",
  );
  fs.writeFileSync(
    runtimeEnvPath,
    runtimeEnvText.replace(
      "VIVENTIUM_RUNTIME_PROFILE=isolated",
      "VIVENTIUM_RUNTIME_PROFILE=shared",
    ),
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {},
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_profile_not_isolated/,
  );

  fs.writeFileSync(
    runtimeEnvPath,
    runtimeEnvText
      .replace("VIVENTIUM_LOCAL_MONGO_PORT=29117\n", "")
      .replace("VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic\n", ""),
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {},
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_missing_mongo_uri/,
  );
});

test("loadSelectedRuntimeEnv constructs blank service Mongo only from selected local runtime fields", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-local-mongo-"),
  );
  const runtimeName = "synthetic-qa-local-mongo";
  const runtimeRoot = path.join(fixtureRoot, runtimeName, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.writeFileSync(
    sharedEnvPath,
    "MONGO_URI=mongodb://canonical-prod.invalid/prod\nJWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  const runtimeEnvPath = path.join(runtimeRoot, "runtime.env");
  const runtimeEnvText = [
    "VIVENTIUM_DEV_ENV_ENABLED=true",
    `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
    "VIVENTIUM_RUNTIME_PROFILE=isolated",
    "VIVENTIUM_LC_API_PORT=5180",
    "VIVENTIUM_LC_FRONTEND_PORT=5190",
    "VIVENTIUM_LOCAL_MONGO_PORT=29117",
    "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
    "",
  ].join("\n");
  fs.writeFileSync(runtimeEnvPath, runtimeEnvText);
  fs.writeFileSync(path.join(serviceEnvDir, "librechat.env"), "MONGO_URI=\n");
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot).map((arg) =>
      arg
        .replace("http://localhost:3190", "http://localhost:5190")
        .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180"),
    ),
  );

  const selected = loadSelectedRuntimeEnv(args, {
    processEnv: { MONGO_URI: "mongodb://process-prod.invalid/prod" },
    sharedEnvPath,
    repoRoot: REPO_ROOT,
  });
  assert.equal(
    selected.env.MONGO_URI,
    "mongodb://127.0.0.1:29117/ViventiumQaSynthetic",
  );
  assert.equal(selected.mongoSource, "selected_runtime_local_fields");
  assert.equal(selected.env.JWT_SECRET, "shared-jwt");
  assert.equal(selected.env.JWT_REFRESH_SECRET, "shared-refresh");

  fs.writeFileSync(runtimeEnvPath, runtimeEnvText.replace("29117", "70000"));
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {},
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_invalid_local_mongo_port/,
  );
  fs.writeFileSync(
    runtimeEnvPath,
    runtimeEnvText.replace("ViventiumQaSynthetic", "../not-a-database"),
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {},
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_invalid_local_mongo_database/,
  );
  fs.writeFileSync(runtimeEnvPath, runtimeEnvText);

  fs.writeFileSync(
    sharedEnvPath,
    "MONGO_URI=mongodb://canonical-prod.invalid/prod\n",
  );
  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {
          MONGO_URI: "mongodb://process-prod.invalid/prod",
          JWT_SECRET: "process-jwt-must-not-substitute",
          JWT_REFRESH_SECRET: "process-refresh-must-not-substitute",
        },
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_missing_shared_jwt_secrets/,
  );
});

test("loadSelectedRuntimeEnv derives scheduling state from the compiled isolated dev-env shape", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-scheduling-shape-"),
  );
  const runtimeName = "synthetic-qa";
  const environmentRoot = path.join(fixtureRoot, runtimeName);
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const schedulingDbPath = path.join(
    environmentRoot,
    "state",
    "runtime",
    "isolated",
    "scheduling",
    "schedules.db",
  );
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.mkdirSync(path.dirname(schedulingDbPath), { recursive: true });
  fs.writeFileSync(schedulingDbPath, "");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.writeFileSync(
    sharedEnvPath,
    "JWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  fs.writeFileSync(
    path.join(runtimeRoot, "runtime.env"),
    [
      "VIVENTIUM_DEV_ENV_ENABLED=true",
      `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
      "VIVENTIUM_RUNTIME_PROFILE=isolated",
      "VIVENTIUM_LC_API_PORT=5180",
      "VIVENTIUM_LC_FRONTEND_PORT=5190",
      "VIVENTIUM_LOCAL_MONGO_PORT=29117",
      "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18091",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic\n",
  );
  const nonce = "ANTI012-effect-public-123";
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot)
      .map((arg) =>
        arg
          .replace("http://localhost:3190", "http://localhost:5190")
          .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180")
          .replace(
            "Evaluate this synthetic reversible decision.",
            `Create one future synthetic reminder labeled ${nonce}.`,
          ),
      )
      .concat([
        "--expect-tool=schedule_create_mcp_scheduling-cortex",
        `--expect-schedule-nonce=${nonce}`,
      ]),
  );

  const selected = loadSelectedRuntimeEnv(args, {
    processEnv: {
      VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
      VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
    },
    sharedEnvPath,
    repoRoot: REPO_ROOT,
  });
  assert.equal(selected.scheduling.dbPath, fs.realpathSync(schedulingDbPath));
  assert.equal(selected.scheduling.mcpUrl, "http://127.0.0.1:18091/mcp");
});

test("loadSelectedRuntimeEnv rejects a scheduling MCP binding inherited only from shared or process env", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-scheduling-provenance-"),
  );
  const runtimeName = "synthetic-qa";
  const environmentRoot = path.join(fixtureRoot, runtimeName);
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const schedulingDbPath = path.join(
    environmentRoot,
    "state",
    "runtime",
    "isolated",
    "scheduling",
    "schedules.db",
  );
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.mkdirSync(path.dirname(schedulingDbPath), { recursive: true });
  fs.writeFileSync(schedulingDbPath, "");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.writeFileSync(
    sharedEnvPath,
    [
      "JWT_SECRET=shared-jwt",
      "JWT_REFRESH_SECRET=shared-refresh",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18091",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  const runtimeEnvPath = path.join(runtimeRoot, "runtime.env");
  const runtimeEnvLines = [
    "VIVENTIUM_DEV_ENV_ENABLED=true",
    `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
    "VIVENTIUM_RUNTIME_PROFILE=isolated",
    "VIVENTIUM_LC_API_PORT=5180",
    "VIVENTIUM_LC_FRONTEND_PORT=5190",
    "VIVENTIUM_LOCAL_MONGO_PORT=29117",
    "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
  ];
  fs.writeFileSync(runtimeEnvPath, [...runtimeEnvLines, ""].join("\n"));
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic\n",
  );
  const nonce = "ANTI012-effect-public-123";
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot)
      .map((arg) =>
        arg
          .replace("http://localhost:3190", "http://localhost:5190")
          .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180")
          .replace(
            "Evaluate this synthetic reversible decision.",
            `Create one future synthetic reminder labeled ${nonce}.`,
          ),
      )
      .concat([
        "--expect-tool=schedule_create_mcp_scheduling-cortex",
        `--expect-schedule-nonce=${nonce}`,
      ]),
  );

  const load = (processOverrides = {}) =>
    loadSelectedRuntimeEnv(args, {
      processEnv: {
        VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
        VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
        ...processOverrides,
      },
      sharedEnvPath,
      repoRoot: REPO_ROOT,
    });
  assert.throws(
    () => load(),
    /selected_runtime_scheduling_mcp_binding_missing/,
  );
  fs.writeFileSync(
    sharedEnvPath,
    "JWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  const inheritedProcessBinding = {
    VIVENTIUM_SCHEDULING_MCP_PORT: "18091",
    SCHEDULING_MCP_URL: "http://127.0.0.1:18091/mcp",
  };
  assert.throws(
    () => load(inheritedProcessBinding),
    /selected_runtime_scheduling_mcp_binding_missing/,
  );
  fs.writeFileSync(
    runtimeEnvPath,
    [
      ...runtimeEnvLines,
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  assert.throws(
    () => load(inheritedProcessBinding),
    /selected_runtime_scheduling_mcp_binding_missing/,
  );
  fs.writeFileSync(
    runtimeEnvPath,
    [...runtimeEnvLines, "VIVENTIUM_SCHEDULING_MCP_PORT=18091", ""].join("\n"),
  );
  assert.throws(
    () => load(inheritedProcessBinding),
    /selected_runtime_scheduling_mcp_binding_missing/,
  );
});

test("loadSelectedRuntimeEnv rejects conflicting scheduling MCP bindings across selected runtime overlays", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-scheduling-conflict-"),
  );
  const runtimeName = "synthetic-qa";
  const environmentRoot = path.join(fixtureRoot, runtimeName);
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const schedulingDbPath = path.join(
    environmentRoot,
    "state",
    "runtime",
    "isolated",
    "scheduling",
    "schedules.db",
  );
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.mkdirSync(path.dirname(schedulingDbPath), { recursive: true });
  fs.writeFileSync(schedulingDbPath, "");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.writeFileSync(
    sharedEnvPath,
    "JWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  fs.writeFileSync(
    path.join(runtimeRoot, "runtime.env"),
    [
      "VIVENTIUM_DEV_ENV_ENABLED=true",
      `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
      "VIVENTIUM_RUNTIME_PROFILE=isolated",
      "VIVENTIUM_LC_API_PORT=5180",
      "VIVENTIUM_LC_FRONTEND_PORT=5190",
      "VIVENTIUM_LOCAL_MONGO_PORT=29117",
      "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18091",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    [
      "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18092",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18092/mcp",
      "",
    ].join("\n"),
  );
  const nonce = "ANTI012-effect-public-123";
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot)
      .map((arg) =>
        arg
          .replace("http://localhost:3190", "http://localhost:5190")
          .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180")
          .replace(
            "Evaluate this synthetic reversible decision.",
            `Create one future synthetic reminder labeled ${nonce}.`,
          ),
      )
      .concat([
        "--expect-tool=schedule_create_mcp_scheduling-cortex",
        `--expect-schedule-nonce=${nonce}`,
      ]),
  );

  assert.throws(
    () =>
      loadSelectedRuntimeEnv(args, {
        processEnv: {
          VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
          VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
        },
        sharedEnvPath,
        repoRoot: REPO_ROOT,
      }),
    /selected_runtime_scheduling_mcp_binding_conflict/,
  );
});

test("loadSelectedRuntimeEnv rejects a scheduling MCP URL and port split across selected overlays", () => {
  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-runtime-scheduling-split-"),
  );
  const runtimeName = "synthetic-qa";
  const environmentRoot = path.join(fixtureRoot, runtimeName);
  const runtimeRoot = path.join(environmentRoot, "runtime");
  const serviceEnvDir = path.join(runtimeRoot, "service-env");
  const schedulingDbPath = path.join(
    environmentRoot,
    "state",
    "runtime",
    "isolated",
    "scheduling",
    "schedules.db",
  );
  fs.mkdirSync(serviceEnvDir, { recursive: true });
  fs.mkdirSync(path.dirname(schedulingDbPath), { recursive: true });
  fs.writeFileSync(schedulingDbPath, "");
  const sharedEnvPath = path.join(fixtureRoot, "shared.env");
  fs.writeFileSync(
    sharedEnvPath,
    "JWT_SECRET=shared-jwt\nJWT_REFRESH_SECRET=shared-refresh\n",
  );
  fs.writeFileSync(
    path.join(runtimeRoot, "runtime.env"),
    [
      "VIVENTIUM_DEV_ENV_ENABLED=true",
      `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
      "VIVENTIUM_RUNTIME_PROFILE=isolated",
      "VIVENTIUM_LC_API_PORT=5180",
      "VIVENTIUM_LC_FRONTEND_PORT=5190",
      "VIVENTIUM_LOCAL_MONGO_PORT=29117",
      "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    [
      "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18091",
      "",
    ].join("\n"),
  );
  const nonce = "ANTI012-effect-public-123";
  const args = parseArgs(
    requiredArgs(path.join(fixtureRoot, "evidence"), runtimeRoot)
      .map((arg) =>
        arg
          .replace("http://localhost:3190", "http://localhost:5190")
          .replace("http://127.0.0.1:3180", "http://127.0.0.1:5180")
          .replace(
            "Evaluate this synthetic reversible decision.",
            `Create one future synthetic reminder labeled ${nonce}.`,
          ),
      )
      .concat([
        "--expect-tool=schedule_create_mcp_scheduling-cortex",
        `--expect-schedule-nonce=${nonce}`,
      ]),
  );

  const load = () =>
    loadSelectedRuntimeEnv(args, {
      processEnv: {
        VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
        VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
      },
      sharedEnvPath,
      repoRoot: REPO_ROOT,
    });
  assert.throws(load, /selected_runtime_scheduling_mcp_binding_missing/);
  fs.writeFileSync(
    path.join(runtimeRoot, "runtime.env"),
    [
      "VIVENTIUM_DEV_ENV_ENABLED=true",
      `VIVENTIUM_DEV_ENV_NAME=${runtimeName}`,
      "VIVENTIUM_RUNTIME_PROFILE=isolated",
      "VIVENTIUM_LC_API_PORT=5180",
      "VIVENTIUM_LC_FRONTEND_PORT=5190",
      "VIVENTIUM_LOCAL_MONGO_PORT=29117",
      "VIVENTIUM_LOCAL_MONGO_DB=ViventiumQaSynthetic",
      "VIVENTIUM_SCHEDULING_MCP_PORT=18091",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  assert.throws(load, /selected_runtime_scheduling_mcp_binding_missing/);
  fs.writeFileSync(
    path.join(serviceEnvDir, "librechat.env"),
    [
      "MONGO_URI=mongodb://127.0.0.1:29117/ViventiumQaSynthetic",
      "SCHEDULING_MCP_URL=http://127.0.0.1:18091/mcp",
      "",
    ].join("\n"),
  );
  assert.throws(load, /selected_runtime_scheduling_mcp_binding_missing/);
});

test("preflightSelectedRuntime requires healthy matching API and Web identity before auth", async () => {
  const args = {
    apiBase: "http://localhost:5180",
    clientBase: "http://localhost:5190",
  };
  const runtime = {
    runtimeIdentity: "synthetic-qa",
    apiPort: 5180,
    clientPort: 5190,
  };
  const healthyFetch = async (url) => {
    if (String(url).endsWith("/api/config")) {
      return new Response(JSON.stringify({ appTitle: "Viventium" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("ok", { status: 200 });
  };

  assert.deepEqual(
    await preflightSelectedRuntime({ args, runtime, fetchImpl: healthyFetch }),
    {
      pass: true,
      healthStatus: 200,
      configStatus: 200,
      clientStatus: 200,
      appTitle: "Viventium",
      runtimeIdentity: "synthetic-qa",
      apiPort: 5180,
      clientPort: 5190,
    },
  );
  await assert.rejects(
    () =>
      preflightSelectedRuntime({
        args,
        runtime,
        fetchImpl: async () =>
          new Response(JSON.stringify({ appTitle: "Not Viventium" }), {
            status: 200,
          }),
      }),
    /selected_runtime_http_identity_preflight_failed/,
  );
});

test("deleteInsertedAuthSession targets only the exact inserted session", async () => {
  const calls = [];
  const sessionId = { synthetic: "session-id" };
  const db = {
    collection(name) {
      calls.push({ operation: "collection", name });
      return {
        async deleteOne(filter) {
          calls.push({ operation: "deleteOne", filter });
          return { deletedCount: 1 };
        },
      };
    },
  };

  assert.equal(await deleteInsertedAuthSession(db, sessionId), 1);
  assert.deepEqual(calls, [
    { operation: "collection", name: "sessions" },
    { operation: "deleteOne", filter: { _id: sessionId } },
  ]);
});

test("assertHarnessSafety fails closed outside an explicitly allowed local non-owner run", () => {
  const privateOutput = fs.mkdtempSync(
    path.join(os.tmpdir(), "viventium-private-qa-"),
  );
  const args = parseArgs(requiredArgs(path.join(privateOutput, "evidence")));
  const selectedUser = { email: "qa@example.com", role: "USER" };
  const allowed = {
    VIVENTIUM_QA_ALLOW_LOCAL_JWT: "1",
    VIVENTIUM_QA_OWNER_EMAIL: "owner@example.com",
  };

  assert.equal(
    assertHarnessSafety({
      args,
      env: allowed,
      selectedUser,
      repoRoot: REPO_ROOT,
    }),
    true,
  );
  assert.throws(
    () =>
      assertHarnessSafety({ args, env: {}, selectedUser, repoRoot: REPO_ROOT }),
    /local_qa_jwt_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT/,
  );
  assert.throws(
    () =>
      assertHarnessSafety({
        args,
        env: { ...allowed, VIVENTIUM_QA_OWNER_EMAIL: "" },
        selectedUser,
        repoRoot: REPO_ROOT,
      }),
    /missing_owner_email_guard/,
  );
  assert.throws(
    () =>
      assertHarnessSafety({
        args,
        env: allowed,
        selectedUser: { email: "owner@example.com", role: "USER" },
        repoRoot: REPO_ROOT,
      }),
    /selected_owner_account_refused/,
  );
  assert.throws(
    () =>
      assertHarnessSafety({
        args,
        env: allowed,
        selectedUser: { email: "qa@example.com", role: "ADMIN" },
        repoRoot: REPO_ROOT,
      }),
    /selected_admin_account_refused/,
  );
  assert.throws(
    () =>
      assertHarnessSafety({
        args: { ...args, apiBase: "https://qa.example.com" },
        env: allowed,
        selectedUser,
        repoRoot: REPO_ROOT,
      }),
    /api_must_be_localhost/,
  );
  assert.throws(
    () =>
      assertHarnessSafety({
        args: { ...args, outputDir: path.join(REPO_ROOT, "output", "private") },
        env: allowed,
        selectedUser,
        repoRoot: REPO_ROOT,
      }),
    /private_output_must_be_outside_repo/,
  );
});

test("withQaRequestMetadata injects a unique run receipt without replacing the request", () => {
  const body = withQaRequestMetadata(
    { text: "synthetic prompt", endpoint: "agents" },
    "ANTI-003-2026-08-10T00-00-00Z-0123456789ab",
  );

  assert.deepEqual(body, {
    text: "synthetic prompt",
    endpoint: "agents",
    viventiumQaRun: true,
    viventiumQaRunId: "ANTI-003-2026-08-10T00-00-00Z-0123456789ab",
  });
});

test("findCorrelatedQaUserMessage falls back only to the unique submitted message and conversation", async () => {
  const exactMessage = {
    messageId: "submitted-user-message",
    parentMessageId: "submitted-parent",
    conversationId: "server-conversation",
    isCreatedByUser: true,
  };
  const queries = [];
  const makeDb = (candidates) => ({
    collection(name) {
      assert.equal(name, "messages");
      return {
        async findOne(query) {
          queries.push({ kind: "metadata", query });
          return null;
        },
        find(query) {
          queries.push({ kind: "exact", query });
          return {
            limit(limit) {
              assert.equal(limit, 2);
              return {
                async toArray() {
                  return candidates;
                },
              };
            },
          };
        },
      };
    },
  });
  const requestReceipt = {
    messageId: "submitted-user-message",
    parentMessageId: "submitted-parent",
    requestConversationId: "new",
    responseConversationId: "server-conversation",
  };
  const result = await findCorrelatedQaUserMessage({
    db: makeDb([exactMessage]),
    userId: "qa-user",
    qaRunId: "ANTI-SYNTHETIC-run",
    requestReceipt,
  });
  assert.deepEqual(result, {
    message: exactMessage,
    source: "exact_submitted_message",
  });
  assert.deepEqual(queries.at(-1), {
    kind: "exact",
    query: {
      user: "qa-user",
      messageId: "submitted-user-message",
      isCreatedByUser: true,
    },
  });

  await assert.rejects(
    () =>
      findCorrelatedQaUserMessage({
        db: makeDb([exactMessage, { ...exactMessage, _id: "duplicate" }]),
        userId: "qa-user",
        qaRunId: "ANTI-SYNTHETIC-run",
        requestReceipt,
      }),
    /exact_submitted_message_correlation_ambiguous/,
  );
});

test("summarizeMessages preserves DB order and reports each part terminal and unfinished state", () => {
  const summary = summarizeMessages([
    {
      messageId: "m-user",
      isCreatedByUser: true,
      createdAt: new Date("2026-08-10T10:00:00.000Z"),
      unfinished: false,
      content: [{ type: "text", text: "private prompt" }],
    },
    {
      messageId: "m-main",
      isCreatedByUser: false,
      createdAt: new Date("2026-08-10T10:00:01.000Z"),
      unfinished: true,
      content: [
        { type: "text", text: "private answer" },
        {
          type: "cortex_call",
          cortex_name: "Reality Check",
          status: "running",
        },
        { type: "cortex_insight", cortex_name: "Red Team", status: "complete" },
      ],
    },
  ]);

  assert.deepEqual(
    summary.map(({ messageOrder, role, unfinished }) => ({
      messageOrder,
      role,
      unfinished,
    })),
    [
      { messageOrder: 0, role: "user", unfinished: false },
      { messageOrder: 1, role: "assistant", unfinished: true },
    ],
  );
  assert.deepEqual(
    summary[1].parts.map(
      ({ partOrder, type, status, terminal, unfinished }) => ({
        partOrder,
        type,
        status,
        terminal,
        unfinished,
      }),
    ),
    [
      {
        partOrder: 0,
        type: "text",
        status: "",
        terminal: false,
        unfinished: true,
      },
      {
        partOrder: 1,
        type: "cortex_call",
        status: "running",
        terminal: false,
        unfinished: true,
      },
      {
        partOrder: 2,
        type: "cortex_insight",
        status: "complete",
        terminal: true,
        unfinished: false,
      },
    ],
  );
  assert.deepEqual(summary[1].agentNames, ["Reality Check", "Red Team"]);
});

test("analyzePersistedTurn proves structural consultant order and selected-Agent Main-last", () => {
  const conversation = { agent_id: "main" };
  const complete = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation,
    messages: [
      {
        isCreatedByUser: false,
        unfinished: false,
        content: [
          { type: "text", text: "Initial reasoning", agentId: "main" },
          { type: "text", text: "Reality evidence", agentId: "reality" },
          { type: "text", text: "Challenge", agentId: "red" },
          { type: "text", text: "Final Main synthesis", agentId: "main" },
        ],
      },
    ],
  });

  assert.deepEqual(complete.graphAgentOrder, [
    "main",
    "reality",
    "red",
    "main",
  ]);
  assert.equal(complete.finalText, "Final Main synthesis");
  assert.equal(complete.finalAuthorAgentId, "main");
  assert.equal(complete.hasHandoff, true);
  assert.equal(complete.mainLast, true);
  assert.equal(complete.conversationAgentMatches, true);

  const broken = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation,
    messages: [
      {
        isCreatedByUser: false,
        unfinished: false,
        content: [
          { type: "text", text: "Initial reasoning", agentId: "main" },
          { type: "text", text: "Consultant spoke last", agentId: "red" },
        ],
      },
    ],
  });
  assert.equal(broken.finalAuthorAgentId, "red");
  assert.equal(broken.mainLast, false);
});

test("analyzePersistedTurn attributes a top-level Phase B follow-up to Main after structured handoffs", () => {
  const complete = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation: { agent_id: "main" },
    messages: [
      {
        messageId: "user-turn",
        isCreatedByUser: true,
        text: "private synthetic prompt",
      },
      {
        messageId: "foreground-answer",
        parentMessageId: "user-turn",
        isCreatedByUser: false,
        agent_id: "main",
        content: [
          { type: "text", text: "Initial Main reasoning", agentId: "main" },
          { type: "text", text: "Reality evidence", agentId: "reality" },
          { type: "text", text: "Red challenge", agentId: "red" },
        ],
      },
      {
        messageId: "phase-b-follow-up",
        parentMessageId: "foreground-answer",
        isCreatedByUser: false,
        agent_id: "main",
        text: "New useful Phase B insight from Main",
      },
    ],
  });

  assert.deepEqual(complete.graphAgentOrder, [
    "main",
    "reality",
    "red",
    "main",
  ]);
  assert.equal(complete.directAssistantMessageCount, 2);
  assert.equal(complete.finalText, "New useful Phase B insight from Main");
  assert.equal(complete.finalAuthorAgentId, "main");
  assert.equal(complete.mainLast, true);
});

test("analyzePersistedTurn resets inferred authorship to canonical message agent at each boundary", () => {
  const analysis = analyzePersistedTurn({
    selectedAgentId: "agent-main",
    originatingUserMessageId: "user-turn",
    conversation: { agent_id: "agent-main" },
    messages: [
      { messageId: "user-turn", isCreatedByUser: true },
      {
        messageId: "main-message",
        parentMessageId: "user-turn",
        isCreatedByUser: false,
        agent_id: "agent-main",
        content: [{ type: "text", text: "Main first." }],
      },
      {
        messageId: "red-message",
        parentMessageId: "main-message",
        isCreatedByUser: false,
        agent_id: "agent-red",
        content: [
          { type: "text", text: "Red spoke last without a part annotation." },
        ],
      },
    ],
  });

  assert.equal(analysis.finalAuthorAgentId, "agent-red");
  assert.equal(analysis.mainLast, false);
  assert.deepEqual(analysis.graphAgentOrder, ["agent-main", "agent-red"]);
});

test("analyzePersistedTurn follows the exact parent dependency when placeholder creation predates user persistence", () => {
  const complete = analyzePersistedTurn({
    selectedAgentId: "main",
    originatingUserMessageId: "submitted-user-message",
    conversation: { agent_id: "main" },
    messages: [
      {
        messageId: "assistant-placeholder-updated-in-place",
        parentMessageId: "submitted-user-message",
        isCreatedByUser: false,
        agent_id: "main",
        createdAt: new Date("2026-08-10T12:00:00.000Z"),
        content: [{ type: "text", text: "Final Main answer", agentId: "main" }],
      },
      {
        messageId: "submitted-user-message",
        isCreatedByUser: true,
        createdAt: new Date("2026-08-10T12:00:00.170Z"),
        text: "private synthetic prompt",
      },
    ],
  });

  assert.equal(complete.directAssistantMessageCount, 1);
  assert.equal(complete.finalText, "Final Main answer");
  assert.equal(complete.mainLast, true);
});

test("analyzePersistedTurn rejects a transfer target that never authors or terminates", () => {
  const escapedFailure = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation: { agent_id: "main" },
    messages: [
      {
        isCreatedByUser: false,
        unfinished: false,
        content: [
          { type: "text", text: "Main text before transfer", agentId: "main" },
          {
            type: "tool_call",
            agentId: "main",
            tool_call: { id: "to-red", name: "lc_transfer_to_red", args: "{}" },
          },
        ],
      },
    ],
  });

  assert.deepEqual(escapedFailure.graphAgentOrder, ["main", "red"]);
  assert.equal(escapedFailure.transferCount, 1);
  assert.equal(escapedFailure.incompleteTransferCount, 1);
  assert.equal(escapedFailure.allTransfersResolved, false);
  assert.equal(escapedFailure.finalMainAfterLastTransfer, false);
  assert.equal(escapedFailure.mainLast, false);
});

test("analyzePersistedTurn requires target output, return, and later Main text", () => {
  const complete = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation: { agent_id: "main" },
    messages: [
      {
        isCreatedByUser: false,
        unfinished: false,
        content: [
          { type: "text", text: "Main text before transfer", agentId: "main" },
          {
            type: "tool_call",
            agentId: "main",
            tool_call: { id: "to-red", name: "lc_transfer_to_red", args: "{}" },
          },
          { type: "text", text: "Red challenge", agentId: "red" },
          {
            type: "tool_call",
            agentId: "red",
            tool_call: {
              id: "to-main",
              name: "lc_transfer_to_main",
              args: "{}",
            },
          },
          { type: "text", text: "Main final after Red", agentId: "main" },
        ],
      },
    ],
  });

  assert.deepEqual(complete.graphAgentOrder, ["main", "red", "main"]);
  assert.equal(complete.transferCount, 2);
  assert.equal(complete.incompleteTransferCount, 0);
  assert.equal(complete.allTransfersResolved, true);
  assert.equal(complete.finalMainAfterLastTransfer, true);
  assert.equal(complete.finalText, "Main final after Red");
  assert.equal(complete.mainLast, true);
});

test("analyzePersistedTurn reads consolidated transfer outputs structurally", () => {
  const complete = analyzePersistedTurn({
    selectedAgentId: "main",
    conversation: { agent_id: "main" },
    messages: [
      {
        isCreatedByUser: false,
        unfinished: false,
        agent_id: "main",
        content: [
          {
            type: "tool_call",
            tool_call: {
              id: "to-red",
              name: "lc_transfer_to_red",
              args: "{}",
              output:
                '--- Transfer ---\n\nRed: {"type":"text","text":"Consolidated Red challenge"}\n\n--- End ---',
            },
          },
          {
            type: "tool_call",
            tool_call: {
              id: "to-main",
              name: "lc_transfer_to_main",
              args: "{}",
              output:
                '--- Transfer ---\n\nMain: {"type":"text","text":"Consolidated Main final"}\n\n--- End ---',
            },
          },
        ],
      },
    ],
  });

  assert.deepEqual(complete.graphAgentOrder, ["main", "red", "main"]);
  assert.equal(complete.allTransfersResolved, true);
  assert.equal(complete.finalText, "Consolidated Main final");
  assert.equal(complete.finalAuthorAgentId, "main");
  assert.equal(complete.mainLast, true);
});

test("validateReopenPersistedConversation requires QA ownership, selected agent, and a terminal causal lineage", () => {
  const messages = [
    {
      user: "qa-user",
      messageId: "user-turn",
      isCreatedByUser: true,
      unfinished: false,
      text: "private synthetic prompt",
    },
    {
      user: "qa-user",
      messageId: "main-answer",
      parentMessageId: "user-turn",
      isCreatedByUser: false,
      unfinished: false,
      agent_id: "main-agent",
      content: [{ type: "text", text: "Main final", agentId: "main-agent" }],
    },
  ];
  const validated = validateReopenPersistedConversation({
    conversation: {
      user: "qa-user",
      conversationId: "private-conversation",
      agent_id: "main-agent",
    },
    messages,
    userId: "qa-user",
    selectedAgentId: "main-agent",
  });

  assert.equal(validated.turnTerminal, true);
  assert.equal(validated.originatingUserMessageId, "user-turn");
  assert.equal(validated.turnAnalysis.originatingUserMessageMatched, true);
  assert.equal(validated.turnAnalysis.mainLast, true);

  assert.throws(
    () =>
      validateReopenPersistedConversation({
        conversation: {
          user: "foreign-user",
          conversationId: "private-conversation",
          agent_id: "main-agent",
        },
        messages,
        userId: "qa-user",
        selectedAgentId: "main-agent",
      }),
    /reopen_conversation_not_owned_by_selected_qa_user/,
  );
  assert.throws(
    () =>
      validateReopenPersistedConversation({
        conversation: {
          user: "qa-user",
          conversationId: "private-conversation",
          agent_id: "foreign-agent",
        },
        messages,
        userId: "qa-user",
        selectedAgentId: "main-agent",
      }),
    /reopen_conversation_agent_mismatch/,
  );
  assert.throws(
    () =>
      validateReopenPersistedConversation({
        conversation: {
          user: "qa-user",
          conversationId: "private-conversation",
          agent_id: "main-agent",
        },
        messages: messages.map((message) =>
          message.isCreatedByUser ? message : { ...message, unfinished: true },
        ),
        userId: "qa-user",
        selectedAgentId: "main-agent",
      }),
    /reopen_conversation_turn_not_terminal/,
  );
});

test("evaluateAcceptance rejects duplicate authoring, blank UI, missing detail persistence, or non-Main final", () => {
  const passing = {
    requestInjectionCount: 1,
    agentApiAccessPass: true,
    selectedAgentVisibleBefore: true,
    expectedConversationPathVisible: true,
    expandedAnswerVisible: true,
    refreshAnswerVisible: true,
    detailExpansionPass: true,
    detailRefreshPass: true,
    visibleProgressSettlementPass: true,
    databaseTerminal: true,
    conversationAgentMatches: true,
    allTransfersResolved: true,
    finalMainAfterLastTransfer: true,
    mainLast: true,
    conversationPreserved: true,
    screenshotCount: 3,
    sessionDeleteCount: 1,
    error: "",
  };
  assert.deepEqual(evaluateAcceptance(passing), { pass: true, failures: [] });
  assert.deepEqual(
    evaluateAcceptance({
      ...passing,
      expectedScheduleLifecycleRequired: true,
      expectedScheduleLifecyclePass: false,
    }),
    {
      pass: false,
      failures: ["expected_schedule_lifecycle_not_clean"],
    },
  );
  assert.deepEqual(
    evaluateAcceptance({
      ...passing,
      requestInjectionCount: 2,
      expandedAnswerVisible: false,
      detailRefreshPass: false,
      visibleProgressSettlementPass: false,
      allTransfersResolved: false,
      finalMainAfterLastTransfer: false,
      mainLast: false,
      conversationPreserved: false,
    }),
    {
      pass: false,
      failures: [
        "agent_chat_post_count_not_one",
        "expanded_answer_not_visible",
        "expanded_detail_not_durable",
        "visible_progress_not_settled",
        "transfer_target_unresolved",
        "main_answer_not_after_last_transfer",
        "selected_agent_not_final_author",
        "conversation_not_proven_preserved",
      ],
    },
  );
});

test("submit conversation preservation requires the same owned terminal lineage before refresh, after refresh, and after cleanup", () => {
  const stableState = {
    identityVerified: true,
    turnTerminal: true,
    originatingUserMessageId: "private-originating-message",
    messageSummary: [
      { messageIdHash: "user-hash", terminal: true, parts: [] },
      { messageIdHash: "assistant-hash", terminal: true, parts: [] },
    ],
    turnAnalysis: {
      finalTextHash: "final-hash",
      finalAuthorAgentIdHash: "main-agent-hash",
      graphAgentOrder: ["main-agent"],
      allTransfersResolved: true,
      finalMainAfterLastTransfer: true,
      conversationAgentMatches: true,
      originatingUserMessageMatched: true,
      mainLast: true,
    },
  };
  assert.equal(
    deriveSubmitConversationPreserved({
      requestInjectionCount: 1,
      beforeRefreshState: stableState,
      afterRefreshState: structuredClone(stableState),
      postCleanupState: structuredClone(stableState),
    }),
    true,
  );
  assert.equal(
    deriveSubmitConversationPreserved({
      requestInjectionCount: 1,
      beforeRefreshState: stableState,
      afterRefreshState: stableState,
      postCleanupState: null,
    }),
    false,
  );
  assert.equal(
    deriveSubmitConversationPreserved({
      requestInjectionCount: 1,
      beforeRefreshState: stableState,
      afterRefreshState: stableState,
      postCleanupState: {
        ...structuredClone(stableState),
        identityVerified: false,
      },
    }),
    false,
  );
  assert.equal(
    deriveSubmitConversationPreserved({
      requestInjectionCount: 1,
      beforeRefreshState: stableState,
      afterRefreshState: stableState,
      postCleanupState: {
        ...structuredClone(stableState),
        turnAnalysis: {
          ...stableState.turnAnalysis,
          finalTextHash: "changed-final-hash",
        },
      },
    }),
    false,
  );
});

test("evaluateReopenAcceptance requires zero agent chat POSTs and durable UI plus DB Main-last lineage", () => {
  const passing = {
    agentChatPostCount: 0,
    agentApiAccessPass: true,
    expectedConversationPathVisible: true,
    expandedAnswerVisible: true,
    refreshAnswerVisible: true,
    detailExpansionPass: true,
    detailRefreshPass: true,
    visibleProgressSettlementPass: true,
    databaseTerminal: true,
    conversationAgentMatches: true,
    originatingUserMessageMatched: true,
    allTransfersResolved: true,
    finalMainAfterLastTransfer: true,
    mainLast: true,
    databaseLineageStable: true,
    conversationPreserved: true,
    screenshotCount: 2,
    sessionDeleteCount: 1,
    error: "",
  };
  assert.deepEqual(evaluateReopenAcceptance(passing), {
    pass: true,
    failures: [],
  });
  assert.deepEqual(
    evaluateReopenAcceptance({
      ...passing,
      agentChatPostCount: 1,
      expectedConversationPathVisible: false,
      detailRefreshPass: false,
      visibleProgressSettlementPass: false,
      mainLast: false,
      databaseLineageStable: false,
      conversationPreserved: false,
    }),
    {
      pass: false,
      failures: [
        "reopen_agent_chat_post_detected",
        "expected_conversation_path_not_visible",
        "expanded_detail_not_durable",
        "visible_progress_not_settled",
        "selected_agent_not_final_author",
        "database_lineage_changed_during_reopen",
        "conversation_not_proven_preserved",
      ],
    },
  );
  assert.deepEqual(
    evaluateReopenAcceptance({
      ...passing,
      databaseLineageStable: null,
      conversationPreserved: false,
    }),
    {
      pass: false,
      failures: [
        "database_lineage_not_revalidated_after_reopen",
        "conversation_not_proven_preserved",
      ],
    },
  );
});

test("conversation preservation is derived only from zero Agent POSTs and stable database lineage", () => {
  assert.equal(
    deriveConversationPreserved({
      agentChatPostCount: 0,
      databaseLineageStable: true,
    }),
    true,
  );
  assert.equal(
    deriveConversationPreserved({
      agentChatPostCount: 1,
      databaseLineageStable: true,
    }),
    false,
  );
  assert.equal(
    deriveConversationPreserved({
      agentChatPostCount: 0,
      databaseLineageStable: false,
    }),
    false,
  );
});

test("reopen lineage revalidation reads a fresh terminal state and distinguishes missing validation from measured change", async () => {
  const beforeState = {
    originatingUserMessageId: "synthetic-originating-message",
    messageSummary: [
      {
        messageIdHash: "synthetic-message-hash",
        role: "assistant",
        terminal: true,
        unfinished: false,
        parts: [],
      },
    ],
    turnAnalysis: {
      finalTextHash: "synthetic-final-hash",
      finalAuthorAgentIdHash: "synthetic-main-hash",
      graphAgentOrder: ["agent-main"],
      allTransfersResolved: true,
      finalMainAfterLastTransfer: true,
      mainLast: true,
    },
  };
  let readCount = 0;
  const stable = await revalidateReopenLineage({
    beforeState,
    loadAfterState: async () => {
      readCount += 1;
      return structuredClone(beforeState);
    },
  });
  assert.equal(readCount, 1);
  assert.equal(stable.lineageStable, true);
  assert.deepEqual(stable.afterState, beforeState);

  const changed = await revalidateReopenLineage({
    beforeState,
    loadAfterState: async () => ({
      ...structuredClone(beforeState),
      turnAnalysis: {
        ...beforeState.turnAnalysis,
        finalTextHash: "changed-synthetic-final-hash",
      },
    }),
  });
  assert.equal(changed.lineageStable, false);

  const notRevalidated = await revalidateReopenLineage({
    beforeState: null,
    loadAfterState: async () => {
      throw new Error("must_not_read_without_a_baseline");
    },
  });
  assert.deepEqual(notRevalidated, {
    afterState: null,
    lineageStable: null,
  });
});

test("buildReopenUiReceipt requires the same expanded handoff detail and answer after refresh", () => {
  const ui = buildReopenUiReceipt({
    agentApiAccess: { pass: true },
    backgroundSettledBeforeExpansion: true,
    backgroundSettledAfterRefresh: true,
    turnAnalysis: { hasHandoff: true },
    expandedReceipt: { pass: true, detailApplicable: true },
    expanded: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred to synthetic consultant"],
      expandedCardLabels: ["Synthetic consultant completed"],
      handoffDetailTexts: ["Private detail"],
      detailFingerprint: "same-private-fingerprint",
    },
    refreshExpandedReceipt: { pass: true, detailApplicable: true },
    afterRefresh: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred to synthetic consultant"],
      expandedCardLabels: ["Synthetic consultant completed"],
      handoffDetailTexts: ["Private detail"],
      detailFingerprint: "same-private-fingerprint",
    },
  });

  assert.deepEqual(ui, {
    agentApiAccessPass: true,
    expectedConversationPathVisible: true,
    expandedAnswerVisible: true,
    refreshAnswerVisible: true,
    detailExpansionPass: true,
    detailRefreshPass: true,
    visibleProgressSettlementPass: true,
  });
  assert.equal(
    buildReopenUiReceipt({
      agentApiAccess: { pass: true },
      backgroundSettledBeforeExpansion: true,
      backgroundSettledAfterRefresh: true,
      turnAnalysis: { hasHandoff: true },
      expandedReceipt: { pass: true, detailApplicable: true },
      expanded: {
        expectedConversationPath: true,
        answerVisible: true,
        handoffLabels: ["Transferred"],
        expandedCardLabels: ["Completed"],
        handoffDetailTexts: [],
        detailFingerprint: "before",
      },
      refreshExpandedReceipt: { pass: true, detailApplicable: true },
      afterRefresh: {
        expectedConversationPath: true,
        answerVisible: true,
        handoffLabels: [],
        expandedCardLabels: ["Completed"],
        handoffDetailTexts: [],
        detailFingerprint: "after",
      },
    }).detailRefreshPass,
    false,
  );

  const labelOnlyHandoff = buildReopenUiReceipt({
    agentApiAccess: { pass: true },
    backgroundSettledBeforeExpansion: true,
    backgroundSettledAfterRefresh: true,
    turnAnalysis: { hasHandoff: true },
    expandedReceipt: { pass: true, detailApplicable: false },
    expanded: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred"],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
    refreshExpandedReceipt: { pass: true, detailApplicable: false },
    afterRefresh: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred"],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
  });
  assert.equal(labelOnlyHandoff.detailExpansionPass, false);
  assert.equal(labelOnlyHandoff.detailRefreshPass, false);

  const visibleOnlyLabelHandoff = buildReopenUiReceipt({
    agentApiAccess: { pass: true },
    backgroundSettledBeforeExpansion: true,
    backgroundSettledAfterRefresh: true,
    turnAnalysis: { hasHandoff: false },
    expandedReceipt: { pass: true, detailApplicable: false },
    expanded: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred"],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
    refreshExpandedReceipt: { pass: true, detailApplicable: false },
    afterRefresh: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: ["Transferred"],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
  });
  assert.equal(visibleOnlyLabelHandoff.detailExpansionPass, false);
  assert.equal(visibleOnlyLabelHandoff.detailRefreshPass, false);

  const noHandoff = buildReopenUiReceipt({
    agentApiAccess: { pass: true },
    backgroundSettledBeforeExpansion: true,
    backgroundSettledAfterRefresh: true,
    turnAnalysis: { hasHandoff: false },
    expandedReceipt: { pass: true, detailApplicable: false },
    expanded: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: [],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
    refreshExpandedReceipt: { pass: true, detailApplicable: false },
    afterRefresh: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: [],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      detailFingerprint: "empty-detail",
    },
  });
  assert.equal(noHandoff.detailExpansionPass, true);
  assert.equal(noHandoff.detailRefreshPass, true);
  assert.equal(noHandoff.visibleProgressSettlementPass, true);

  const durableHarnessActivity = buildReopenUiReceipt({
    agentApiAccess: { pass: true },
    backgroundSettledBeforeExpansion: true,
    backgroundSettledAfterRefresh: true,
    turnAnalysis: { hasHandoff: false },
    expandedReceipt: { pass: true, detailApplicable: true },
    expanded: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: [],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      harnessActivityDetailTexts: ["Connected tool completed."],
      detailFingerprint: "same-activity-fingerprint",
    },
    refreshExpandedReceipt: { pass: true, detailApplicable: true },
    afterRefresh: {
      expectedConversationPath: true,
      answerVisible: true,
      handoffLabels: [],
      expandedCardLabels: [],
      handoffDetailTexts: [],
      harnessActivityDetailTexts: ["Connected tool completed."],
      detailFingerprint: "same-activity-fingerprint",
    },
  });
  assert.equal(durableHarnessActivity.detailExpansionPass, true);
  assert.equal(durableHarnessActivity.detailRefreshPass, true);

  assert.equal(
    buildReopenUiReceipt({
      agentApiAccess: { pass: true },
      backgroundSettledBeforeExpansion: true,
      backgroundSettledAfterRefresh: false,
      turnAnalysis: { hasHandoff: false },
      expandedReceipt: { pass: true, detailApplicable: false },
      expanded: {
        expectedConversationPath: true,
        answerVisible: true,
        handoffLabels: [],
        expandedCardLabels: [],
        handoffDetailTexts: [],
        detailFingerprint: "empty-detail",
      },
      refreshExpandedReceipt: { pass: true, detailApplicable: false },
      afterRefresh: {
        expectedConversationPath: true,
        answerVisible: true,
        handoffLabels: [],
        expandedCardLabels: [],
        handoffDetailTexts: [],
        detailFingerprint: "empty-detail",
      },
    }).visibleProgressSettlementPass,
    false,
  );
});

test("expandVisibleDetails opens every durable harness activity and requires nonempty detail", async () => {
  let closed = 2;
  let open = 0;
  let detail = 0;
  const page = {
    waitForTimeout: async () => {},
    locator: (selector) => ({
      count: async () => {
        if (
          selector.includes("harness-activity") &&
          selector.includes(":not([open])")
        ) {
          return closed;
        }
        if (
          selector.includes("harness-activity") &&
          selector.includes("ol > li")
        ) {
          return detail;
        }
        if (
          selector.includes("harness-activity") &&
          selector.includes("[open]")
        ) {
          return open;
        }
        return 0;
      },
      nth: () => ({
        click: async () => {},
        locator: () => ({
          click: async () => {
            closed -= 1;
            open += 1;
            detail += 1;
          },
        }),
      }),
    }),
  };

  const receipt = await expandVisibleDetails(page);

  assert.equal(receipt.detailApplicable, true);
  assert.equal(receipt.harnessActivityExpandableCount, 2);
  assert.equal(receipt.harnessActivityClickedCount, 2);
  assert.equal(receipt.harnessActivityExpandedCount, 2);
  assert.equal(receipt.harnessActivityDetailCount, 2);
  assert.equal(receipt.pass, true);
});

test("reopenLineageFingerprint changes when causal Main-last evidence changes", () => {
  const base = {
    originatingUserMessageId: "private-user-message",
    messageSummary: [
      { messageIdHash: "user-hash", terminal: true, parts: [] },
      { messageIdHash: "main-hash", terminal: true, parts: [] },
    ],
    turnAnalysis: {
      finalTextHash: "final-hash",
      finalAuthorAgentIdHash: "main-agent-hash",
      graphAgentOrder: ["main-agent", "red-agent", "main-agent"],
      allTransfersResolved: true,
      finalMainAfterLastTransfer: true,
      mainLast: true,
    },
  };
  const fingerprint = reopenLineageFingerprint(base);
  assert.equal(fingerprint.length, 32);
  assert.equal(reopenLineageFingerprint({ ...base }), fingerprint);
  assert.notEqual(
    reopenLineageFingerprint({
      ...base,
      turnAnalysis: { ...base.turnAnalysis, mainLast: false },
    }),
    fingerprint,
  );
});

test("buildPublicSummary emits hashes and counts but no raw private values", () => {
  const summary = buildPublicSummary({
    args: {
      caseId: "ANTI-SYNTHETIC",
      qaRunId: "ANTI-SYNTHETIC-run-private",
      qaEmail: "qa-private@example.com",
      agentId: "agent-private",
      prompt: "raw private synthetic prompt",
      outputDir: "/private/evidence/run",
    },
    conversationId: "conversation-private",
    visibleAgentNames: ["Reality Check", "Red Team"],
    messageSummary: [
      { unfinished: false, parts: [{ type: "text", terminal: true }] },
    ],
    turnTerminal: true,
    conversationPreserved: true,
    expectedScheduleLifecycle: {
      required: true,
      pass: true,
      schedulingHealthCheckCount: 2,
      schedulingHealthSuccessCount: 2,
      schedulingPreflightHealthVerified: true,
      schedulingCleanupHealthVerified: true,
      schedulingDbPathSha256: "a".repeat(64),
    },
  });
  const serialized = JSON.stringify(summary);

  assert.equal(summary.caseId, "ANTI-SYNTHETIC");
  assert.equal(summary.visibleAgentCount, 2);
  assert.equal(summary.turnTerminal, true);
  assert.equal(summary.conversationPreserved, true);
  assert.equal(summary.expectedScheduleHealthCheckCount, 2);
  assert.equal(summary.expectedScheduleHealthSuccessCount, 2);
  assert.equal(summary.expectedSchedulePreflightHealthVerified, true);
  assert.equal(summary.expectedScheduleCleanupHealthVerified, true);
  assert.equal(summary.expectedScheduleDbPathSha256, "a".repeat(64));
  for (const forbidden of [
    "qa-private@example.com",
    "agent-private",
    "raw private synthetic prompt",
    "conversation-private",
    "/private/evidence/run",
  ]) {
    assert.equal(serialized.includes(forbidden), false);
  }
});

test("first visible paint correlation fails closed unless the DOM candidate is the exact Main descendant", () => {
  const receipt = {
    interactionStartedAtMs: 1_000,
    paintedAtMs: 1_145.4,
    userMessageId: "private-user-id",
    assistantMessageId: "private-main-id",
    assistantPartId: "content:0",
    assistantPartAgentId: "agent-main",
  };
  const messages = [
    {
      messageId: "private-user-id",
      isCreatedByUser: true,
    },
    {
      messageId: "private-main-id",
      parentMessageId: "private-user-id",
      isCreatedByUser: false,
      agent_id: "agent-main",
      content: [{ type: "text", text: "Main answer.", agentId: "agent-main" }],
    },
  ];

  const correlated = correlateFirstVisibleMainPaint({
    receipt,
    messages,
    originatingUserMessageId: "private-user-id",
    selectedAgentId: "agent-main",
  });
  assert.deepEqual(correlated.publicMetrics, {
    firstVisibleMainPaintObserved: true,
    firstVisibleMainPaintCorrelated: true,
    firstVisibleMainPaintMs: 145,
    firstVisibleMainPaintCorrelationCount: 1,
  });
  assert.equal(
    correlateFirstVisibleMainPaint({
      receipt,
      messages,
      originatingUserMessageId: "a-different-user-id",
      selectedAgentId: "agent-main",
    }).publicMetrics.firstVisibleMainPaintCorrelated,
    false,
  );
  assert.equal(
    correlateFirstVisibleMainPaint({
      receipt,
      messages: [
        messages[0],
        {
          ...messages[1],
          agent_id: "agent-not-main",
          content: [
            {
              ...messages[1].content[0],
              agentId: "agent-not-main",
            },
          ],
        },
      ],
      originatingUserMessageId: "private-user-id",
      selectedAgentId: "agent-main",
    }).publicMetrics.firstVisibleMainPaintCorrelated,
    false,
  );
});

test("first visible paint correlation attributes the exact persisted text part, not merely its message", () => {
  const messages = [
    {
      messageId: "private-user-id",
      isCreatedByUser: true,
    },
    {
      messageId: "private-shared-assistant-id",
      parentMessageId: "private-user-id",
      isCreatedByUser: false,
      agent_id: "agent-main",
      content: [
        {
          type: "text",
          text: "Consultant answer first.",
          agentId: "agent-consultant",
        },
        {
          type: "text",
          text: "Main synthesis second.",
          agentId: "agent-main",
        },
      ],
    },
  ];
  const baseReceipt = {
    interactionStartedAtMs: 1_000,
    paintedAtMs: 1_125,
    userMessageId: "private-user-id",
    assistantMessageId: "private-shared-assistant-id",
  };

  assert.equal(
    correlateFirstVisibleMainPaint({
      receipt: {
        ...baseReceipt,
        assistantPartId: "content:0",
        assistantPartAgentId: "agent-consultant",
      },
      messages,
      originatingUserMessageId: "private-user-id",
      selectedAgentId: "agent-main",
    }).publicMetrics.firstVisibleMainPaintCorrelated,
    false,
  );
  assert.equal(
    correlateFirstVisibleMainPaint({
      receipt: {
        ...baseReceipt,
        assistantPartId: "content:1",
        assistantPartAgentId: "agent-main",
      },
      messages,
      originatingUserMessageId: "private-user-id",
      selectedAgentId: "agent-main",
    }).publicMetrics.firstVisibleMainPaintCorrelated,
    true,
  );
});

test("first visible paint correlation cannot confuse sanitizer-removed Main text with later consultant text", () => {
  const result = correlateFirstVisibleMainPaint({
    receipt: {
      interactionStartedAtMs: 1_000,
      paintedAtMs: 1_125,
      userMessageId: "private-user-id",
      assistantMessageId: "private-shared-assistant-id",
      assistantPartId: "content:1",
      assistantPartAgentId: "agent-consultant",
    },
    messages: [
      { messageId: "private-user-id", isCreatedByUser: true },
      {
        messageId: "private-shared-assistant-id",
        parentMessageId: "private-user-id",
        isCreatedByUser: false,
        agent_id: "agent-main",
        content: [
          {
            type: "text",
            text: 'Tool: workspace_status {"workspace_id":"wrk_public_safe"}',
            agentId: "agent-main",
          },
          {
            type: "text",
            text: "Consultant answer.",
            agentId: "agent-consultant",
          },
        ],
      },
    ],
    originatingUserMessageId: "private-user-id",
    selectedAgentId: "agent-main",
  });

  assert.equal(result.publicMetrics.firstVisibleMainPaintObserved, true);
  assert.equal(result.publicMetrics.firstVisibleMainPaintCorrelated, false);
  assert.equal(result.publicMetrics.firstVisibleMainPaintMs, null);
});

test("first visible paint correlation validates every source part in an adjacent Main text block", () => {
  const result = correlateFirstVisibleMainPaint({
    receipt: {
      interactionStartedAtMs: 1_000,
      paintedAtMs: 1_111,
      userMessageId: "private-user-id",
      assistantMessageId: "private-main-id",
      assistantPartId: "content:0,1",
      assistantPartAgentId: "agent-main",
    },
    messages: [
      { messageId: "private-user-id", isCreatedByUser: true },
      {
        messageId: "private-main-id",
        parentMessageId: "private-user-id",
        isCreatedByUser: false,
        agent_id: "agent-main",
        content: [
          { type: "text", text: "Main ", agentId: "agent-main" },
          { type: "text", text: "answer.", agentId: "agent-main" },
        ],
      },
    ],
    originatingUserMessageId: "private-user-id",
    selectedAgentId: "agent-main",
  });

  assert.equal(result.publicMetrics.firstVisibleMainPaintCorrelated, true);
  assert.equal(result.publicMetrics.firstVisibleMainPaintMs, 111);
});

test("first visible paint correlation follows a persisted stream identity after earlier activity insertion", () => {
  const result = correlateFirstVisibleMainPaint({
    receipt: {
      interactionStartedAtMs: 1_000,
      paintedAtMs: 1_109,
      userMessageId: "private-user-id",
      assistantMessageId: "private-main-id",
      assistantPartId: "content:1",
      assistantPartAgentId: "agent-main",
    },
    messages: [
      { messageId: "private-user-id", isCreatedByUser: true },
      {
        messageId: "private-main-id",
        parentMessageId: "private-user-id",
        isCreatedByUser: false,
        agent_id: "agent-main",
        content: [
          { type: "cortex_insight" },
          { type: "harness_activity" },
          {
            type: "text",
            text: "Main answer.",
            agentId: "agent-main",
            viventium_render_part_id: "content:1",
          },
        ],
      },
    ],
    originatingUserMessageId: "private-user-id",
    selectedAgentId: "agent-main",
  });

  assert.equal(result.publicMetrics.firstVisibleMainPaintCorrelated, true);
  assert.equal(result.publicMetrics.firstVisibleMainPaintMs, 109);
});

test("paint observer stays armed through consultant-first content and records the later Main identity", async () => {
  const originalWindow = global.window;
  const originalDocument = global.document;
  const originalMutationObserver = global.MutationObserver;
  const originalRequestAnimationFrame = global.requestAnimationFrame;
  const originalPerformance = global.performance;
  const assistantTextParts = [];
  let observerCallback;
  const visiblePart = (agentId, partId, text) => ({
    dataset: {
      viventiumAgentId: agentId,
      viventiumPartId: partId,
    },
    textContent: text,
    getBoundingClientRect: () => ({ width: 100, height: 20 }),
  });
  const userContent = visiblePart("", "", "Synthetic prompt");
  const userMessage = {
    id: "private-user-id",
    querySelector: (selector) => (selector === ".user-turn" ? {} : null),
    querySelectorAll: (selector) =>
      selector === ".message-content" ? [userContent] : [],
  };
  const assistantMessage = {
    id: "private-assistant-id",
    querySelector: (selector) => (selector === ".agent-turn" ? {} : null),
    querySelectorAll: (selector) =>
      selector === ".message-content" ? assistantTextParts : [],
  };

  try {
    global.window = {
      getComputedStyle: () => ({
        display: "block",
        visibility: "visible",
        opacity: "1",
      }),
    };
    global.document = {
      body: {},
      querySelectorAll: (selector) =>
        selector === ".message-render" ? [userMessage, assistantMessage] : [],
    };
    global.MutationObserver = class {
      constructor(callback) {
        observerCallback = callback;
      }
      observe() {}
      disconnect() {}
    };
    global.requestAnimationFrame = (callback) => callback();
    global.performance = { timeOrigin: 1_000, now: () => 25 };
    const page = {
      evaluate: async (callback, ...args) => callback(...args),
    };

    assistantTextParts.push(
      visiblePart("agent-consultant", "content:0", "Consultant answer first."),
    );
    await armFirstVisibleMainPaintObserver(
      page,
      "Synthetic prompt",
      "agent-main",
    );
    assert.equal(
      global.window.__viventiumFirstVisibleMainPaint.paintedAtMs,
      null,
    );

    assistantTextParts.push(
      visiblePart("agent-main", "content:2", "Main synthesis second."),
    );
    observerCallback();
    assert.equal(
      global.window.__viventiumFirstVisibleMainPaint.assistantPartId,
      "content:2",
    );
    assert.equal(
      global.window.__viventiumFirstVisibleMainPaint.assistantPartAgentId,
      "agent-main",
    );
    assert.equal(
      global.window.__viventiumFirstVisibleMainPaint.paintedAtMs,
      1_025,
    );
  } finally {
    global.window = originalWindow;
    global.document = originalDocument;
    global.MutationObserver = originalMutationObserver;
    global.requestAnimationFrame = originalRequestAnimationFrame;
    global.performance = originalPerformance;
  }
});

test("public summary exposes only first-paint durations and counts", () => {
  const summary = buildPublicSummary({
    args: {
      caseId: "ANTI-012",
      qaRunId: "ANTI-012-run",
      qaEmail: "qa-private@example.com",
      agentId: "agent-main-private",
      prompt: "private prompt",
      outputDir: "/private/evidence/run",
    },
    timing: {
      privateReceipt: {
        interactionStartedAtMs: 9_000,
        paintedAtMs: 9_123,
        userMessageId: "private-user-id",
        assistantMessageId: "private-main-id",
        assistantPartId: "content:private-part",
        assistantPartAgentId: "private-main-agent-id",
      },
      publicMetrics: {
        firstVisibleMainPaintObserved: true,
        firstVisibleMainPaintCorrelated: true,
        firstVisibleMainPaintMs: 123,
        firstVisibleMainPaintCorrelationCount: 1,
      },
    },
    expectedToolExecution: {
      required: true,
      pass: true,
      callCount: 1,
      successfulCallCount: 1,
      failedCallCount: 0,
      expectedToolName: "schedule_create_mcp_scheduling-cortex",
      privateTaskId: "private-task-id",
    },
    expectedScheduleLifecycle: {
      required: true,
      pass: true,
      preflightMatchingRowCount: 0,
      postRunMatchingRowCount: 1,
      cleanupAttemptCount: 1,
      cleanupSuccessCount: 1,
      postCleanupMatchingRowCount: 0,
      protectedBaselineStable: true,
      protectedFingerprint: "private-protected-fingerprint",
      matchingTaskIds: ["private-schedule-task-id"],
    },
  });
  const serialized = JSON.stringify(summary);
  assert.equal(summary.firstVisibleMainPaintMs, 123);
  assert.equal(summary.firstVisibleMainPaintCorrelationCount, 1);
  assert.equal(summary.expectedToolExecutionPass, true);
  assert.equal(summary.expectedToolCallCount, 1);
  assert.equal(summary.expectedScheduleLifecyclePass, true);
  assert.equal(summary.expectedSchedulePostRunRowCount, 1);
  assert.equal(summary.expectedSchedulePostCleanupRowCount, 0);
  for (const forbidden of [
    "private-user-id",
    "private-main-id",
    "interactionStartedAtMs",
    "paintedAtMs",
    "content:private-part",
    "private-main-agent-id",
    "9000",
    "9123",
    "schedule_create_mcp_scheduling-cortex",
    "private-task-id",
    "private-protected-fingerprint",
    "private-schedule-task-id",
  ]) {
    assert.equal(serialized.includes(forbidden), false);
  }
});

test("reopen public summary hashes the conversation and leaks neither identifier nor token", () => {
  const summary = buildPublicSummary({
    args: {
      runMode: "reopen",
      caseId: "ANTI-006",
      qaRunId: "ANTI-006-public-run",
      qaEmail: "qa-private@example.com",
      agentId: "agent-private",
      prompt: "public-safe audit label",
      outputDir: "/private/evidence/run",
      reopenConversationId: "conversation-private-reopen",
      accessToken: "token-private-sentinel",
    },
    conversationId: "conversation-private-reopen",
    requestInjectionCount: 0,
    agentChatPostCount: 0,
    conversationPreserved: true,
    acceptance: { pass: true, failures: [] },
    error: `${["Bear", "er"].join("")} token-private-sentinel failed at http://localhost/c/conversation-private-reopen`,
  });
  const serialized = JSON.stringify(summary);

  assert.equal(summary.runMode, "reopen");
  assert.equal(summary.agentChatPostCount, 0);
  assert.equal(summary.conversationPreserved, true);
  assert.equal(summary.conversationIdHash.length, 16);
  for (const forbidden of [
    "conversation-private-reopen",
    "token-private-sentinel",
    "qa-private@example.com",
    "/private/evidence/run",
  ]) {
    assert.equal(serialized.includes(forbidden), false);
  }

  const mutated = buildPublicSummary({
    args: {
      runMode: "reopen",
      caseId: "ANTI-006",
      qaRunId: "ANTI-006-public-run-mutated",
      qaEmail: "qa@example.com",
      agentId: "agent-synthetic",
      prompt: "public-safe audit label",
      outputDir: "/private/evidence/mutated",
      reopenConversationId: "conversation-private-reopen",
    },
    conversationId: "conversation-private-reopen",
    agentChatPostCount: 0,
    conversationPreserved: false,
    acceptance: {
      pass: false,
      failures: ["conversation_not_proven_preserved"],
    },
  });
  assert.equal(mutated.conversationPreserved, false);
  assert.equal(mutated.pass, false);
});
