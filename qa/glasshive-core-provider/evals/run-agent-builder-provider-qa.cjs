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
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = (process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190").replace(/\/$/, "");
const API_BASE = (process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180").replace(/\/$/, "");
const PRIVATE_ROOT =
  process.env.VIVENTIUM_QA_PRIVATE_DIR ||
  path.join(os.homedir(), "Library", "Application Support", "Viventium", "private-user-data");
const HEADED = process.argv.includes("--headed");

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[line.slice(0, index).trim()] = value;
  }
  return values;
}

function loadLocalEnv() {
  const runtimeRoot = path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "runtime",
  );
  return [
    path.join(runtimeRoot, "runtime.env"),
    path.join(runtimeRoot, "runtime.local.env"),
    path.join(runtimeRoot, "service-env", "librechat.env"),
    path.join(LIBRECHAT_ROOT, ".env"),
  ].reduce((all, candidate) => Object.assign(all, parseEnvFile(candidate)), { ...process.env });
}

function shortHash(value, length = 12) {
  return crypto.createHash("sha256").update(String(value || "")).digest("hex").slice(0, length);
}

function publicError(value) {
  return String(value || "browser_qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/\s+/g, " ")
    .slice(0, 400);
}

function requireLocalOptIn() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("GlassHive Agent Builder QA is local-development only");
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error("Set VIVENTIUM_QA_ALLOW_LOCAL_JWT=1");
  }
  if (!process.env.VIVENTIUM_QA_EMAIL && !process.env.VIVENTIUM_QA_USER_NAME) {
    throw new Error("Set VIVENTIUM_QA_EMAIL or VIVENTIUM_QA_USER_NAME");
  }
}

