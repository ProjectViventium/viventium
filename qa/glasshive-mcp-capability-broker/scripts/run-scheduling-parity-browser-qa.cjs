#!/usr/bin/env node
"use strict";

/**
 * Real-browser acceptance for main-Agent scheduling through the GlassHive conversation provider.
 *
 * The harness uses the configured non-admin local QA account, creates one synthetic reminder
 * through the visible chat UI, verifies persistence and reload, deletes it through the same UI,
 * and removes the exact synthetic chat/session residue. Raw screenshots stay in App Support.
 */

const crypto = require("crypto");
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const APP_SUPPORT = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
);
const CONFIG_PATH = path.join(APP_SUPPORT, "config.yaml");
const DEFAULT_AGENT_ID =
  process.env.VIVENTIUM_QA_AGENT_ID || "agent_viventium_main_95aeb3";

function hashValue(value, length = 12) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      value.length >= 2 &&
      value[0] === value[value.length - 1] &&
      (value[0] === '"' || value[0] === "'")
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadRuntimeEnv() {
  const runtime = path.join(APP_SUPPORT, "runtime");
  const candidates = [
    path.join(runtime, "runtime.env"),
    path.join(runtime, "runtime.local.env"),
    path.join(runtime, "service-env", "librechat.env"),
    path.join(LIBRECHAT_ROOT, ".env"),
  ];
  const env = { ...process.env };
  for (const candidate of candidates)
    Object.assign(env, parseEnvFile(candidate));
  const port = String(env.VIVENTIUM_LOCAL_MONGO_PORT || "").trim();
  const database = String(
    env.VIVENTIUM_LOCAL_MONGO_DB || "LibreChatViventium",
  ).trim();
  if (port) env.MONGO_URI = `mongodb://127.0.0.1:${port}/${database}`;
  return env;
}

function configuredQaEmail() {
  if (process.env.VIVENTIUM_QA_EMAIL)
    return process.env.VIVENTIUM_QA_EMAIL.trim().toLowerCase();
  if (!fs.existsSync(CONFIG_PATH)) return "";
  const yaml = require(path.join(LIBRECHAT_ROOT, "node_modules", "yaml"));
  const config = yaml.parse(fs.readFileSync(CONFIG_PATH, "utf8")) || {};
  return String(config.runtime?.extra_env?.VIVENTIUM_QA_EMAIL || "")
    .trim()
    .toLowerCase();
}

function parseArgs(argv) {
  const args = {
    apiBase: process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180",
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190",
    agentId: DEFAULT_AGENT_ID,
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 240000),
    headless: process.env.VIVENTIUM_QA_HEADLESS !== "0",
    cleanupMarker: "",
  };
  for (const arg of argv) {
    if (arg === "--headed") args.headless = false;
    else if (arg === "--headless") args.headless = true;
    else if (arg.startsWith("--timeout-ms="))
      args.timeoutMs = Number(arg.slice(13));
    else if (arg.startsWith("--cleanup-marker="))
      args.cleanupMarker = arg.slice("--cleanup-marker=".length).trim();
  }
  args.apiBase = args.apiBase.replace(/\/$/, "");
  args.clientBase = args.clientBase.replace(/\/$/, "");
  return args;
}

function ensureLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("local_qa_jwt_forbidden_in_ci_or_production");
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error("local_qa_jwt_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT");
  }
}

async function createQaAuth({ env, db, user }) {
  const jwt = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
  );
  const { ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  if (!env.JWT_SECRET || !env.JWT_REFRESH_SECRET)
    throw new Error("missing_jwt_prerequisites");
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: String(user._id), sessionId: String(sessionId) },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  const accessToken = jwt.sign(
    {
      id: String(user._id),
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: "2h" },
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
  return { sessionId, refreshToken, accessToken };
}

async function attachAuth({ context, args, auth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  await context.addCookies(
    [args.apiBase, args.clientBase].flatMap((url) => [
      {
        name: "refreshToken",
        value: auth.refreshToken,
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
    ]),
  );
}

async function installAccessToken(page, fallbackToken) {
  const refreshed = await page.evaluate(async () => {
    const response = await fetch("/api/auth/refresh", { method: "POST" });
    const payload = await response.json().catch(() => ({}));
    return {
      ok: response.ok,
      token: typeof payload.token === "string" ? payload.token : "",
    };
  });
  const token =
    refreshed.ok && refreshed.token ? refreshed.token : fallbackToken;
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: value }));
  }, token);
  await page.waitForTimeout(400);
  return token;
}

