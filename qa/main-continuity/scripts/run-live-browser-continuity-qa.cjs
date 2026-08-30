#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = "http://127.0.0.1:3190";
const API_BASE = "http://127.0.0.1:3180";
const MARKER = "Amber Lantern 42";
const FIRST_PROMPT =
  "Continuity QA WEB1. Remember that the project codename is Amber Lantern 42. Reply only: Ready for the next question.";
const SECOND_PROMPT = "What was the project codename?";
const THIRD_PROMPT =
  "Use one native file or shell tool to inspect AGENTS.md without changing files, then reply with TOOL_CONTEXT_OK.";

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const split = line.indexOf("=");
    const key = line.slice(0, split).trim();
    let value = line.slice(split + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadEnv() {
  const runtime = path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "runtime",
  );
  return {
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, ".env")),
    ...parseEnvFile(path.join(runtime, "runtime.env")),
    ...parseEnvFile(path.join(runtime, "runtime.local.env")),
    ...parseEnvFile(path.join(runtime, "service-env", "librechat.env")),
    ...parseEnvFile(path.join(runtime, "service-env", "librechat.owner.env")),
    ...process.env,
  };
}

function hash(value) {
  return crypto.createHash("sha256").update(String(value || "")).digest("hex").slice(0, 16);
}

function progress(step) {
  process.stderr.write(`${JSON.stringify({ step })}\n`);
}

function renderText(message) {
  if (typeof message?.text === "string" && message.text.trim()) return message.text.trim();
  return (Array.isArray(message?.content) ? message.content : [])
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("")
    .trim();
}

async function waitForFinishedTurn({ db, userId, prompt, startedAt, timeoutMs = 240000 }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const userMessage = await db.collection("messages").findOne(
      {
        user: userId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: new Date(startedAt.getTime() - 2000) },
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    if (userMessage) {
      const assistant = await db.collection("messages").findOne(
        {
          user: userId,
          conversationId: userMessage.conversationId,
          parentMessageId: userMessage.messageId,
          isCreatedByUser: false,
          unfinished: false,
        },
        { sort: { createdAt: -1, _id: -1 } },
      );
      if (assistant && renderText(assistant)) return { userMessage, assistant };
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("browser_turn_timeout");
}

async function installAuth(page, accessToken) {
  await page.evaluate((token) => {
    localStorage.setItem("token", token);
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: token }));
  }, accessToken);
}

