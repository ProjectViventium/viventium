#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * ACT-37 real browser + Mongo + runtime restart acceptance.
 *
 * This harness is intentionally local-only and destructive to one synthetic in-flight QA turn:
 * it waits until an active background-cortex row is both visible and persisted, restarts the local
 * Viventium stack, proves the row survives reload, then waits for the normal stale-cortex recovery
 * window to make that interrupted row terminal and honest.
 *
 * Public reports contain hashes, counts, state classes, and verdicts only. Raw prompts, message and
 * conversation ids, account identifiers, tokens, command output, and private URLs stay local.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { execFileSync, spawn } = require("child_process");
const {
  assertNonOwnerQaSelection,
  cleanupQaRunArtifacts,
  installQaRequestIsolation,
} = require("./browser-qa-safety.cjs");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const LOCAL_JWT_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_LOCAL_JWT";
const RUNTIME_RESTART_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_RUNTIME_RESTART";
const EXPECTED_CORTEX_NAME = "Red Team";
const ACTIVE_CORTEX_STATUSES = new Set([
  "activating",
  "brewing",
  "processing",
  "running",
]);
const CORTEX_TYPES = new Set([
  "cortex_activation",
  "cortex_brewing",
  "cortex_insight",
]);
const RECOVERY_REASON = "stale_cortex_startup_recovery";

function hashValue(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function sanitizePublicError(value) {
  return String(value || "qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, "Bearer <redacted>")
    .replace(/sk-[A-Za-z0-9._-]+/g, "sk-<redacted>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 240);
}

function exitCodeForResult(result) {
  if (result?.pass) {
    return 0;
  }
  return result?.environmentBlocked ? 2 : 1;
}

function isExpectedNavigationAbort(value) {
  return /(?:net::ERR_ABORTED|NS_BINDING_ABORTED)/i.test(String(value || ""));
}

function isExpectedQaAuthBootstrapDiagnostic(value) {
  return /(?:status of 401 \(Unauthorized\)|Request failed with status code 401)/i.test(
    String(value || ""),
  );
}

function parseArgs(argv) {
  const startedAt = new Date().toISOString();
  const args = {
    startedAt,
    qaRunId: `interruption-${hashValue(startedAt)}`,
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190",
    apiBase: process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180",
    qaEmail: process.env.VIVENTIUM_QA_EMAIL || "qa@example.com",
    expectedCortexName:
      process.env.VIVENTIUM_QA_INTERRUPTION_CORTEX_NAME || EXPECTED_CORTEX_NAME,
    prompt:
      process.env.VIVENTIUM_QA_INTERRUPTION_PROMPT ||
      "I will launch a paid workflow analytics pilot next month based on one supportive buyer interview. Red-team this concrete plan and identify the smallest kill criterion.",
    out:
      process.env.VIVENTIUM_QA_REPORT_PATH ||
      path.join(
        REPO_ROOT,
        "qa",
        "background_agents",
        "reports",
        "2026-07-09-interruption-restart-browser-qa.md",
      ),
    headless: process.env.VIVENTIUM_QA_HEADLESS !== "0",
    activationTimeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 120000),
    restartTimeoutMs: Number(
      process.env.VIVENTIUM_QA_RESTART_TIMEOUT_MS || 180000,
    ),
    recoveryTimeoutMs: Number(
      process.env.VIVENTIUM_QA_RECOVERY_TIMEOUT_MS || 420000,
    ),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--client-base") {
      args.clientBase = next;
      i += 1;
    } else if (arg === "--api-base") {
      args.apiBase = next;
      i += 1;
    } else if (arg === "--qa-email") {
      args.qaEmail = next;
      i += 1;
    } else if (arg === "--expected-cortex-name") {
      args.expectedCortexName = next;
      i += 1;
    } else if (arg === "--prompt") {
      args.prompt = next;
      i += 1;
    } else if (arg === "--out") {
      args.out = next;
      i += 1;
    } else if (arg === "--headed") {
      args.headless = false;
    } else if (arg === "--headless") {
      args.headless = true;
    }
  }
  return args;
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const env = {};
  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
      continue;
    }
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

function localEnv() {
  const appSupportRuntime = path.join(
    process.env.HOME || "",
    "Library",
    "Application Support",
    "Viventium",
    "runtime",
  );
  return {
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, ".env")),
    ...parseEnvFile(path.join(REPO_ROOT, ".env")),
    ...parseEnvFile(path.join(appSupportRuntime, "runtime.env")),
    ...parseEnvFile(path.join(appSupportRuntime, "runtime.local.env")),
    ...process.env,
  };
}

