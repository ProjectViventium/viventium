#!/usr/bin/env node
"use strict";

/**
 * Real-browser acceptance for GlassHive as a normal Agent Builder provider.
 *
 * The harness uses a caller-selected non-admin QA account, creates two synthetic agents through the
 * supported API, configures each through the visible Agent Builder, runs one browser conversation,
 * verifies persistence in Mongo, and removes the synthetic agents/conversation before exit. Raw
 * screenshots remain under private App Support; stdout contains public-safe booleans and counts.
 */

const crypto = require("crypto");
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = (process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190").replace(/\/$/, "");
const API_BASE = (process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180").replace(/\/$/, "");
const PRIVATE_ROOT = process.env.VIVENTIUM_QA_PRIVATE_DIR || path.join(os.homedir(), "Library", "Application Support", "Viventium", "private-user-data");
const HEADED = process.argv.includes("--headed");

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    let value = line.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[line.slice(0, index).trim()] = value;
  }
  return values;
}

function loadLocalEnv() {
  const runtimeRoot = path.join(os.homedir(), "Library", "Application Support", "Viventium", "runtime");
  return [path.join(runtimeRoot, "runtime.env"), path.join(runtimeRoot, "runtime.local.env"), path.join(runtimeRoot, "service-env", "librechat.env"), path.join(LIBRECHAT_ROOT, ".env")].reduce((all, candidate) => Object.assign(all, parseEnvFile(candidate)), {
    ...process.env,
  });
}

function shortHash(value, length = 12) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function publicError(value) {
  return String(value || "browser_qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/\s+/g, " ")
    .slice(0, 400);
}

function authoredAssistantText(message) {
  const values = [];
  if (typeof message?.text === "string") values.push(message.text);
  for (const part of Array.isArray(message?.content) ? message.content : []) {
    if (part?.type !== "text") continue;
    if (typeof part.text === "string") values.push(part.text);
    if (typeof part?.text?.value === "string") values.push(part.text.value);
  }
  return values.join("\n");
}

function countOccurrences(value, needle) {
  return String(value || "").split(needle).length - 1;
}

function completedRequestDelta(after, before) {
  return (
    Number(after?.completed_request_count || 0) -
    Number(before?.completed_request_count || 0)
  );
}

function textTreeContains(rootPath, needle) {
  if (!rootPath || !fs.existsSync(rootPath)) return false;
  const pending = [path.resolve(rootPath)];
  while (pending.length) {
    const current = pending.pop();
    const stat = fs.lstatSync(current);
    if (stat.isSymbolicLink()) continue;
    if (stat.isDirectory()) {
      for (const entry of fs.readdirSync(current)) pending.push(path.join(current, entry));
      continue;
    }
    if (!stat.isFile() || stat.size > 1024 * 1024) continue;
    if (fs.readFileSync(current, "utf8").includes(needle)) return true;
  }
  return false;
}

async function visibleUiErrorLabels(page) {
  const visibleText = await page
    .locator("body")
    .innerText()
    .catch(() => "");
  const labels = visibleText.match(/\b(?:Memory|Provider|Model(?: Authentication)?|Authentication|Title|Tool) Error\b/gi);
  return [...new Set((labels || []).map((label) => label.replace(/\s+/g, " ").trim()))];
}

function sqlLiteral(value) {
  return `'${String(value || "").replaceAll("'", "''")}'`;
}

function providerStateFor(env, { ownerId, conversationId, agentId }) {
  if (!env.WPR_DB_PATH || !fs.existsSync(env.WPR_DB_PATH)) return null;
  const owner = sqlLiteral(ownerId);
  const conversation = sqlLiteral(conversationId);
  const agent = sqlLiteral(agentId);
  const sessionWhere = `owner_id = ${owner} AND conversation_id = ${conversation} AND agent_id = ${agent}`;
  const sql = `
    SELECT
      (SELECT COUNT(*) FROM provider_sessions WHERE ${sessionWhere}) AS session_count,
      (SELECT COUNT(*) FROM provider_requests request
        JOIN provider_sessions session ON session.session_id = request.session_id
        WHERE session.${sessionWhere}) AS request_count,
      (SELECT COUNT(*) FROM provider_requests request
        JOIN provider_sessions session ON session.session_id = request.session_id
        WHERE session.${sessionWhere} AND request.state = 'completed') AS completed_request_count,
      (SELECT COUNT(*) FROM provider_requests request
        JOIN provider_sessions session ON session.session_id = request.session_id
        WHERE session.${sessionWhere} AND request.state = 'cancelled') AS cancelled_request_count,
      COALESCE((SELECT MAX(history_count) FROM provider_sessions WHERE ${sessionWhere}), 0) AS history_count;
  `;
  const raw = execFileSync("/usr/bin/sqlite3", ["-json", env.WPR_DB_PATH, sql], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return JSON.parse(raw || "[]")[0] || null;
}

function providerRequestEvidence(env, { ownerId, conversationId, agentId, messageId = "" }) {
  if (!env.WPR_DB_PATH || !fs.existsSync(env.WPR_DB_PATH)) return null;
  const owner = sqlLiteral(ownerId);
  const conversation = sqlLiteral(conversationId);
  const agent = sqlLiteral(agentId);
  const messageFilter = messageId ? `AND request.message_id = ${sqlLiteral(messageId)}` : "";
  const sql = `
    SELECT
      request.request_id,
      request.state,
      COALESCE(run.instruction, '') AS instruction,
      COALESCE(run.output_text, '') AS output_text,
      COALESCE(request.response_json, '') AS response_json,
      COALESCE((
        SELECT GROUP_CONCAT(activity.summary || activity.payload_json, char(10))
        FROM provider_activity activity
        WHERE activity.request_id = request.request_id
      ), '') AS activity_text
    FROM provider_requests request
    JOIN provider_sessions session ON session.session_id = request.session_id
    LEFT JOIN runs run ON run.run_id = request.run_id
    WHERE
      session.owner_id = ${owner}
      AND session.conversation_id = ${conversation}
      AND session.agent_id = ${agent}
      ${messageFilter}
    ORDER BY request.created_at DESC
    LIMIT 1;
  `;
  const raw = execFileSync("/usr/bin/sqlite3", ["-json", env.WPR_DB_PATH, sql], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  return JSON.parse(raw || "[]")[0] || null;
}

function cleanupProviderState(env, { ownerId, agentIds }) {
  if (!env.WPR_DB_PATH || !fs.existsSync(env.WPR_DB_PATH) || !agentIds.length) return;
  const owner = sqlLiteral(ownerId);
  const agents = agentIds.map(sqlLiteral).join(", ");
  const sessionFilter = `owner_id = ${owner} AND agent_id IN (${agents})`;
  const sql = `
    BEGIN IMMEDIATE;
    DELETE FROM provider_activity WHERE request_id IN (
      SELECT request_id FROM provider_requests WHERE session_id IN (
        SELECT session_id FROM provider_sessions WHERE ${sessionFilter}
      )
    );
    DELETE FROM provider_requests WHERE session_id IN (
      SELECT session_id FROM provider_sessions WHERE ${sessionFilter}
    );
    DELETE FROM provider_sessions WHERE ${sessionFilter};
    COMMIT;
  `;
  execFileSync("/usr/bin/sqlite3", [env.WPR_DB_PATH, sql], {
    stdio: ["ignore", "ignore", "pipe"],
  });
}

function requireLocalOptIn() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("GlassHive Agent Builder QA is local-development only");
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error("Set VIVENTIUM_QA_ALLOW_LOCAL_JWT=1");
  }
  if (!process.env.VIVENTIUM_QA_EMAIL && !process.env.VIVENTIUM_QA_USER_NAME && !process.env.VIVENTIUM_QA_USER_HASH) {
    throw new Error("Set VIVENTIUM_QA_EMAIL, VIVENTIUM_QA_USER_NAME, or VIVENTIUM_QA_USER_HASH");
  }
}

async function createQaAuth(env) {
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("Missing local QA auth prerequisites");
  }
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"));
  const jwt = require(path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"));
  const client = new MongoClient(env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
  });
  await client.connect();
  const dbName = new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
  const db = client.db(dbName);
  let user;
  if (process.env.VIVENTIUM_QA_USER_HASH) {
    const expectedHash = process.env.VIVENTIUM_QA_USER_HASH.trim().toLowerCase();
    const candidates = await db.collection("users").find({}).toArray();
    user = candidates.find((candidate) => shortHash(candidate._id) === expectedHash);
  } else {
    const selector = process.env.VIVENTIUM_QA_USER_NAME ? { name: process.env.VIVENTIUM_QA_USER_NAME.trim() } : { email: process.env.VIVENTIUM_QA_EMAIL.trim().toLowerCase() };
    user = await db.collection("users").findOne(selector);
  }
  if (!user?._id || String(user.role || "").toUpperCase() === "ADMIN") {
    await client.close();
    throw new Error("Configured non-admin QA user was not found");
  }
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign({ id: user._id.toString(), sessionId: sessionId.toString() }, env.JWT_REFRESH_SECRET, { expiresIn: 7200 });
  const accessToken = jwt.sign(
    {
      id: user._id.toString(),
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
    refreshTokenHash: crypto.createHash("sha256").update(refreshToken).digest("hex"),
  });
  return { accessToken, client, db, refreshToken, sessionId, user };
}