async function submitPrompt(page, prompt) {
  const input = page
    .getByLabel("Message input")
    .or(page.getByPlaceholder(/^Message Viventium$/))
    .last();
  await input.waitFor({ state: "visible", timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").last().click({ timeout: 30000 });
}

async function waitForVisibleAssistant(page, messageId) {
  const container = page.locator(`[id="${String(messageId)}"]`).last();
  await container.waitFor({ state: "visible", timeout: 30000 });
  await container
    .locator(".agent-turn")
    .waitFor({ state: "visible", timeout: 30000 });
  if (!(await container.innerText()).trim())
    throw new Error("browser_assistant_message_not_visible");
}

function messageText(message) {
  const text = typeof message?.text === "string" ? message.text : "";
  const content = Array.isArray(message?.content)
    ? message.content
        .map((part) => {
          if (part?.type !== "text") return "";
          if (typeof part.text === "string") return part.text;
          return typeof part.text?.value === "string" ? part.text.value : "";
        })
        .filter(Boolean)
        .join("\n")
    : "";
  // LibreChat can persist the same visible answer both in `text` and structured content along with
  // non-rendered tool parts. Compare the canonical visible `text` when present so UI verification
  // does not demand hidden/internal content that the renderer correctly omits.
  return text.trim() || content.trim();
}

async function waitForCondition(fn, { timeoutMs, intervalMs = 750, error }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await fn();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(error);
}

async function waitForTurn({ db, userId, prompt, startedAt, timeoutMs }) {
  const userMessage = await waitForCondition(
    () =>
      db.collection("messages").findOne(
        {
          user: userId,
          isCreatedByUser: true,
          text: prompt,
          createdAt: { $gte: startedAt },
        },
        { sort: { createdAt: -1, _id: -1 } },
      ),
    { timeoutMs, error: "browser_user_message_not_persisted" },
  );
  const assistantMessage = await waitForCondition(
    async () => {
      const rows = await db
        .collection("messages")
        .find({
          user: userId,
          conversationId: userMessage.conversationId,
          isCreatedByUser: false,
          createdAt: { $gte: startedAt },
        })
        .sort({ createdAt: -1, _id: -1 })
        .limit(8)
        .toArray();
      return (
        rows.find(
          (candidate) =>
            candidate.parentMessageId === userMessage.messageId &&
            candidate.unfinished !== true,
        ) || rows.find((candidate) => candidate.unfinished !== true)
      );
    },
    { timeoutMs, error: "browser_assistant_message_not_completed" },
  );
  const assistantText = messageText(assistantMessage);
  if (!assistantText) throw new Error("browser_assistant_message_empty");
  return { userMessage, assistantMessage, assistantText };
}

function sqlQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function matchingSchedules(dbPath, marker) {
  const sql = [
    "SELECT active,next_run_at,prompt,schedule_json",
    "FROM scheduled_tasks",
    `WHERE prompt LIKE ${sqlQuote(`%${marker}%`)}`,
    "ORDER BY created_at;",
  ].join(" ");
  const output = execFileSync("sqlite3", ["-readonly", "-json", dbPath, sql], {
    encoding: "utf8",
  }).trim();
  return output ? JSON.parse(output) : [];
}

function localRunAt(minutesAhead = 45) {
  const date = new Date(Date.now() + minutesAhead * 60 * 1000);
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const parts = Object.fromEntries(
    formatter.formatToParts(date).map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

async function main() {
  ensureLocalQaAuth();
  const args = parseArgs(process.argv.slice(2));
  const env = loadRuntimeEnv();
  const qaEmail = configuredQaEmail();
  if (!qaEmail) throw new Error("configured_qa_email_missing");
  if (!env.MONGO_URI) throw new Error("local_mongo_uri_missing");
  const schedulingDb =
    env.SCHEDULING_DB_PATH ||
    path.join(
      APP_SUPPORT,
      "state",
      "runtime",
      "isolated",
      "scheduling",
      "schedules.db",
    );
  if (!fs.existsSync(schedulingDb)) throw new Error("scheduling_db_missing");

  const { MongoClient } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const { chromium } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
  );
  const mongo = new MongoClient(env.MONGO_URI);
  let db;
  let browser;
  let page;
  let auth;
  let user;
  const conversationIds = new Set();
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const marker =
    args.cleanupMarker ||
    `SCHEDPARITY_BROWSER_${hashValue(stamp, 12).toUpperCase()}`;
  const runAt = localRunAt();
  const privateOutputDir = path.join(
    APP_SUPPORT,
    "private-user-data",
    "qa",
    "glasshive-mcp-capability-broker",
    stamp,
  );
  const summary = {
    ok: false,
    markerHash: hashValue(marker),
    qaUserHash: "",
    createVisible: false,
    reloadPreserved: false,
    persistedExactlyOne: false,
    persistedTimezoneCorrect: false,
    cleanupVisible: false,
    zeroScheduleResidue: false,
    conversationResidue: null,
    recoveryOnly: Boolean(args.cleanupMarker),
  };

  try {
    await mongo.connect();
    const dbName =
      new URL(env.MONGO_URI).pathname.replace(/^\//, "") ||
      "LibreChatViventium";
    db = mongo.db(dbName);
    user = await db.collection("users").findOne({ email: qaEmail });
    if (!user?._id) throw new Error("configured_qa_user_not_found");
    if (String(user.role || "").toUpperCase() === "ADMIN") {
      throw new Error("configured_qa_user_must_be_non_admin");
    }
    summary.qaUserHash = hashValue(user._id);
    auth = await createQaAuth({ env, db, user });

    fs.mkdirSync(privateOutputDir, { recursive: true, mode: 0o700 });
    browser = await chromium.launch({
      channel: "chrome",
      headless: args.headless,
    });
    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1440, height: 960 },
    });
    await attachAuth({ context, args, auth });
    page = await context.newPage();
    const agentUrl = `${args.clientBase}/c/new?agent_id=${encodeURIComponent(args.agentId)}`;
    await page.goto(agentUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await installAccessToken(page, auth.accessToken);
    await page.goto(agentUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    await installAccessToken(page, auth.accessToken);

    const cleanupPrompt =
      `Delete the temporary schedule containing ${marker} now. ` +
      "Confirm only after the scheduling tool succeeds.";
    if (args.cleanupMarker) {
      const cleanupStartedAt = new Date();
      await submitPrompt(page, cleanupPrompt);
      const cleanupTurn = await waitForTurn({
        db,
        userId: String(user._id),
        prompt: cleanupPrompt,
        startedAt: cleanupStartedAt,
        timeoutMs: args.timeoutMs,
      });
      conversationIds.add(cleanupTurn.userMessage.conversationId);
      await waitForVisibleAssistant(
        page,
        cleanupTurn.assistantMessage.messageId,
      );
      summary.cleanupVisible = true;
      await waitForCondition(
        () => matchingSchedules(schedulingDb, marker).length === 0,
        { timeoutMs: 30000, error: "synthetic_schedule_cleanup_failed" },
      );
      summary.zeroScheduleResidue = true;
      await page.screenshot({
        path: path.join(privateOutputDir, "recovery-deleted-zero-residue.png"),
        fullPage: true,
      });
      summary.ok = summary.cleanupVisible && summary.zeroScheduleResidue;
    } else {
      const createPrompt =
        `Create a one-time reminder for ${runAt} America/Toronto. ` +
        `When it runs, reply exactly: Synthetic browser scheduler parity check ${marker}. ` +
        "This is temporary QA; confirm only after the scheduling tool succeeds.";
      const createStartedAt = new Date();
      await submitPrompt(page, createPrompt);
      const createTurn = await waitForTurn({
        db,
        userId: String(user._id),
        prompt: createPrompt,
        startedAt: createStartedAt,
        timeoutMs: args.timeoutMs,
      });
      conversationIds.add(createTurn.userMessage.conversationId);
      await waitForVisibleAssistant(
        page,
        createTurn.assistantMessage.messageId,
      );
      summary.createVisible = true;
      const createdRows = await waitForCondition(
        () => {
          const rows = matchingSchedules(schedulingDb, marker);
          return rows.length === 1 ? rows : null;
        },
        {
          timeoutMs: 30000,
          error: "synthetic_schedule_not_persisted_exactly_once",
        },
      );
      summary.persistedExactlyOne =
        createdRows.length === 1 && createdRows[0].active === 1;
      const scheduleJson = JSON.parse(createdRows[0].schedule_json || "{}");
      summary.persistedTimezoneCorrect =
        scheduleJson.timezone === "America/Toronto";
      await page.screenshot({
        path: path.join(privateOutputDir, "created-before-reload.png"),
        fullPage: true,
      });

      await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
      await installAccessToken(page, auth.accessToken);
      await waitForVisibleAssistant(
        page,
        createTurn.assistantMessage.messageId,
      );
      summary.reloadPreserved = true;

      const cleanupStartedAt = new Date();
      await submitPrompt(page, cleanupPrompt);
      const cleanupTurn = await waitForTurn({
        db,
        userId: String(user._id),
        prompt: cleanupPrompt,
        startedAt: cleanupStartedAt,
        timeoutMs: args.timeoutMs,
      });
      conversationIds.add(cleanupTurn.userMessage.conversationId);
      await waitForVisibleAssistant(
        page,
        cleanupTurn.assistantMessage.messageId,
      );
      summary.cleanupVisible = true;
      await waitForCondition(
        () => matchingSchedules(schedulingDb, marker).length === 0,
        { timeoutMs: 30000, error: "synthetic_schedule_cleanup_failed" },
      );
      summary.zeroScheduleResidue = true;
      await page.screenshot({
        path: path.join(privateOutputDir, "deleted-zero-residue.png"),
        fullPage: true,
      });

      summary.ok =
        summary.createVisible &&
        summary.reloadPreserved &&
        summary.persistedExactlyOne &&
        summary.persistedTimezoneCorrect &&
        summary.cleanupVisible &&
        summary.zeroScheduleResidue;
    }
  } finally {
    if (
      page &&
      db &&
      user?._id &&
      fs.existsSync(schedulingDb) &&
      matchingSchedules(schedulingDb, marker).length > 0
    ) {
      try {
        const recoveryPrompt =
          `Delete the temporary schedule containing ${marker} now. ` +
          "Confirm only after the scheduling tool succeeds.";
        const recoveryStartedAt = new Date();
        await submitPrompt(page, recoveryPrompt);
        const recoveryTurn = await waitForTurn({
          db,
          userId: String(user._id),
          prompt: recoveryPrompt,
          startedAt: recoveryStartedAt,
          timeoutMs: args.timeoutMs,
        });
        conversationIds.add(recoveryTurn.userMessage.conversationId);
        await waitForCondition(
          () => matchingSchedules(schedulingDb, marker).length === 0,
          {
            timeoutMs: 30000,
            error: "synthetic_schedule_recovery_cleanup_failed",
          },
        );
        summary.zeroScheduleResidue = true;
        await page.screenshot({
          path: path.join(
            privateOutputDir,
            "failure-recovery-zero-residue.png",
          ),
          fullPage: true,
        });
      } catch {
        summary.zeroScheduleResidue = false;
      }
    }
    if (browser) await browser.close().catch(() => {});
    if (db && user?._id) {
      const ids = Array.from(conversationIds);
      if (ids.length) {
        const ownedConversationQuery = {
          conversationId: { $in: ids },
          user: { $in: [user._id, String(user._id)] },
        };
        await db.collection("messages").deleteMany(ownedConversationQuery);
        await db.collection("conversations").deleteMany(ownedConversationQuery);
        const remaining = await db
          .collection("messages")
          .countDocuments(ownedConversationQuery);
        summary.conversationResidue = remaining;
      }
      if (auth?.sessionId)
        await db.collection("sessions").deleteOne({ _id: auth.sessionId });
    }
    await mongo.close().catch(() => {});
    if (
      fs.existsSync(schedulingDb) &&
      matchingSchedules(schedulingDb, marker).length !== 0
    ) {
      summary.zeroScheduleResidue = false;
      summary.ok = false;
    }
    if (
      summary.conversationResidue !== null &&
      summary.conversationResidue !== 0
    )
      summary.ok = false;
    fs.mkdirSync(privateOutputDir, { recursive: true, mode: 0o700 });
    fs.writeFileSync(
      path.join(privateOutputDir, "result.private.json"),
      JSON.stringify({ ...summary, marker, runAt }, null, 2),
      { mode: 0o600 },
    );
  }

  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  if (!summary.ok) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`${String(error?.message || error)}\n`);
  process.exitCode = 1;
});