async function createQaAuth({ args, env }) {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("Local QA JWT auth is forbidden in CI or production");
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== "1") {
    throw new Error(`Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1`);
  }
  if (process.env[RUNTIME_RESTART_ALLOW_ENV] !== "1") {
    throw new Error(
      `Runtime restart QA requires ${RUNTIME_RESTART_ALLOW_ENV}=1`,
    );
  }
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("Missing local QA auth prerequisites");
  }

  const { MongoClient, ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const jwt = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
  );
  const { MeiliSearch } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "meilisearch"),
  );
  const client = new MongoClient(env.MONGO_URI);
  await client.connect();
  const dbName =
    new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
  const db = client.db(dbName);
  const user = await db.collection("users").findOne({ email: args.qaEmail });
  if (!user?._id) {
    await client.close();
    throw new Error("QA user not found");
  }
  assertNonOwnerQaSelection({
    ownerEmail: process.env.VIVENTIUM_QA_OWNER_EMAIL,
    requestedEmail: args.qaEmail,
    selectedUser: user,
  });

  const userId = user._id.toString();
  const accessToken = jwt.sign(
    {
      id: userId,
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: "2h" },
  );
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: userId, sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  await db.collection("sessions").insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash: crypto
      .createHash("sha256")
      .update(refreshToken)
      .digest("hex"),
  });

  return {
    db,
    userId,
    accessToken,
    refreshToken,
    meiliClient:
      env.MEILI_HOST && env.MEILI_MASTER_KEY
        ? new MeiliSearch({
            host: env.MEILI_HOST,
            apiKey: env.MEILI_MASTER_KEY,
          })
        : null,
    async close() {
      await db
        .collection("sessions")
        .deleteOne({ _id: sessionId })
        .catch(() => {});
      await client.close();
    },
  };
}

async function attachAuthCookies({ context, args, qaAuth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  const cookies = [args.apiBase, args.clientBase].flatMap((url) => [
    {
      name: "refreshToken",
      value: qaAuth.refreshToken,
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
    {
      name: "token_provider",
      value: "librechat",
      url,
      httpOnly: true,
      sameSite: "Strict",
      expires,
    },
  ]);
  await context.addCookies(cookies);
}

async function installAccessToken(page, localAccessToken) {
  const refresh = await page.evaluate(async () => {
    const response = await fetch("/api/auth/refresh", { method: "POST" });
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    return {
      ok: response.ok,
      status: response.status,
      token: payload && typeof payload.token === "string" ? payload.token : "",
    };
  });
  const token = refresh.ok && refresh.token ? refresh.token : localAccessToken;
  if (!token) {
    throw new Error(`auth_refresh_failed_status_${refresh.status}`);
  }
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: value }));
  }, token);
  await page.waitForTimeout(250);
}