async function main() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("local_browser_qa_only");
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error("set_VIVENTIUM_QA_ALLOW_LOCAL_JWT=1");
  }
  const outputDir = path.resolve(String(process.env.VIVENTIUM_QA_PRIVATE_DIR || ""));
  if (!outputDir || outputDir === path.parse(outputDir).root) throw new Error("private_output_required");
  if (path.relative(REPO_ROOT, outputDir).split(path.sep)[0] !== "..") {
    throw new Error("private_output_must_be_outside_repo");
  }
  fs.mkdirSync(outputDir, { recursive: true });

  const env = loadEnv();
  const agentId = String(env.VIVENTIUM_QA_MAIN_AGENT_ID || "").trim();
  if (!agentId) throw new Error("VIVENTIUM_QA_MAIN_AGENT_ID_is_required");
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET || !env.VIVENTIUM_QA_EMAIL) {
    throw new Error("missing_local_qa_prerequisites");
  }
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"));
  const jwt = require(path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, "node_modules", "playwright"));
  const mongo = new MongoClient(env.MONGO_URI, { serverSelectionTimeoutMS: 5000 });
  let browser;
  let sessionId;
  let db;
  let user;
  const result = {
    pass: false,
    browserPostCount: 0,
    screenshots: 0,
    firstFinished: false,
    secondFinished: false,
    secondRetainedMarker: false,
    thirdFinished: false,
    toolContextOk: false,
    exactUserTurns: false,
    oneReplyPerTurn: false,
    detailsVisible: false,
    refreshPersisted: false,
    agentSelectedAfterRefresh: false,
    consoleErrorCount: 0,
  };

  try {
    await mongo.connect();
    const dbName = new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
    db = mongo.db(dbName);
    user = await db.collection("users").findOne({ email: env.VIVENTIUM_QA_EMAIL.trim().toLowerCase() });
    if (!user?._id || String(user.role || "").toUpperCase() === "ADMIN") {
      throw new Error("non_admin_qa_user_required");
    }
    const agent = await db.collection("agents").findOne({ id: agentId });
    if (!agent?.id) throw new Error("main_agent_missing");

    sessionId = new ObjectId();
    const userId = String(user._id);
    const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const refreshToken = jwt.sign(
      { id: userId, sessionId: String(sessionId) },
      env.JWT_REFRESH_SECRET,
      { expiresIn: 7200 },
    );
    const accessToken = jwt.sign(
      { id: userId, username: user.username, provider: user.provider, email: user.email },
      env.JWT_SECRET,
      { expiresIn: "2h" },
    );
    await db.collection("sessions").insertOne({
      _id: sessionId,
      user: user._id,
      expiration,
      refreshTokenHash: crypto.createHash("sha256").update(refreshToken).digest("hex"),
    });

    browser = await chromium.launch({ channel: "chrome", headless: false });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const expires = Math.floor(Date.now() / 1000) + 7200;
    await context.addCookies(
      [CLIENT_BASE, API_BASE].flatMap((url) => [
        { name: "refreshToken", value: refreshToken, url, httpOnly: true, sameSite: "Strict", expires },
        { name: "token_provider", value: "librechat", url, httpOnly: true, sameSite: "Strict", expires },
      ]),
    );
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    page.on("console", (message) => {
      if (message.type() === "error") result.consoleErrorCount += 1;
    });
    page.on("request", (request) => {
      if (request.method() === "POST" && /\/api\/agents\/chat/.test(new URL(request.url()).pathname)) {
        result.browserPostCount += 1;
      }
    });

    await page.goto(CLIENT_BASE, { waitUntil: "domcontentloaded" });
    progress("browser_opened");
    await installAuth(page, accessToken);
    await page.goto(`${CLIENT_BASE}/c/new?agent_id=${encodeURIComponent(agentId)}`, {
      waitUntil: "domcontentloaded",
    });
    await installAuth(page, accessToken);
    const input = page.getByLabel("Message input").or(page.getByPlaceholder(/^Message/)).last();
    await input.waitFor({ state: "visible" });
    await page.screenshot({ path: path.join(outputDir, "01-before-submit.png"), fullPage: true });
    result.screenshots += 1;

    const firstStarted = new Date();
    await input.fill(FIRST_PROMPT);
    await page.getByTestId("send-button").last().click();
    progress("first_submitted");
    const first = await waitForFinishedTurn({ db, userId, prompt: FIRST_PROMPT, startedAt: firstStarted });
    result.firstFinished = true;
    progress("first_finished");
    await page
      .locator(`[id="${first.assistant.messageId}"]`)
      .waitFor({ state: "visible", timeout: 60000 });
    progress("first_visible");
    await page.screenshot({ path: path.join(outputDir, "02-first-finished.png"), fullPage: true });
    result.screenshots += 1;

    const secondStarted = new Date();
    await input.fill(SECOND_PROMPT);
    await page.getByTestId("send-button").last().click();
    progress("second_submitted");
    const second = await waitForFinishedTurn({ db, userId, prompt: SECOND_PROMPT, startedAt: secondStarted });
    result.secondFinished = true;
    const secondText = renderText(second.assistant);
    result.secondRetainedMarker = secondText.toLowerCase().includes(MARKER.toLowerCase());
    progress("second_finished");
    await page
      .locator(`[id="${second.assistant.messageId}"]`)
      .waitFor({ state: "visible", timeout: 60000 });
    progress("second_visible");

    const thirdStarted = new Date();
    await input.fill(THIRD_PROMPT);
    await page.getByTestId("send-button").last().click();
    progress("third_submitted");
    const third = await waitForFinishedTurn({ db, userId, prompt: THIRD_PROMPT, startedAt: thirdStarted });
    result.thirdFinished = true;
    result.toolContextOk = renderText(third.assistant).includes("TOOL_CONTEXT_OK");
    progress("third_finished");
    await page
      .locator(`[id="${third.assistant.messageId}"]`)
      .waitFor({ state: "visible", timeout: 60000 });
    progress("third_visible");

    const conversationId = String(third.userMessage.conversationId);
    const userTurns = await db.collection("messages").find({
      user: userId,
      conversationId,
      isCreatedByUser: true,
      text: { $in: [FIRST_PROMPT, SECOND_PROMPT, THIRD_PROMPT] },
    }).toArray();
    result.exactUserTurns = userTurns.length === 3;
    const replyCounts = await Promise.all(
      userTurns.map((message) =>
        db.collection("messages").countDocuments({
          user: userId,
          conversationId,
          isCreatedByUser: false,
          parentMessageId: message.messageId,
          unfinished: false,
        }),
      ),
    );
    result.oneReplyPerTurn = replyCounts.length === 3 && replyCounts.every((count) => count === 1);

    const details = page.getByText("Harness activity", { exact: true }).last();
    if (await details.isVisible().catch(() => false)) {
      await details.click();
      result.detailsVisible = true;
    }
    await page.screenshot({ path: path.join(outputDir, "03-third-and-details.png"), fullPage: true });
    result.screenshots += 1;

    await page.reload({ waitUntil: "domcontentloaded" });
    await installAuth(page, accessToken);
    await page
      .locator(`[id="${third.assistant.messageId}"]`)
      .waitFor({ state: "visible", timeout: 60000 });
    await page
      .getByPlaceholder(/^Message Viventium$/)
      .last()
      .waitFor({ state: "visible", timeout: 30000 });
    result.agentSelectedAfterRefresh = true;
    progress("refresh_visible");
    result.refreshPersisted = true;
    await page.screenshot({ path: path.join(outputDir, "04-after-refresh.png"), fullPage: true });
    result.screenshots += 1;

    result.conversationHash = hash(conversationId);
    result.firstMessageHash = hash(first.assistant.messageId);
    result.secondMessageHash = hash(second.assistant.messageId);
    result.thirdMessageHash = hash(third.assistant.messageId);
    result.pass =
      result.firstFinished &&
      result.secondFinished &&
      result.secondRetainedMarker &&
      result.thirdFinished &&
      result.toolContextOk &&
      result.exactUserTurns &&
      result.oneReplyPerTurn &&
      result.detailsVisible &&
      result.refreshPersisted &&
      result.agentSelectedAfterRefresh;
  } finally {
    if (db && sessionId) await db.collection("sessions").deleteOne({ _id: sessionId }).catch(() => {});
    await browser?.close().catch(() => {});
    await mongo.close().catch(() => {});
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.pass) process.exitCode = 1;
}

main().catch((error) => {
  process.stderr.write(`${String(error?.message || error).replace(/\/Users\/[^\s]+/g, "<path>")}\n`);
  process.exitCode = 1;
});