function authCookies(auth) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  return [API_BASE, CLIENT_BASE].flatMap((url) => [
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
  ]);
}

async function installAccessToken(page, fallbackToken) {
  const refreshed = await page.evaluate(async () => {
    const response = await fetch("/api/auth/refresh", { method: "POST" });
    const body = await response.json().catch(() => ({}));
    return { token: typeof body?.token === "string" ? body.token : "" };
  });
  const token = refreshed.token || fallbackToken;
  if (!token) throw new Error("Unable to establish browser QA auth");
  await page.evaluate((value) => {
    localStorage.setItem("token", value);
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: value }));
  }, token);
}

async function api(accessToken, method, pathname, body) {
  const response = await fetch(`${API_BASE}${pathname}`, {
    method,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const rawPayload = await response.text();
  let payload = {};
  try {
    payload = rawPayload ? JSON.parse(rawPayload) : {};
  } catch {
    throw new Error(`${method} ${pathname} returned non-JSON content (${response.headers.get("content-type") || "unknown"}, bytes=${rawPayload.length}, body=${publicError(rawPayload)})`);
  }
  if (!response.ok) throw new Error(`${method} ${pathname} returned HTTP ${response.status}`);
  return payload;
}

async function openAgentBuilder(page) {
  const agentBuilder = page.getByRole("button", { name: "Agent Builder" });
  if (!(await agentBuilder.isVisible().catch(() => false))) {
    await page.locator("#toggle-right-nav").click();
  }
  await agentBuilder.waitFor({ state: "visible", timeout: 30000 });
  if ((await agentBuilder.getAttribute("data-state")) !== "open") await agentBuilder.click();
  await page.getByRole("combobox", { name: "Agent" }).first().waitFor({ state: "visible", timeout: 30000 });
}

async function selectAgent(page, name) {
  const select = page.getByRole("combobox", { name: "Agent" }).first();
  await select.click();
  const search = page.locator('input[placeholder="Search agents by name"]:visible').last();
  if (await search.isVisible().catch(() => false)) {
    await search.fill(name);
  } else {
    const focusedInput = page.locator("input:focus");
    if (await focusedInput.isVisible().catch(() => false)) {
      await focusedInput.fill(name);
    }
  }
  const namedOption = page.getByRole("option", { name, exact: true }).last();
  if (!(await namedOption.isVisible().catch(() => false))) {
    const visibleOptionCount = await page.locator('[role="option"]:visible').count();
    const visibleListboxCount = await page.locator('[role="listbox"]:visible').count();
    throw new Error(`Agent option unavailable after search (options=${visibleOptionCount}, listboxes=${visibleListboxCount})`);
  }
  await namedOption.waitFor({ state: "visible", timeout: 30000 });
  await namedOption.click();
  await page.getByRole("textbox", { name: "Agent name" }).waitFor({ state: "visible" });
  await page.waitForFunction((expected) => document.querySelector('input[aria-label="Agent name"]')?.value === expected, name);
}

async function pickCombobox(page, ariaName, optionText) {
  const select = page.getByRole("combobox", { name: ariaName, exact: true });
  await select.click();
  const search = page.locator(ariaName === "Provider" ? 'input[placeholder="Search provider by name"]:visible' : 'input[placeholder="Select a model"]:visible');
  if (await search.isVisible().catch(() => false)) await search.fill(optionText);
  const namedOption = page.getByRole("option", { name: optionText, exact: true }).last();
  if (!(await namedOption.isVisible().catch(() => false))) {
    const visibleLabels = await page.locator('[role="option"]:visible').allInnerTexts();
    const providerText = await page
      .getByRole("combobox", { name: "Provider", exact: true })
      .innerText()
      .catch(() => "unavailable");
    const modelDisabled = await page
      .getByRole("combobox", { name: "Model", exact: true })
      .isDisabled()
      .catch(() => true);
    const visibleComboboxLabels = await page.locator('[role="combobox"]:visible').evaluateAll((elements) => elements.map((element) => element.getAttribute("aria-label") || "unlabelled"));
    throw new Error(
      `${ariaName} option unavailable after search (options=${visibleLabels
        .map((value) => value.trim())
        .filter(Boolean)
        .join("|")}, provider=${providerText.trim()}, model_disabled=${modelDisabled}, comboboxes=${visibleComboboxLabels.join("|")}, path=${new URL(page.url()).pathname})`,
    );
  }
  await namedOption.waitFor({ state: "visible", timeout: 30000 });
  await namedOption.click();
}

function capabilityControls(page, parameterField = "model_parameters") {
  const legacyPrefix = parameterField === "model_parameters" ? "#glasshive" : "#unused-legacy";
  return {
    workspace: page
      .locator(`#${parameterField}-glasshive-workspace-mode, ${legacyPrefix}-workspace-mode`)
      .first(),
    access: page
      .locator(`#${parameterField}-glasshive-access, ${legacyPrefix}-access`)
      .first(),
    effort: page.locator(`#${parameterField}-effort, ${legacyPrefix}-effort`).first(),
  };
}

async function configureGlassHiveAgent(page, name, modelLabel, modelId, effort) {
  await selectAgent(page, name);
  const modelButton = page.locator('label[for="provider"]').locator("..").getByRole("button");
  await modelButton.click();
  await pickCombobox(page, "Provider", "GlassHive");
  await pickCombobox(page, "Model", modelLabel);
  const readiness = page.getByText(/^(Authenticated and ready|Sign-in required|Checking…|Unavailable)$/).last();
  await readiness.waitFor({ timeout: 30000 });
  await page.waitForFunction(() => Array.from(document.querySelectorAll("body *")).some((element) => ["Authenticated and ready", "Sign-in required", "Unavailable"].includes(String(element.textContent || "").trim())), undefined, { timeout: 30000 });
  const readinessText = (await readiness.innerText()).trim();
  if (readinessText !== "Authenticated and ready") {
    throw new Error(`GlassHive readiness was ${readinessText}`);
  }
  const controls = capabilityControls(page);
  const initial = {
    workspace: await controls.workspace.inputValue(),
    access: await controls.access.inputValue(),
    effort: await controls.effort.inputValue(),
  };
  await controls.access.selectOption("workspace");
  await controls.effort.selectOption(effort);
  await page.getByRole("button", { name: /Back to builder/i }).click();
  const saveResponse = page.waitForResponse((response) => response.request().method() === "PATCH" && /\/api\/agents\//.test(response.url()), { timeout: 30000 });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const saved = await saveResponse;
  if (!saved.ok()) throw new Error(`Agent Builder save returned HTTP ${saved.status()}`);
  await page.reload({ waitUntil: "domcontentloaded" });
  await installAccessToken(page, "");
  await openAgentBuilder(page);
  await selectAgent(page, name);
  await page.locator('label[for="provider"]').locator("..").getByRole("button").click();
  const persistedReadiness = page.getByText("Authenticated and ready", {
    exact: true,
  });
  await persistedReadiness.waitFor({ state: "visible", timeout: 30000 });
  const persistedControls = capabilityControls(page);
  const persisted = {
    provider: await page.getByRole("combobox", { name: "Provider", exact: true }).innerText(),
    model: await page.getByRole("combobox", { name: "Model", exact: true }).innerText(),
    workspace: await persistedControls.workspace.inputValue(),
    access: await persistedControls.access.inputValue(),
    effort: await persistedControls.effort.inputValue(),
    ready: await persistedReadiness.isVisible(),
  };
  await page.getByRole("button", { name: /Back to builder/i }).click();
  return {
    defaultsCorrect: initial.workspace === "life" && initial.access === "full",
    persisted: persisted.provider.includes("GlassHive") && persisted.model.includes(modelLabel) && persisted.workspace === "life" && persisted.access === "workspace" && persisted.effort === effort && persisted.ready,
    persistenceEvidence: persisted,
    modelId,
  };
}

async function configureGlassHiveFallback(page, name) {
  await selectAgent(page, name);
  await page.locator('label[for="provider"]').locator("..").getByRole("button").click();
  await page.locator('button[aria-labelledby="fallback-llm-label"]').click();
  await pickCombobox(page, "Provider", "GlassHive");
  await pickCombobox(page, "Model", "Claude / Opus 5");
  const readiness = page.getByText("Authenticated and ready", { exact: true });
  await readiness.waitFor({ state: "visible", timeout: 30000 });
  const controls = capabilityControls(page, "fallback_llm_model_parameters");
  await controls.effort.selectOption("high");
  const configured = {
    provider: await page.getByRole("combobox", { name: "Provider", exact: true }).innerText(),
    model: await page.getByRole("combobox", { name: "Model", exact: true }).innerText(),
    effort: await controls.effort.inputValue(),
    ready: await readiness.isVisible(),
  };
  await page.getByRole("button", { name: /Back to builder/i }).click();
  await page.getByRole("button", { name: /Back to builder/i }).click();
  const saveResponse = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && /\/api\/agents\//.test(response.url()),
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const saved = await saveResponse;
  if (!saved.ok()) throw new Error(`Agent Builder fallback save returned HTTP ${saved.status()}`);

  await page.reload({ waitUntil: "domcontentloaded" });
  await installAccessToken(page, "");
  await openAgentBuilder(page);
  await selectAgent(page, name);
  await page.locator('label[for="provider"]').locator("..").getByRole("button").click();
  await page.locator('button[aria-labelledby="fallback-llm-label"]').click();
  const persistedReadiness = page.getByText("Authenticated and ready", { exact: true });
  await persistedReadiness.waitFor({ state: "visible", timeout: 30000 });
  const persistedControls = capabilityControls(page, "fallback_llm_model_parameters");
  const persisted = {
    provider: await page.getByRole("combobox", { name: "Provider", exact: true }).innerText(),
    model: await page.getByRole("combobox", { name: "Model", exact: true }).innerText(),
    effort: await persistedControls.effort.inputValue(),
    ready: await persistedReadiness.isVisible(),
  };
  await page.getByRole("button", { name: /Back to builder/i }).click();
  await page.getByRole("button", { name: /Back to builder/i }).click();
  return {
    visible:
      configured.provider.includes("GlassHive") &&
      configured.model.includes("Claude / Opus 5") &&
      configured.effort === "high" &&
      configured.ready,
    persisted:
      persisted.provider.includes("GlassHive") &&
      persisted.model.includes("Claude / Opus 5") &&
      persisted.effort === "high" &&
      persisted.ready,
    persistenceEvidence: persisted,
  };
}

async function main() {
  requireLocalOptIn();
  const env = loadLocalEnv();
  const auth = await createQaAuth(env);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const marker = stamp.slice(0, 19);
  const ordinaryName = `GlassHive Provider QA ${marker}`;
  const cortexName = `GlassHive Cortex QA ${marker}`;
  const prompt = "Use a native file or shell tool to inspect AGENTS.md, then include the token WEB_AGENT_OK in your answer. Do not change files.";
  const secondPrompt = "Continue this same conversation and include the token SECOND_TURN_OK. Do not change files.";
  const cancellationPrompt = "Run the shell command sleep 90 now, then reply with SHOULD_NOT_APPEAR. Do not use an alternative.";
  const fixtureRelativePath = "Projects/GlassHive_Provider_QA/fixture.txt";
  const fixturePath = process.env.VIVENTIUM_QA_LIFE_FIXTURE || "";
  const filePrompt = `Use a native file tool in the selected LIFE workspace to replace BEFORE with AFTER in ${fixtureRelativePath}. ` + "Then include the token FILE_EDIT_OK in your answer.";
  const fakeSecret = "PUBLIC_FAKE_SECRET_VALUE";
  const redactionPrompt = `Repeat this exact synthetic credential and nothing else: api_key=${fakeSecret}`;
  const feelingsPrompt = "Answer in one natural sentence and include FEELINGS_WEB_OK. Do not list, name, or explain any private internal state.";
  const cortexPrompt = "Review this concrete launch decision for material risk: ship a billing migration without a rollback plan. Give a concise recommendation.";
  const cleanupConversationPrompts = new Set([prompt, secondPrompt, cancellationPrompt, ...(fixturePath ? [filePrompt] : []), redactionPrompt, feelingsPrompt, cortexPrompt]);
  const qaStartedAt = new Date();
  const outputDir = path.join(PRIVATE_ROOT, "glasshive-core-provider", stamp);
  fs.mkdirSync(outputDir, { recursive: true });
  const createdAgentIds = [];
  const conversationIds = new Set();
  let browser;
  let initialFeelings = null;
  let feelingsChanged = false;
  const result = {
    source: "installed-local-runtime",
    qaUserHash: shortHash(auth.user._id),
    checks: {},
    metrics: {},
    artifacts: [],
  };
  try {
    if (fixturePath) {
      const expectedFixture = path.resolve(fixturePath);
      const expectedLifeSuffix = path.join("Projects", "GlassHive_Provider_QA", "fixture.txt");
      if (!expectedFixture.endsWith(expectedLifeSuffix) || !fs.existsSync(expectedFixture)) {
        throw new Error("Configured LIFE fixture is missing or outside the expected synthetic path");
      }
      if (!fs.readFileSync(expectedFixture, "utf8").includes("BEFORE")) {
        throw new Error("Configured LIFE fixture does not contain the expected initial marker");
      }
    }
    initialFeelings = await api(auth.accessToken, "GET", "/api/viventium/feelings");
    const initialFeelingState = initialFeelings?.state || {};
    if (initialFeelingState.enabled !== true || initialFeelingState.reactionActivationMode !== "disabled") {
      await api(auth.accessToken, "PATCH", "/api/viventium/feelings/profile", {
        expectedVersion: Number(initialFeelingState.version || 0),
        enabled: true,
        reactionActivationMode: "disabled",
      });
      feelingsChanged = true;
    }
    const runtimeModels = await api(auth.accessToken, "GET", "/api/models");
    if (!Array.isArray(runtimeModels["glasshive-harness"])) {
      throw new Error(`GlassHive runtime model catalog missing (providers=${Object.keys(runtimeModels).sort().join(",")})`);
    }
    const providerReadiness = await api(auth.accessToken, "GET", "/api/agents/provider-readiness/glasshive-harness");
    if (providerReadiness.status !== "ready") {
      throw new Error(`GlassHive authenticated readiness was ${providerReadiness.status || "missing"}: ${providerReadiness.detail || "no detail"}`);
    }
    for (const [name, description] of [
      [ordinaryName, "Synthetic ordinary-agent provider QA"],
      [cortexName, "Synthetic cortex-agent provider QA"],
    ]) {
      const agent = await api(auth.accessToken, "POST", "/api/agents", {
        name,
        description,
        instructions: "Answer concisely and follow the visible user request.",
        provider: "openAI",
        model: "gpt-5.6-terra",
        category: "general",
        tools: [],
      });
      if (typeof agent.id !== "string" || !agent.id) {
        throw new Error(`Create-agent response omitted id (keys=${Object.keys(agent).sort().join(",")})`);
      }
      createdAgentIds.push(agent.id);
    }
    const listedAgents = await api(auth.accessToken, "GET", "/api/agents?requiredPermission=2&limit=100");
    if (!createdAgentIds.every((id) => listedAgents.data?.some((agent) => agent.id === id))) {
      const createdDocs = await auth.db
        .collection("agents")
        .find({ id: { $in: createdAgentIds } }, { projection: { _id: 1 } })
        .toArray();
      const ownerAclCount = await auth.db.collection("aclentries").countDocuments({
        resourceType: "agent",
        resourceId: { $in: createdDocs.map((agent) => agent._id) },
        principalId: auth.user._id,
      });
      throw new Error(`Synthetic agents were not returned by the supported editable-agent list (documents=${createdDocs.length}, owner_acl=${ownerAclCount})`);
    }

    const { chromium } = require(path.join(LIBRECHAT_ROOT, "node_modules", "playwright"));
    browser = await chromium.launch({ channel: "chrome", headless: !HEADED });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    });
    await context.addCookies(authCookies(auth));
    await context.addInitScript(() => {
      localStorage.setItem("fullPanelCollapse", "false");
      localStorage.setItem("react-resizable-panels:collapsed", "false");
      localStorage.setItem("side:active-panel", "agents");
    });
    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    const consoleErrors = [];
    const criticalHttpErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(shortHash(message.text()));
        console.error(JSON.stringify({ browserConsoleError: publicError(message.text()) }));
      }
    });
    page.on("pageerror", (error) => {
      consoleErrors.push(shortHash(error?.message));
      console.error(JSON.stringify({ browserPageError: publicError(error?.message) }));
    });
    page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname;
      if (response.status() >= 400 && /\/api\/(agents|models|auth\/refresh)/.test(pathname)) {
        criticalHttpErrors.push(`${response.status()} ${pathname}`);
      }
    });

    await page.goto(`${CLIENT_BASE}/c/new`, { waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    await openAgentBuilder(page);
    const ordinary = await configureGlassHiveAgent(page, ordinaryName, "Codex / GPT-5.6 Sol", "codex-cli:gpt-5.6-sol", "medium");
    const cortex = await configureGlassHiveAgent(page, cortexName, "Claude / Opus 5", "claude-code:opus", "max");
    const fallback = await configureGlassHiveFallback(page, ordinaryName);

    await selectAgent(page, ordinaryName);
    await page.getByRole("button", { name: /^Select (an )?agent$/i }).click();
    const input = page
      .getByLabel("Message input")
      .or(page.getByPlaceholder(/^Message Viventium$/))
      .last();
    await input.waitFor({ state: "visible", timeout: 30000 });
    await input.fill(prompt);
    const startedAt = new Date();
    await page.getByTestId("send-button").last().click();
    const assistantTurn = page.locator(".agent-turn").filter({ hasText: "WEB_AGENT_OK" }).last();
    await assistantTurn.waitFor({ state: "visible", timeout: 180000 });
    await assistantTurn.getByText("Harness activity", { exact: true }).last().waitFor({ state: "visible" });
    await input.fill(secondPrompt);
    await page.getByTestId("send-button").last().click();
    const secondAssistantTurn = page.locator(".agent-turn").filter({ hasText: "SECOND_TURN_OK" }).last();
    await secondAssistantTurn.waitFor({ state: "visible", timeout: 180000 });
    await secondAssistantTurn.getByText("Harness activity", { exact: true }).last().waitFor({ state: "visible" });
    let fileAssistantTurn = null;
    if (fixturePath) {
      await input.fill(filePrompt);
      await page.getByTestId("send-button").last().click();
      fileAssistantTurn = page.locator(".agent-turn").filter({ hasText: "FILE_EDIT_OK" }).last();
      await fileAssistantTurn.waitFor({ state: "visible", timeout: 180000 });
      await fileAssistantTurn.getByText("Harness activity", { exact: true }).last().waitFor({ state: "visible" });
    }
    const turnCountBeforeRedaction = await page.locator(".agent-turn").count();
    await input.fill(redactionPrompt);
    await page.getByTestId("send-button").last().click();
    await page.waitForFunction((priorCount) => document.querySelectorAll(".agent-turn").length > priorCount, turnCountBeforeRedaction, { timeout: 30000 });
    const redactionAssistantTurn = page.locator(".agent-turn").nth(turnCountBeforeRedaction);
    await redactionAssistantTurn.getByText("Harness activity", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    await page.waitForFunction(
      ({ index, forbidden }) => {
        const turn = document.querySelectorAll(".agent-turn")[index];
        const text = String(turn?.textContent || "");
        return text.includes("[REDACTED]") && !text.includes(forbidden);
      },
      { index: turnCountBeforeRedaction, forbidden: fakeSecret },
      { timeout: 180000 },
    );
    const redactionAssistantText = await redactionAssistantTurn.innerText();
    await input.fill(feelingsPrompt);
    await page.getByTestId("send-button").last().click();
    const feelingsAssistantTurn = page.locator(".agent-turn").filter({ hasText: "FEELINGS_WEB_OK" }).last();
    await feelingsAssistantTurn.waitFor({ state: "visible", timeout: 180000 });
    await feelingsAssistantTurn.getByText("Harness activity", { exact: true }).last().waitFor({ state: "visible" });
    const turnCountBeforeCancellation = await page.locator(".agent-turn").count();
    await input.fill(cancellationPrompt);
    await page.getByTestId("send-button").last().click();
    await page.waitForFunction((priorCount) => document.querySelectorAll(".agent-turn").length > priorCount, turnCountBeforeCancellation, { timeout: 30000 });
    const cancelledAssistantTurn = page.locator(".agent-turn").nth(turnCountBeforeCancellation);
    const cancelledActivity = cancelledAssistantTurn.getByText("Harness activity", { exact: true });
    await cancelledActivity.waitFor({ state: "visible", timeout: 30000 });
    await cancelledActivity.click();
    await cancelledAssistantTurn.getByText("The harness started working.", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
    const stopButton = page.getByRole("button", { name: "Stop generating", exact: true }).last();
    await stopButton.waitFor({ state: "visible", timeout: 30000 });
    await stopButton.click();
    await stopButton.waitFor({ state: "hidden", timeout: 30000 });
    const cancelledUserMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        isCreatedByUser: true,
        text: cancellationPrompt,
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    let cancelledAssistantMessage = cancelledUserMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: cancelledUserMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: cancelledUserMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    await page.reload({ waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    if (cancelledUserMessage) {
      cancelledAssistantMessage = await auth.db.collection("messages").findOne(
        {
          user: String(auth.user._id),
          conversationId: cancelledUserMessage.conversationId,
          isCreatedByUser: false,
          parentMessageId: cancelledUserMessage.messageId,
        },
        { sort: { createdAt: -1, _id: -1 } },
      );
    }
    const cancellationActivitySurvivedRefresh = await cancelledActivity.isVisible().catch(() => false);
    let cancellationSummarySurvivedRefresh = false;
    if (cancellationActivitySurvivedRefresh) {
      await cancelledActivity.click();
      cancellationSummarySurvivedRefresh = await cancelledAssistantTurn
        .getByText("The harness turn was cancelled.", { exact: true })
        .isVisible()
        .catch(() => false);
    }

    const mainProviderStateBeforeCortex = cancelledUserMessage?.conversationId
      ? providerStateFor(env, {
          ownerId: String(auth.user._id),
          conversationId: String(cancelledUserMessage.conversationId),
          agentId: createdAgentIds[0],
        })
      : null;
    await api(auth.accessToken, "PATCH", `/api/agents/${encodeURIComponent(createdAgentIds[0])}`, {
      background_cortices: [
        {
          agent_id: createdAgentIds[1],
          activation: {
            enabled: true,
            provider: "groq",
            model: "qwen/qwen3.6-27b",
            prompt: "Activate only when the latest user message asks for a material risk review of a concrete launch decision. Return the configured JSON activation object and no other text.",
            confidence_threshold: 0.5,
            cooldown_ms: 0,
            max_history: 6,
          },
        },
      ],
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    const cortexInput = page
      .getByLabel("Message input")
      .or(page.getByPlaceholder(/^Message Viventium$/))
      .last();
    await cortexInput.waitFor({ state: "visible", timeout: 30000 });
    await cortexInput.fill(cortexPrompt);
    await page.getByTestId("send-button").last().click();
    await page.getByText(cortexName, { exact: true }).last().waitFor({
      state: "visible",
      timeout: 180000,
    });
    const cortexUserMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        isCreatedByUser: true,
        text: cortexPrompt,
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    let cortexParentMessage = null;
    let phaseBMessages = [];
    let phaseBProviderState = null;
    const cortexEvidenceDeadline = Date.now() + 180000;
    while (Date.now() < cortexEvidenceDeadline && cortexUserMessage) {
      cortexParentMessage = await auth.db.collection("messages").findOne(
        {
          user: String(auth.user._id),
          conversationId: cortexUserMessage.conversationId,
          isCreatedByUser: false,
          parentMessageId: cortexUserMessage.messageId,
        },
        { sort: { createdAt: -1, _id: -1 } },
      );
      phaseBMessages = await auth.db
        .collection("messages")
        .find({
          user: String(auth.user._id),
          conversationId: cortexUserMessage.conversationId,
          "metadata.viventium.type": "cortex_followup",
          createdAt: { $gte: cortexUserMessage.createdAt },
        })
        .toArray();
      phaseBProviderState = providerStateFor(env, {
        ownerId: String(auth.user._id),
        conversationId: cortexUserMessage.conversationId,
        agentId: createdAgentIds[0],
      });
      const parts = Array.isArray(cortexParentMessage?.content) ? cortexParentMessage.content : [];
      if (
        parts.some(
          (part) =>
            part?.type === "cortex_insight" &&
            String(part?.status || "") === "complete",
        ) &&
        completedRequestDelta(
          phaseBProviderState,
          mainProviderStateBeforeCortex,
        ) >= 2
      ) {
        break;
      }
      await page.waitForTimeout(1000);
    }
    await page.reload({ waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    const cortexCardVisibleAfterRefresh = await page
      .getByText(cortexName, { exact: true })
      .last()
      .isVisible()
      .catch(() => false);
    const visibleScreenshot = path.join(outputDir, "agent-builder-and-chat.png");
    await page.screenshot({ path: visibleScreenshot, fullPage: true });
    result.artifacts.push(path.basename(visibleScreenshot));

    const userMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: new Date(startedAt.getTime() - 5000) },
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    if (userMessage?.conversationId) conversationIds.add(String(userMessage.conversationId));
    const assistantMessage = userMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: userMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: userMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const conversation = userMessage?.conversationId
      ? await auth.db.collection("conversations").findOne({
          user: String(auth.user._id),
          conversationId: userMessage.conversationId,
        })
      : null;
    const secondUserMessage = userMessage?.conversationId
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: userMessage.conversationId,
            isCreatedByUser: true,
            text: secondPrompt,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const secondAssistantMessage = secondUserMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: secondUserMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: secondUserMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const fileUserMessage = fixturePath
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: userMessage?.conversationId,
            isCreatedByUser: true,
            text: filePrompt,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const fileAssistantMessage = fileUserMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: fileUserMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: fileUserMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const redactionUserMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        conversationId: userMessage?.conversationId,
        isCreatedByUser: true,
        text: redactionPrompt,
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    const redactionAssistantMessage = redactionUserMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: redactionUserMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: redactionUserMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const feelingsUserMessage = await auth.db.collection("messages").findOne(
      {
        user: String(auth.user._id),
        conversationId: userMessage?.conversationId,
        isCreatedByUser: true,
        text: feelingsPrompt,
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    const feelingsAssistantMessage = feelingsUserMessage
      ? await auth.db.collection("messages").findOne(
          {
            user: String(auth.user._id),
            conversationId: feelingsUserMessage.conversationId,
            isCreatedByUser: false,
            parentMessageId: feelingsUserMessage.messageId,
          },
          { sort: { createdAt: -1, _id: -1 } },
        )
      : null;
    const providerState = userMessage?.conversationId
      ? providerStateFor(env, {
          ownerId: String(auth.user._id),
          conversationId: String(userMessage.conversationId),
          agentId: createdAgentIds[0],
        })
      : null;
    const feelingsProviderRequest =
      feelingsUserMessage?.conversationId && feelingsAssistantMessage?.messageId
        ? providerRequestEvidence(env, {
            ownerId: String(auth.user._id),
            conversationId: String(feelingsUserMessage.conversationId),
            agentId: createdAgentIds[0],
            messageId: String(feelingsAssistantMessage.messageId),
          })
        : null;
    const redactionProviderRequest =
      redactionUserMessage?.conversationId && redactionAssistantMessage?.messageId
        ? providerRequestEvidence(env, {
            ownerId: String(auth.user._id),
            conversationId: String(redactionUserMessage.conversationId),
            agentId: createdAgentIds[0],
            messageId: String(redactionAssistantMessage.messageId),
          })
        : null;
    const cortexProviderState = cortexUserMessage?.conversationId
      ? providerStateFor(env, {
          ownerId: String(auth.user._id),
          conversationId: String(cortexUserMessage.conversationId),
          agentId: createdAgentIds[1],
        })
      : null;
    const cortexProviderRequest = cortexUserMessage?.conversationId
      ? providerRequestEvidence(env, {
          ownerId: String(auth.user._id),
          conversationId: String(cortexUserMessage.conversationId),
          agentId: createdAgentIds[1],
        })
      : null;
    const phaseBProviderRequest = cortexUserMessage?.conversationId
      ? providerRequestEvidence(env, {
          ownerId: String(auth.user._id),
          conversationId: String(cortexUserMessage.conversationId),
          agentId: createdAgentIds[0],
        })
      : null;
    const cortexParts = Array.isArray(cortexParentMessage?.content) ? cortexParentMessage.content.filter((part) => String(part?.type || "").startsWith("cortex_")) : [];
    const savedAgents = await auth.db
      .collection("agents")
      .find({ id: { $in: createdAgentIds } })
      .toArray();
    const savedById = new Map(savedAgents.map((agent) => [agent.id, agent]));

    await page.reload({ waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    if (assistantMessage?.messageId) {
      await page.locator(`[id="${assistantMessage.messageId}"]`).waitFor({
        state: "visible",
        timeout: 30000,
      });
    }
    const visibleUiErrors = await visibleUiErrorLabels(page);
    // The memory writer is an intentionally separate direct-provider auxiliary. A synthetic QA
    // account without that provider credential may surface its own honest degraded-state card;
    // keep it in evidence, but do not misclassify it as a GlassHive endpoint failure.
    const endpointUiErrors = visibleUiErrors.filter((label) => label.toLowerCase() !== "memory error");
    const redactionPersistedText = authoredAssistantText(redactionAssistantMessage);
    const redactionProviderOutput = [redactionProviderRequest?.output_text, redactionProviderRequest?.response_json, redactionProviderRequest?.activity_text].join("\n");
    const feelingsProviderOutput = [feelingsProviderRequest?.output_text, feelingsProviderRequest?.response_json, feelingsProviderRequest?.activity_text].join("\n");
    const lifeRoot = fixturePath ? path.resolve(fixturePath, "..", "..", "..") : env.VIVENTIUM_LIFE_DIR;
    result.checks = {
      ordinaryDefaultsVisible: ordinary.defaultsCorrect,
      ordinarySaveReloadPersistence: ordinary.persisted,
      cortexSaveReloadPersistence: cortex.persisted,
      fallbackOpusHighVisible: fallback.visible,
      fallbackOpusHighSaveReloadPersistence: fallback.persisted,
      ordinaryMongoRoundTrip: savedById.get(createdAgentIds[0])?.provider === "glasshive-harness" && savedById.get(createdAgentIds[0])?.model === ordinary.modelId && savedById.get(createdAgentIds[0])?.glasshive_options?.workspace?.mode === "life" && savedById.get(createdAgentIds[0])?.glasshive_options?.access === "workspace" && savedById.get(createdAgentIds[0])?.model_parameters?.reasoning_effort === "medium" && savedById.get(createdAgentIds[0])?.fallback_llm_provider === "glasshive-harness" && savedById.get(createdAgentIds[0])?.fallback_llm_model === "claude-code:opus" && savedById.get(createdAgentIds[0])?.fallback_llm_model_parameters?.reasoning_effort === "high",
      cortexMongoRoundTrip: savedById.get(createdAgentIds[1])?.provider === "glasshive-harness" && savedById.get(createdAgentIds[1])?.model === cortex.modelId && savedById.get(createdAgentIds[1])?.glasshive_options?.access === "workspace" && savedById.get(createdAgentIds[1])?.model_parameters?.reasoning_effort === "max",
      versionCreated: savedAgents.every((agent) => Array.isArray(agent.versions) && agent.versions.length > 0),
      browserHarnessAnswerVisible: await page.locator(".agent-turn").filter({ hasText: "WEB_AGENT_OK" }).last().isVisible(),
      browserHarnessActivityVisible: await page.locator(".agent-turn").filter({ hasText: "WEB_AGENT_OK" }).last().getByText("Harness activity", { exact: true }).last().isVisible(),
      secondTurnVisible: await page.locator(".agent-turn").filter({ hasText: "SECOND_TURN_OK" }).last().isVisible(),
      secondTurnActivityVisible: await page.locator(".agent-turn").filter({ hasText: "SECOND_TURN_OK" }).last().getByText("Harness activity", { exact: true }).last().isVisible(),
      nativeFileEditVisible: !fixturePath || (Boolean(fileAssistantTurn) && (await fileAssistantTurn.isVisible().catch(() => false))),
      nativeFileEditPersisted: !fixturePath || (Boolean(fileAssistantMessage) && fs.readFileSync(fixturePath, "utf8").includes("AFTER") && !fs.readFileSync(fixturePath, "utf8").includes("BEFORE")),
      streamRedactionVisible: redactionAssistantText.includes("[REDACTED]") && !redactionAssistantText.includes(fakeSecret),
      streamRedactionPersisted: redactionPersistedText.includes("[REDACTED]") && !redactionPersistedText.includes(fakeSecret) && !redactionProviderOutput.includes(fakeSecret),
      feelingsMainFrameExactlyOnce: Boolean(feelingsProviderRequest) && countOccurrences(feelingsProviderRequest.instruction, "<viventium_feeling_state>") === 1 && countOccurrences(feelingsProviderRequest.instruction, "</viventium_feeling_state>") === 1,
      feelingsPhaseBReusesMainSessionWithoutSecondFrame: Boolean(phaseBProviderRequest) && countOccurrences(phaseBProviderRequest.instruction, "<viventium_feeling_state>") === 0 && countOccurrences(phaseBProviderRequest.instruction, "</viventium_feeling_state>") === 0,
      feelingsExcludedFromSpecialistCortex: Boolean(cortexProviderRequest) && countOccurrences(cortexProviderRequest.instruction, "<viventium_feeling_state>") === 0,
      feelingsPrivateFromOutputActivityAndLife: Boolean(feelingsAssistantMessage) && !authoredAssistantText(feelingsAssistantMessage).includes("<viventium_feeling_state>") && !feelingsProviderOutput.includes("<viventium_feeling_state>") && !textTreeContains(lifeRoot, "<viventium_feeling_state>"),
      assistantPersisted: Boolean(assistantMessage),
      secondAssistantPersisted: Boolean(secondAssistantMessage),
      oneAssistantReply:
        userMessage &&
        (await auth.db.collection("messages").countDocuments({
          user: String(auth.user._id),
          conversationId: userMessage.conversationId,
          isCreatedByUser: false,
          parentMessageId: userMessage.messageId,
        })) === 1,
      oneSecondAssistantReply:
        secondUserMessage &&
        (await auth.db.collection("messages").countDocuments({
          user: String(auth.user._id),
          conversationId: secondUserMessage.conversationId,
          isCreatedByUser: false,
          parentMessageId: secondUserMessage.messageId,
        })) === 1,
      oneNativeSession: providerState?.session_count === 1,
      expectedMainRequestsBeforeCortex: mainProviderStateBeforeCortex?.request_count === (fixturePath ? 6 : 5) && mainProviderStateBeforeCortex?.completed_request_count === (fixturePath ? 5 : 4) && mainProviderStateBeforeCortex?.cancelled_request_count === 1,
      cancelledAssistantPersisted: Boolean(cancelledAssistantMessage),
      explicitCancellationVisible: cancellationActivitySurvivedRefresh && cancellationSummarySurvivedRefresh,
      cancelledAnswerNotAuthored: cancelledAssistantMessage?.unfinished === true && !authoredAssistantText(cancelledAssistantMessage).includes("SHOULD_NOT_APPEAR"),
      completeVisibleHistoryRetained: Number(providerState?.history_count || 0) >= 3,
      cortexCardVisibleAfterRefresh,
      phaseAActivationProducedVisibleCortex: cortexCardVisibleAfterRefresh && cortexParts.some((part) => part?.type === "cortex_insight" && String(part?.status || "") === "complete"),
      cortexInsightPersisted: cortexParts.some((part) => part?.type === "cortex_insight" && String(part?.status || "") === "complete"),
      cortexUsesClaudeGlassHiveSession: cortexProviderState?.session_count === 1 && cortexProviderState?.completed_request_count >= 1,
      phaseBResolvedOnMainGlassHiveSession:
        providerState?.session_count === 1 &&
        phaseBMessages.length <= 1 &&
        completedRequestDelta(providerState, mainProviderStateBeforeCortex) >= 2,
      conversationTitleGenerated: typeof conversation?.title === "string" && conversation.title.trim().length > 0 && conversation?.title !== prompt,
      noEndpointUiErrors: endpointUiErrors.length === 0,
      noConsoleErrors: consoleErrors.length === 0,
      noCriticalHttpErrors: criticalHttpErrors.length === 0,
    };
    result.metrics = {
      configuredAgentCount: savedAgents.length,
      conversationCount: conversationIds.size,
      consoleErrorCount: consoleErrors.length,
      criticalHttpErrorCount: criticalHttpErrors.length,
      visibleUiErrors,
      endpointUiErrors,
      conversationTitleGenerated: result.checks.conversationTitleGenerated,
      ordinaryPersistenceEvidence: ordinary.persistenceEvidence,
      cortexPersistenceEvidence: cortex.persistenceEvidence,
      fallbackPersistenceEvidence: fallback.persistenceEvidence,
      providerState: providerState
        ? {
            sessionCount: providerState.session_count,
            requestCount: providerState.request_count,
            completedRequestCount: providerState.completed_request_count,
            cancelledRequestCount: providerState.cancelled_request_count,
            historyCount: providerState.history_count,
          }
        : null,
      cortexProviderState: cortexProviderState
        ? {
            sessionCount: cortexProviderState.session_count,
            requestCount: cortexProviderState.request_count,
            completedRequestCount: cortexProviderState.completed_request_count,
            cancelledRequestCount: cortexProviderState.cancelled_request_count,
            historyCount: cortexProviderState.history_count,
          }
        : null,
      phaseBEvidence: {
        messageCount: phaseBMessages.length,
        outcome: phaseBMessages.length === 1 ? "persisted" : "suppressed",
        parentCortexPartTypes: cortexParts.map((part) => String(part?.type || "unknown")),
        mainCompletedBefore: Number(mainProviderStateBeforeCortex?.completed_request_count || 0),
        mainCompletedAfter: Number(providerState?.completed_request_count || 0),
      },
      cancellationPersistenceEvidence: {
        assistantPersisted: Boolean(cancelledAssistantMessage),
        unfinished: cancelledAssistantMessage?.unfinished === true,
        contentPartTypes: Array.isArray(cancelledAssistantMessage?.content) ? cancelledAssistantMessage.content.map((part) => String(part?.type || "unknown")) : [],
        activitySurvivedRefresh: cancellationActivitySurvivedRefresh,
        summarySurvivedRefresh: cancellationSummarySurvivedRefresh,
      },
      deepConversationEvidence: {
        nativeFileFixtureEnabled: Boolean(fixturePath),
        nativeFileChanged: Boolean(fixturePath) && fs.existsSync(fixturePath) && fs.readFileSync(fixturePath, "utf8").includes("AFTER"),
        redactionMarkerVisible: redactionAssistantText.includes("[REDACTED]"),
        redactionSecretVisibleOrPersisted: redactionAssistantText.includes(fakeSecret) || redactionPersistedText.includes(fakeSecret) || redactionProviderOutput.includes(fakeSecret),
        feelingsMainFrameCount: countOccurrences(feelingsProviderRequest?.instruction, "<viventium_feeling_state>"),
        feelingsPhaseBFrameCount: countOccurrences(phaseBProviderRequest?.instruction, "<viventium_feeling_state>"),
        feelingsSpecialistFrameCount: countOccurrences(cortexProviderRequest?.instruction, "<viventium_feeling_state>"),
        feelingsFrameFoundInLife: textTreeContains(lifeRoot, "<viventium_feeling_state>"),
      },
    };
    result.pass = Object.values(result.checks).every(Boolean);
    fs.writeFileSync(path.join(outputDir, "result.json"), `${JSON.stringify(result, null, 2)}\n`);
    console.log(JSON.stringify(result, null, 2));
    if (!result.pass) process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (feelingsChanged && initialFeelings?.state) {
      const currentFeelings = await api(auth.accessToken, "GET", "/api/viventium/feelings").catch(() => null);
      if (currentFeelings?.state) {
        await api(auth.accessToken, "PATCH", "/api/viventium/feelings/profile", {
          expectedVersion: Number(currentFeelings.state.version || 0),
          enabled: initialFeelings.state.enabled === true,
          reactionActivationMode: initialFeelings.state.reactionActivationMode || initialFeelings.config?.reaction?.activationMode || "always",
        }).catch(() => {});
      }
    }
    const syntheticMessages = await auth.db
      .collection("messages")
      .find(
        {
          user: String(auth.user._id),
          isCreatedByUser: true,
          text: { $in: [...cleanupConversationPrompts] },
          createdAt: { $gte: qaStartedAt },
        },
        { projection: { conversationId: 1 } },
      )
      .toArray()
      .catch(() => []);
    for (const message of syntheticMessages) {
      if (message?.conversationId) conversationIds.add(String(message.conversationId));
    }
    for (const conversationId of conversationIds) {
      await auth.db
        .collection("messages")
        .deleteMany({ user: String(auth.user._id), conversationId })
        .catch(() => {});
      await auth.db
        .collection("conversations")
        .deleteMany({ user: String(auth.user._id), conversationId })
        .catch(() => {});
    }
    for (const agentId of createdAgentIds) {
      await api(auth.accessToken, "DELETE", `/api/agents/${encodeURIComponent(agentId)}`).catch(() => {});
    }
    cleanupProviderState(env, {
      ownerId: String(auth.user._id),
      agentIds: createdAgentIds,
    });
    await auth.db
      .collection("sessions")
      .deleteOne({ _id: auth.sessionId })
      .catch(() => {});
    await auth.client.close(true).catch(() => {});
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      pass: false,
      errorClass: shortHash(error?.message),
      error: publicError(error?.message),
    }),
  );
  process.exitCode = 1;
});