async function createAuthenticatedPage({
  browser,
  args,
  qaAuth,
  collectDiagnostics = false,
}) {
  const context = await browser.newContext({
    baseURL: args.clientBase,
    viewport: { width: 1280, height: 960 },
  });
  await attachAuthCookies({ context, args, qaAuth });
  const page = await context.newPage();
  await installQaRequestIsolation(page, { qaRunId: args.qaRunId });
  const diagnostics = { consoleErrors: [], failedRequests: [], httpErrors: [] };
  if (collectDiagnostics) {
    page.on("console", (message) => {
      if (message.type() === "error") {
        diagnostics.consoleErrors.push(sanitizePublicError(message.text()));
      }
    });
    page.on("requestfailed", (request) => {
      diagnostics.failedRequests.push(
        sanitizePublicError(request.failure()?.errorText || "failed"),
      );
    });
    page.on("response", (response) => {
      if (response.status() < 400) {
        return;
      }
      let pathname = "<invalid-path>";
      try {
        pathname = new URL(response.url()).pathname;
      } catch {
        // Keep the public-safe placeholder.
      }
      diagnostics.httpErrors.push(`${response.status()} ${pathname}`);
    });
  }
  await page.goto(args.clientBase, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await installAccessToken(page, qaAuth.accessToken);
  return { context, page, diagnostics };
}

async function submitPrompt(page, prompt, timeoutMs) {
  const input = page
    .getByLabel("Message input")
    .or(page.getByPlaceholder(/^Message Viventium$/))
    .last();
  await input.waitFor({
    state: "visible",
    timeout: Math.min(timeoutMs, 60000),
  });
  await input.fill(prompt);
  await page.getByTestId("send-button").last().click({ timeout: timeoutMs });
}

async function waitForConversationForPrompt({
  qaAuth,
  prompt,
  startedAt,
  timeoutMs,
}) {
  const deadline = Date.now() + timeoutMs;
  const startedDate = new Date(startedAt);
  while (Date.now() < deadline) {
    const userMessage = await qaAuth.db.collection("messages").findOne(
      {
        user: qaAuth.userId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: startedDate },
      },
      { sort: { createdAt: -1, _id: -1 }, projection: { conversationId: 1 } },
    );
    if (userMessage?.conversationId) {
      return String(userMessage.conversationId);
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("missing_current_qa_conversation_for_prompt");
}

function summarizeCortexMessage(message) {
  const parts = Array.isArray(message?.content)
    ? message.content.filter((part) => part && CORTEX_TYPES.has(part.type))
    : [];
  const activeNames = [];
  const recoveredTerminalNames = [];
  const terminalNames = [];
  for (const part of parts) {
    const name = String(
      part.cortex_name || part.cortexName || part.cortex_id || "",
    ).trim();
    const status = String(part.status || "")
      .trim()
      .toLowerCase();
    if (name && ACTIVE_CORTEX_STATUSES.has(status)) {
      activeNames.push(name);
    }
    if (
      name &&
      ["complete", "completed", "done", "error", "failed"].includes(status)
    ) {
      terminalNames.push(name);
    }
    if (
      name &&
      part.recovery_reason === RECOVERY_REASON &&
      ["error", "failed"].includes(status)
    ) {
      recoveredTerminalNames.push(name);
    }
  }
  return {
    activeNames: [...new Set(activeNames)].sort(),
    recoveredTerminalNames: [...new Set(recoveredTerminalNames)].sort(),
    terminalNames: [...new Set(terminalNames)].sort(),
    cortexPartCount: parts.length,
    unfinished: message?.unfinished === true,
    textLength: typeof message?.text === "string" ? message.text.length : 0,
    hasGenerationPlaceholder:
      typeof message?.text === "string" &&
      /\bGeneration in progress\.?\b/i.test(message.text),
  };
}

async function findCortexMessage({ qaAuth, conversationId, startedAt }) {
  return qaAuth.db.collection("messages").findOne(
    {
      user: qaAuth.userId,
      conversationId,
      isCreatedByUser: false,
      createdAt: { $gte: new Date(startedAt) },
      "content.type": { $in: [...CORTEX_TYPES] },
    },
    {
      sort: { createdAt: -1, _id: -1 },
      projection: {
        messageId: 1,
        conversationId: 1,
        content: 1,
        text: 1,
        unfinished: 1,
        createdAt: 1,
        updatedAt: 1,
      },
    },
  );
}

async function waitForPersistedActiveCortex({
  qaAuth,
  conversationId,
  startedAt,
  expectedCortexName,
  timeoutMs,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const message = await findCortexMessage({
      qaAuth,
      conversationId,
      startedAt,
    });
    const state = summarizeCortexMessage(message);
    if (message && state.activeNames.includes(expectedCortexName)) {
      return { message, state };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("persisted_active_cortex_timeout");
}

async function waitForRecoveredTerminalCortex({
  qaAuth,
  conversationId,
  startedAt,
  expectedCortexName,
  timeoutMs,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const message = await findCortexMessage({
      qaAuth,
      conversationId,
      startedAt,
    });
    const state = summarizeCortexMessage(message);
    if (
      message &&
      state.recoveredTerminalNames.includes(expectedCortexName) &&
      !state.activeNames.includes(expectedCortexName) &&
      state.unfinished === false
    ) {
      return { message, state };
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("recovered_terminal_cortex_timeout");
}

async function waitForVisibleCortexRow(page, expectedCortexName, timeoutMs) {
  await page.waitForFunction(
    (name) =>
      Array.from(
        document.querySelectorAll(".progress-text-wrapper button"),
      ).some((button) => String(button.textContent || "").includes(name)),
    expectedCortexName,
    { timeout: timeoutMs },
  );
}

function runLocalCommand(args, timeoutMs, { handoffAfterMs = 0 } = {}) {
  const executable = path.join(REPO_ROOT, "bin", "viventium");
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
      cwd: REPO_ROOT,
      env: process.env,
      detached: handoffAfterMs > 0,
      stdio: "ignore",
    });
    let settled = false;
    let handoffTimer = null;
    const timeoutTimer = setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      child.kill("SIGTERM");
      reject(new Error(`viventium_${args[0]}_failed:command_timeout`));
    }, timeoutMs);

    const finish = (callback) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeoutTimer);
      if (handoffTimer) {
        clearTimeout(handoffTimer);
      }
      callback();
    };

    child.once("error", (error) => {
      finish(() =>
        reject(
          new Error(
            `viventium_${args[0]}_failed:${sanitizePublicError(error?.message || error)}`,
          ),
        ),
      );
    });
    child.once("exit", (code, signal) => {
      finish(() => {
        if (code === 0) {
          resolve();
          return;
        }
        reject(
          new Error(
            `viventium_${args[0]}_failed:exit_${code ?? "none"}_${signal || "none"}`,
          ),
        );
      });
    });

    if (handoffAfterMs > 0) {
      handoffTimer = setTimeout(() => {
        finish(() => {
          child.unref();
          resolve();
        });
      }, handoffAfterMs);
    }
  });
}