async function createQaAuth(env) {
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("Missing local QA auth prerequisites");
  }
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"));
  const jwt = require(path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"));
  const client = new MongoClient(env.MONGO_URI, { serverSelectionTimeoutMS: 5000 });
  await client.connect();
  const dbName = new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
  const db = client.db(dbName);
  const selector = process.env.VIVENTIUM_QA_USER_NAME
    ? { name: process.env.VIVENTIUM_QA_USER_NAME.trim() }
    : { email: process.env.VIVENTIUM_QA_EMAIL.trim().toLowerCase() };
  const user = await db.collection("users").findOne(selector);
  if (!user?._id || String(user.role || "").toUpperCase() === "ADMIN") {
    await client.close();
    throw new Error("Configured non-admin QA user was not found");
  }
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: user._id.toString(), sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: 7200 },
  );
  const accessToken = jwt.sign(
    { id: user._id.toString(), username: user.username, provider: user.provider, email: user.email },
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
    { name: "refreshToken", value: auth.refreshToken, url, httpOnly: true, sameSite: "Strict", expires },
    { name: "token_provider", value: "librechat", url, httpOnly: true, sameSite: "Strict", expires },
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
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const rawPayload = await response.text();
  let payload = {};
  try {
    payload = rawPayload ? JSON.parse(rawPayload) : {};
  } catch {
    throw new Error(
      `${method} ${pathname} returned non-JSON content (${response.headers.get("content-type") || "unknown"}, bytes=${rawPayload.length}, body=${publicError(rawPayload)})`,
    );
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
  await page
    .getByRole("combobox", { name: "Agent" })
    .first()
    .waitFor({ state: "visible", timeout: 30000 });
}

async function selectAgent(page, name) {
  const select = page.getByRole("combobox", { name: "Agent" }).first();
  await select.click();
  const search = page.locator('input[placeholder="Search agents by name"]:visible').last();
  if (await search.isVisible().catch(() => false)) {
    await search.fill(name);
  } else {
    const focusedInput = page.locator('input:focus');
    if (await focusedInput.isVisible().catch(() => false)) {
      await focusedInput.fill(name);
    }
  }
  const namedOption = page.getByRole("option", { name, exact: true }).last();
  if (!(await namedOption.isVisible().catch(() => false))) {
    const visibleOptionCount = await page.locator('[role="option"]:visible').count();
    const visibleListboxCount = await page.locator('[role="listbox"]:visible').count();
    throw new Error(
      `Agent option unavailable after search (options=${visibleOptionCount}, listboxes=${visibleListboxCount})`,
    );
  }
  await namedOption.waitFor({ state: "visible", timeout: 30000 });
  await namedOption.click();
  await page.getByRole("textbox", { name: "Agent name" }).waitFor({ state: "visible" });
  await page.waitForFunction(
    (expected) => document.querySelector('input[aria-label="Agent name"]')?.value === expected,
    name,
  );
}

async function pickCombobox(page, ariaName, optionText) {
  const select = page.getByRole("combobox", { name: ariaName, exact: true });
  await select.click();
  const search = page.locator(
    ariaName === "Provider"
      ? 'input[placeholder="Search provider by name"]:visible'
      : 'input[placeholder="Select a model"]:visible',
  );
  if (await search.isVisible().catch(() => false)) await search.fill(optionText);
  const namedOption = page.getByRole("option", { name: optionText, exact: true }).last();
  if (!(await namedOption.isVisible().catch(() => false))) {
    const visibleLabels = await page
      .locator('[role="option"]:visible')
      .allInnerTexts();
    const providerText = await page
      .getByRole("combobox", { name: "Provider", exact: true })
      .innerText()
      .catch(() => "unavailable");
    const modelDisabled = await page
      .getByRole("combobox", { name: "Model", exact: true })
      .isDisabled()
      .catch(() => true);
    const visibleComboboxLabels = await page
      .locator('[role="combobox"]:visible')
      .evaluateAll((elements) => elements.map((element) => element.getAttribute("aria-label") || "unlabelled"));
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
      .locator(
        `#${parameterField}-glasshive-workspace-mode, ${legacyPrefix}-workspace-mode`,
      )
      .first(),
    access: page
      .locator(`#${parameterField}-glasshive-access, ${legacyPrefix}-access`)
      .first(),
    effort: page
      .locator(`#${parameterField}-effort, ${legacyPrefix}-effort`)
      .first(),
  };
}

async function configureGlassHiveAgent(page, name, modelLabel, modelId, effort) {
  await selectAgent(page, name);
  const modelButton = page.locator('label[for="provider"]').locator("..").getByRole("button");
  await modelButton.click();
  await pickCombobox(page, "Provider", "GlassHive");
  await pickCombobox(page, "Model", modelLabel);
  const readiness = page
    .getByText(/^(Authenticated and ready|Sign-in required|Checking…|Unavailable)$/)
    .last();
  await readiness.waitFor({ timeout: 30000 });
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
  const saveResponse = page.waitForResponse(
    (response) => response.request().method() === "PATCH" && /\/api\/agents\//.test(response.url()),
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const saved = await saveResponse;
  if (!saved.ok()) throw new Error(`Agent Builder save returned HTTP ${saved.status()}`);
  await page.reload({ waitUntil: "domcontentloaded" });
  await installAccessToken(page, "");
  await openAgentBuilder(page);
  await selectAgent(page, name);
  await page.locator('label[for="provider"]').locator("..").getByRole("button").click();
  const persistedControls = capabilityControls(page);
  const persisted = {
    provider: await page.getByRole("combobox", { name: "Provider", exact: true }).innerText(),
    model: await page.getByRole("combobox", { name: "Model", exact: true }).innerText(),
    workspace: await persistedControls.workspace.inputValue(),
    access: await persistedControls.access.inputValue(),
    effort: await persistedControls.effort.inputValue(),
    ready: await page.getByText("Authenticated and ready", { exact: true }).isVisible(),
  };
  await page.getByRole("button", { name: /Back to builder/i }).click();
  return {
    defaultsCorrect: initial.workspace === "life" && initial.access === "full",
    persisted:
      persisted.provider.includes("GlassHive") &&
      persisted.model.includes(modelLabel) &&
      persisted.workspace === "life" &&
      persisted.access === "workspace" &&
      persisted.effort === effort &&
      persisted.ready,
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
  const outputDir = path.join(PRIVATE_ROOT, "glasshive-core-provider", stamp);
  fs.mkdirSync(outputDir, { recursive: true });
  const createdAgentIds = [];
  const conversationIds = new Set();
  let browser;
  const result = {
    source: "installed-local-runtime",
    qaUserHash: shortHash(auth.user._id),
    checks: {},
    metrics: {},
    artifacts: [],
  };
  try {
    const runtimeModels = await api(auth.accessToken, "GET", "/api/models");
    if (!Array.isArray(runtimeModels["glasshive-harness"])) {
      throw new Error(
        `GlassHive runtime model catalog missing (providers=${Object.keys(runtimeModels).sort().join(",")})`,
      );
    }
    const providerReadiness = await api(
      auth.accessToken,
      "GET",
      "/api/agents/provider-readiness/glasshive-harness",
    );
    if (providerReadiness.status !== "ready") {
      throw new Error(
        `GlassHive authenticated readiness was ${providerReadiness.status || "missing"}: ${providerReadiness.detail || "no detail"}`,
      );
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
    const listedAgents = await api(
      auth.accessToken,
      "GET",
      "/api/agents?requiredPermission=2&limit=100",
    );
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
      throw new Error(
        `Synthetic agents were not returned by the supported editable-agent list (documents=${createdDocs.length}, owner_acl=${ownerAclCount})`,
      );
    }

    const { chromium } = require(path.join(LIBRECHAT_ROOT, "node_modules", "playwright"));
    browser = await chromium.launch({ channel: "chrome", headless: !HEADED });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
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
    const ordinary = await configureGlassHiveAgent(
      page,
      ordinaryName,
      "Codex / GPT-5.6 Sol",
      "codex-cli:gpt-5.6-sol",
      "medium",
    );
    const cortex = await configureGlassHiveAgent(
      page,
      cortexName,
      "Claude / Opus 5",
      "claude-code:opus",
      "max",
    );
    const fallback = await configureGlassHiveFallback(page, ordinaryName);

    await selectAgent(page, ordinaryName);
    await page.getByRole("button", { name: /^Select (an )?agent$/i }).click();
    const prompt = "Use a native file or shell tool to inspect AGENTS.md, then include the token WEB_AGENT_OK in your answer. Do not change files.";
    const input = page.getByLabel("Message input").or(page.getByPlaceholder(/^Message Viventium$/)).last();
    await input.waitFor({ state: "visible", timeout: 30000 });
    await input.fill(prompt);
    const startedAt = new Date();
    await page.getByTestId("send-button").last().click();
    const assistantTurn = page.locator(".agent-turn").filter({ hasText: "WEB_AGENT_OK" }).last();
    await assistantTurn.waitFor({ state: "visible", timeout: 180000 });
    await assistantTurn
      .getByText("Harness activity", { exact: true })
      .last()
      .waitFor({ state: "visible" });
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
    result.checks = {
      ordinaryDefaultsVisible: ordinary.defaultsCorrect,
      ordinarySaveReloadPersistence: ordinary.persisted,
      cortexSaveReloadPersistence: cortex.persisted,
      fallbackOpusHighVisible: fallback.visible,
      fallbackOpusHighSaveReloadPersistence: fallback.persisted,
      ordinaryMongoRoundTrip:
        savedById.get(createdAgentIds[0])?.provider === "glasshive-harness" &&
        savedById.get(createdAgentIds[0])?.model === ordinary.modelId &&
        savedById.get(createdAgentIds[0])?.glasshive_options?.workspace?.mode === "life" &&
        savedById.get(createdAgentIds[0])?.glasshive_options?.access === "workspace" &&
        savedById.get(createdAgentIds[0])?.model_parameters?.reasoning_effort === "medium" &&
        savedById.get(createdAgentIds[0])?.fallback_llm_provider === "glasshive-harness" &&
        savedById.get(createdAgentIds[0])?.fallback_llm_model === "claude-code:opus" &&
        savedById.get(createdAgentIds[0])?.fallback_llm_model_parameters?.reasoning_effort === "high",
      cortexMongoRoundTrip:
        savedById.get(createdAgentIds[1])?.provider === "glasshive-harness" &&
        savedById.get(createdAgentIds[1])?.model === cortex.modelId &&
        savedById.get(createdAgentIds[1])?.glasshive_options?.access === "workspace" &&
        savedById.get(createdAgentIds[1])?.model_parameters?.reasoning_effort === "max",
      versionCreated: savedAgents.every((agent) => Array.isArray(agent.versions) && agent.versions.length > 0),
      browserHarnessAnswerVisible: await page
        .locator(".agent-turn")
        .filter({ hasText: "WEB_AGENT_OK" })
        .last()
        .isVisible(),
      browserHarnessActivityVisible: await page
        .locator(".agent-turn")
        .filter({ hasText: "WEB_AGENT_OK" })
        .last()
        .getByText("Harness activity", { exact: true })
        .last()
        .isVisible(),
      assistantPersisted: Boolean(assistantMessage),
      oneAssistantReply:
        userMessage &&
        (await auth.db.collection("messages").countDocuments({
          user: String(auth.user._id),
          conversationId: userMessage.conversationId,
          isCreatedByUser: false,
          parentMessageId: userMessage.messageId,
        })) === 1,
      noConsoleErrors: consoleErrors.length === 0,
      noCriticalHttpErrors: criticalHttpErrors.length === 0,
    };
    result.metrics = {
      configuredAgentCount: savedAgents.length,
      conversationCount: conversationIds.size,
      consoleErrorCount: consoleErrors.length,
      criticalHttpErrorCount: criticalHttpErrors.length,
      ordinaryPersistenceEvidence: ordinary.persistenceEvidence,
      cortexPersistenceEvidence: cortex.persistenceEvidence,
      fallbackPersistenceEvidence: fallback.persistenceEvidence,
    };
    result.pass = Object.values(result.checks).every(Boolean);
    fs.writeFileSync(path.join(outputDir, "result.json"), `${JSON.stringify(result, null, 2)}\n`);
    console.log(JSON.stringify(result, null, 2));
    if (!result.pass) process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => {});
    for (const conversationId of conversationIds) {
      await auth.db.collection("messages").deleteMany({ user: String(auth.user._id), conversationId }).catch(() => {});
      await auth.db.collection("conversations").deleteMany({ user: String(auth.user._id), conversationId }).catch(() => {});
    }
    for (const agentId of createdAgentIds) {
      await api(auth.accessToken, "DELETE", `/api/agents/${encodeURIComponent(agentId)}`).catch(() => {});
    }
    await auth.db.collection("sessions").deleteOne({ _id: auth.sessionId }).catch(() => {});
    await auth.client.close(true).catch(() => {});
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ pass: false, errorClass: shortHash(error?.message), error: publicError(error?.message) }));
  process.exitCode = 1;
});