function getApiProcessFingerprint() {
  try {
    const output = execFileSync(
      "/usr/sbin/lsof",
      ["-t", "-iTCP:3180", "-sTCP:LISTEN"],
      { encoding: "utf8", timeout: 5000 },
    ).trim();
    return output ? hashValue(output) : "";
  } catch {
    return "";
  }
}

async function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (response.ok) {
        return;
      }
    } catch {
      // Expected while the local runtime is restarting.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("runtime_health_timeout");
}

async function restartRuntime({ args, beforeFingerprint }) {
  await runLocalCommand(["stop"], args.restartTimeoutMs);
  let startCommandError = null;
  try {
    await runLocalCommand(["start"], args.restartTimeoutMs, {
      handoffAfterMs: 1000,
    });
  } catch (error) {
    startCommandError = error;
  }
  try {
    // Runtime health is authoritative after the detached launcher handoff. On macOS the supported
    // launcher can terminate its invoking process while the detached stack continues warming.
    await waitForHttp(`${args.apiBase}/api/health`, args.restartTimeoutMs);
    await waitForHttp(args.clientBase, args.restartTimeoutMs);
  } catch (healthError) {
    throw startCommandError || healthError;
  }
  const afterFingerprint = getApiProcessFingerprint();
  return {
    beforeFingerprint,
    afterFingerprint,
    changed: Boolean(
      beforeFingerprint &&
      afterFingerprint &&
      beforeFingerprint !== afterFingerprint,
    ),
  };
}

function renderReport(result) {
  return [
    "# Background Cortex Interruption/Restart Browser QA",
    "",
    `- Started: ${result.startedAt}`,
    "- Scope: local synthetic QA account, real browser, Mongo persistence, supported runtime stop/start, normal stale-cortex recovery.",
    `- QA user hash: \`${result.qaUserHash}\``,
    `- Prompt hash: \`${result.promptHash}\``,
    `- Conversation hash: \`${result.conversationHash || "unverified"}\``,
    `- Parent message hash: \`${result.parentMessageHash || "unverified"}\``,
    `- Expected cortex: ${result.expectedCortexName}`,
    `- Active card visible before restart: ${result.activeCardVisibleBeforeRestart}`,
    `- Active cortex persisted before restart: ${result.activePersistedBeforeRestart}`,
    `- Runtime API process changed: ${result.runtimeProcessChanged}`,
    `- Cortex card visible immediately after restart: ${result.cardVisibleImmediatelyAfterRestart}`,
    `- Persisted active state survived restart: ${result.activeStateSurvivedRestart}`,
    `- Recovered terminal cortex persisted: ${result.recoveredTerminalPersisted}`,
    `- Recovered terminal cortex visible after reload: ${result.recoveredTerminalVisibleAfterReload}`,
    `- Expanded recovered detail visible: ${result.expandedRecoveredDetailVisible}`,
    `- Parent unfinished after recovery: ${result.parentUnfinishedAfterRecovery}`,
    `- Misleading generation placeholder visible after recovery: ${result.generationPlaceholderVisibleAfterRecovery}`,
    `- Post-restart console errors: ${result.consoleErrorCount}`,
    `- Unexpected post-restart console errors: ${result.unexpectedConsoleErrorCount}`,
    `- Post-restart failed requests: ${result.failedRequestCount}`,
    `- Unexpected post-restart failed requests: ${result.unexpectedFailedRequestCount}`,
    `- Post-restart HTTP errors: ${result.httpErrorCount}`,
    `- Unexpected post-restart HTTP errors: ${result.unexpectedHttpErrorCount}`,
    "- Expected diagnostic exclusions: local-QA pre-token 401 bootstrap and browser navigation abort only.",
    result.unexpectedConsoleErrorSamples.length
      ? `- Unexpected console error samples: ${result.unexpectedConsoleErrorSamples
          .map((item) => `\`${item}\``)
          .join("; ")}`
      : "",
    result.unexpectedFailedRequestSamples.length
      ? `- Unexpected failed-request samples: ${result.unexpectedFailedRequestSamples
          .map((item) => `\`${item}\``)
          .join("; ")}`
      : "",
    result.unexpectedHttpErrorSamples.length
      ? `- Unexpected HTTP error samples: ${result.unexpectedHttpErrorSamples
          .map((item) => `\`${item}\``)
          .join("; ")}`
      : "",
    `- Result: ${result.pass ? "PASS" : "FAIL"}`,
    result.error ? `- Error: ${result.error}` : "",
    "",
  ]
    .filter(Boolean)
    .join("\n");
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const env = localEnv();
  const result = {
    startedAt: args.startedAt,
    qaUserHash: hashValue(args.qaEmail),
    promptHash: hashValue(args.prompt),
    expectedCortexName: args.expectedCortexName,
    conversationHash: "",
    parentMessageHash: "",
    activeCardVisibleBeforeRestart: false,
    activePersistedBeforeRestart: false,
    runtimeProcessChanged: false,
    cardVisibleImmediatelyAfterRestart: false,
    activeStateSurvivedRestart: false,
    recoveredTerminalPersisted: false,
    recoveredTerminalVisibleAfterReload: false,
    expandedRecoveredDetailVisible: false,
    parentUnfinishedAfterRecovery: true,
    generationPlaceholderVisibleAfterRecovery: false,
    consoleErrorCount: 0,
    unexpectedConsoleErrorCount: 0,
    failedRequestCount: 0,
    unexpectedFailedRequestCount: 0,
    httpErrorCount: 0,
    unexpectedHttpErrorCount: 0,
    unexpectedConsoleErrorSamples: [],
    unexpectedFailedRequestSamples: [],
    unexpectedHttpErrorSamples: [],
    environmentBlocked: false,
    error: null,
    pass: false,
  };

  let qaAuth;
  let browser;
  let initialContext;
  let restartedContext;
  const trackedConversationIds = new Set();
  try {
    qaAuth = await createQaAuth({ args, env });
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    browser = await chromium.launch({
      channel: "chrome",
      headless: args.headless,
    });

    const initial = await createAuthenticatedPage({ browser, args, qaAuth });
    initialContext = initial.context;
    const page = initial.page;
    await page.goto(`${args.clientBase}/c/new`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await installAccessToken(page, qaAuth.accessToken);
    await submitPrompt(page, args.prompt, args.activationTimeoutMs);

    const conversationId = await waitForConversationForPrompt({
      qaAuth,
      prompt: args.prompt,
      startedAt: args.startedAt,
      timeoutMs: args.activationTimeoutMs,
    });
    trackedConversationIds.add(conversationId);
    result.conversationHash = hashValue(conversationId);
    await waitForVisibleCortexRow(
      page,
      args.expectedCortexName,
      args.activationTimeoutMs,
    );
    result.activeCardVisibleBeforeRestart = true;

    const active = await waitForPersistedActiveCortex({
      qaAuth,
      conversationId,
      startedAt: args.startedAt,
      expectedCortexName: args.expectedCortexName,
      timeoutMs: args.activationTimeoutMs,
    });
    result.parentMessageHash = hashValue(active.message.messageId);
    result.activePersistedBeforeRestart = true;

    const beforeFingerprint = getApiProcessFingerprint();
    const restart = await restartRuntime({ args, beforeFingerprint });
    result.runtimeProcessChanged = restart.changed;

    const immediateMessage = await findCortexMessage({
      qaAuth,
      conversationId,
      startedAt: args.startedAt,
    });
    const immediateState = summarizeCortexMessage(immediateMessage);
    result.activeStateSurvivedRestart = immediateState.activeNames.includes(
      args.expectedCortexName,
    );

    const restarted = await createAuthenticatedPage({
      browser,
      args,
      qaAuth,
      collectDiagnostics: true,
    });
    restartedContext = restarted.context;
    const restartedPage = restarted.page;
    await restartedPage.goto(`${args.clientBase}/c/${conversationId}`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await installAccessToken(restartedPage, qaAuth.accessToken);
    await waitForVisibleCortexRow(
      restartedPage,
      args.expectedCortexName,
      args.activationTimeoutMs,
    );
    result.cardVisibleImmediatelyAfterRestart = true;
    // The helper first opens an authenticated landing page and then intentionally navigates to the
    // interrupted conversation. Discard bootstrap/aborted-navigation noise after that state is
    // proven; the final recovery reload below remains fully instrumented.
    await restartedPage.waitForTimeout(1500);
    restarted.diagnostics.consoleErrors.length = 0;
    restarted.diagnostics.failedRequests.length = 0;
    restarted.diagnostics.httpErrors.length = 0;

    const recovered = await waitForRecoveredTerminalCortex({
      qaAuth,
      conversationId,
      startedAt: args.startedAt,
      expectedCortexName: args.expectedCortexName,
      timeoutMs: args.recoveryTimeoutMs,
    });
    result.recoveredTerminalPersisted = true;
    result.parentUnfinishedAfterRecovery = recovered.state.unfinished;
    result.generationPlaceholderVisibleAfterRecovery =
      recovered.state.hasGenerationPlaceholder;

    await restartedPage.reload({
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await installAccessToken(restartedPage, qaAuth.accessToken);
    await waitForVisibleCortexRow(
      restartedPage,
      args.expectedCortexName,
      args.activationTimeoutMs,
    );
    const header = restartedPage
      .locator(".progress-text-wrapper button")
      .filter({ hasText: args.expectedCortexName })
      .first();
    await header.click({ timeout: 10000 }).catch(() => {});
    const body = await restartedPage
      .locator("body")
      .innerText({ timeout: 10000 });
    result.recoveredTerminalVisibleAfterReload =
      body.includes(args.expectedCortexName) &&
      /Error occurred|did not finish|runtime recovery/i.test(body);
    result.expandedRecoveredDetailVisible = body.includes(
      `Background agent: ${args.expectedCortexName}`,
    );
    result.generationPlaceholderVisibleAfterRecovery ||=
      /\bGeneration in progress\.?\b/i.test(body);
    result.consoleErrorCount = restarted.diagnostics.consoleErrors.length;
    result.failedRequestCount = restarted.diagnostics.failedRequests.length;
    result.httpErrorCount = restarted.diagnostics.httpErrors.length;
    result.unexpectedConsoleErrorSamples = [
      ...new Set(
        restarted.diagnostics.consoleErrors.filter(
          (item) => !isExpectedQaAuthBootstrapDiagnostic(item),
        ),
      ),
    ].slice(0, 3);
    result.unexpectedConsoleErrorCount =
      restarted.diagnostics.consoleErrors.filter(
        (item) => !isExpectedQaAuthBootstrapDiagnostic(item),
      ).length;
    result.unexpectedFailedRequestSamples = [
      ...new Set(
        restarted.diagnostics.failedRequests.filter(
          (item) => !isExpectedNavigationAbort(item),
        ),
      ),
    ].slice(0, 3);
    result.unexpectedFailedRequestCount =
      restarted.diagnostics.failedRequests.filter(
        (item) => !isExpectedNavigationAbort(item),
      ).length;
    result.unexpectedHttpErrorSamples = [
      ...new Set(
        restarted.diagnostics.httpErrors.filter((item) => !/^401\s/.test(item)),
      ),
    ].slice(0, 3);
    result.unexpectedHttpErrorCount = restarted.diagnostics.httpErrors.filter(
      (item) => !/^401\s/.test(item),
    ).length;

    result.pass =
      result.activeCardVisibleBeforeRestart &&
      result.activePersistedBeforeRestart &&
      result.runtimeProcessChanged &&
      result.cardVisibleImmediatelyAfterRestart &&
      result.activeStateSurvivedRestart &&
      result.recoveredTerminalPersisted &&
      result.recoveredTerminalVisibleAfterReload &&
      result.expandedRecoveredDetailVisible &&
      result.parentUnfinishedAfterRecovery === false &&
      result.generationPlaceholderVisibleAfterRecovery === false &&
      result.unexpectedConsoleErrorCount === 0 &&
      result.unexpectedFailedRequestCount === 0 &&
      result.unexpectedHttpErrorCount === 0;
  } catch (error) {
    const message = String(error?.message || error || "qa_failed");
    result.environmentBlocked =
      /QA user not found|Missing local QA auth|auth_refresh_failed/.test(
        message,
      );
    result.error = sanitizePublicError(message);
  } finally {
    if (qaAuth) {
      try {
        const cleanup = await cleanupQaRunArtifacts({
          db: qaAuth.db,
          userId: qaAuth.userId,
          startedAt: new Date(args.startedAt),
          trackedConversationIds: [...trackedConversationIds],
          qaRunId: args.qaRunId,
          meiliClient: qaAuth.meiliClient,
        });
        result.cleanupPass = true;
        result.cleanupConversationCount = cleanup.conversationsDeleted;
      } catch (cleanupError) {
        result.cleanupPass = false;
        result.pass = false;
        result.error = sanitizePublicError(
          cleanupError?.message || cleanupError,
        );
      }
    }
    await restartedContext?.close().catch(() => {});
    await initialContext?.close().catch(() => {});
    await browser?.close().catch(() => {});
    await qaAuth?.close().catch(() => {});
  }

  fs.mkdirSync(path.dirname(args.out), { recursive: true });
  fs.writeFileSync(args.out, `${renderReport(result)}\n`, "utf8");
  console.log(
    JSON.stringify(
      {
        ...result,
        error: result.error,
      },
      null,
      2,
    ),
  );
  process.exit(exitCodeForResult(result));
}

if (require.main === module) {
  run();
}

module.exports = {
  exitCodeForResult,
  isExpectedNavigationAbort,
  isExpectedQaAuthBootstrapDiagnostic,
  sanitizePublicError,
  summarizeCortexMessage,
};
