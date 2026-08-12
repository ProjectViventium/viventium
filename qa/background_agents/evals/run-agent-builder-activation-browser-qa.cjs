#!/usr/bin/env node
"use strict";

/**
 * Real-browser acceptance for Agent Builder activation routes.
 *
 * The harness is deliberately read-only: it opens every persisted cortex card,
 * compares its visible route with Mongo, checks the runtime model catalog, reloads,
 * and proves that no agent fields changed. Screenshots and the detailed record stay
 * under private App Support; stdout contains only public-safe counts/hashes.
 */

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const {
  assertNonOwnerQaSelection,
} = require("./browser-qa-safety.cjs");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const CLIENT_BASE = (
  process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190"
).replace(/\/$/, "");
const API_BASE = (
  process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180"
).replace(/\/$/, "");
const MAIN_AGENT_ID =
  process.env.VIVENTIUM_QA_AGENT_ID || "agent_viventium_main_95aeb3";
const PRIVATE_ROOT =
  process.env.VIVENTIUM_QA_PRIVATE_DIR ||
  path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "private-user-data",
  );
const HEADED = process.argv.includes("--headed");

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
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

function loadLocalEnv() {
  const runtimeRoot = path.join(
    os.homedir(),
    "Library",
    "Application Support",
    "Viventium",
    "runtime",
  );
  const candidates = [
    path.join(runtimeRoot, "runtime.env"),
    path.join(runtimeRoot, "runtime.local.env"),
    path.join(runtimeRoot, "service-env", "librechat.env"),
    path.join(LIBRECHAT_ROOT, ".env"),
  ];
  return candidates.reduce(
    (all, filePath) => Object.assign(all, parseEnvFile(filePath)),
    { ...process.env },
  );
}

function shortHash(value, length = 12) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function publicError(value) {
  return String(value || "agent_builder_qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/\s+/g, " ")
    .slice(0, 300);
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, stable(value[key])]),
    );
  }
  return value;
}

function snapshotHash(agent) {
  return shortHash(
    JSON.stringify(
      stable({
        instructions: agent?.instructions,
        tools: agent?.tools,
        tool_options: agent?.tool_options,
        provider: agent?.provider,
        model: agent?.model,
        background_cortices: agent?.background_cortices,
      }),
    ),
    20,
  );
}

function requireLocalOptIn() {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    throw new Error("Agent Builder QA is local-development only");
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== "1") {
    throw new Error("Set VIVENTIUM_QA_ALLOW_LOCAL_JWT=1 for this local QA harness");
  }
  if (!process.env.VIVENTIUM_QA_EMAIL && !process.env.VIVENTIUM_QA_USER_NAME) {
    throw new Error("Set VIVENTIUM_QA_EMAIL or VIVENTIUM_QA_USER_NAME");
  }
}

async function createQaAuth(env) {
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error("Missing local QA auth prerequisites");
  }
  const { MongoClient, ObjectId } = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "mongodb"),
  );
  const jwt = require(
    path.join(LIBRECHAT_ROOT, "node_modules", "jsonwebtoken"),
  );
  const client = new MongoClient(env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
  });
  await client.connect();
  const dbName =
    new URL(env.MONGO_URI).pathname.replace(/^\//, "") || "LibreChatViventium";
  const db = client.db(dbName);
  const selector = process.env.VIVENTIUM_QA_USER_NAME
    ? { name: process.env.VIVENTIUM_QA_USER_NAME.trim() }
    : { email: process.env.VIVENTIUM_QA_EMAIL.trim().toLowerCase() };
  const user = await db.collection("users").findOne(selector);
  const owner = await db
    .collection("users")
    .findOne({ role: "ADMIN" }, { projection: { email: 1 } });
  if (!user?._id) {
    await client.close();
    throw new Error("Configured QA user was not found");
  }
  if (String(user.role || "").toUpperCase() === "ADMIN") {
    await client.close();
    throw new Error("Admin/owner account refused for Agent Builder QA");
  }
  assertNonOwnerQaSelection({
    ownerEmail: owner?.email,
    requestedEmail: process.env.VIVENTIUM_QA_EMAIL || "",
    selectedUser: user,
  });

  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: user._id.toString(), sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: 7200 },
  );
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
    refreshTokenHash: crypto
      .createHash("sha256")
      .update(refreshToken)
      .digest("hex"),
  });
  return { accessToken, client, db, refreshToken, sessionId, user };
}

async function readAgentSnapshot(db) {
  const agent = await db.collection("agents").findOne({ id: MAIN_AGENT_ID });
  if (!agent) throw new Error("Main agent is not provisioned");
  const cortices = Array.isArray(agent.background_cortices)
    ? agent.background_cortices
    : [];
  const cortexIds = cortices.map((entry) => entry.agent_id).filter(Boolean);
  const cortexAgents = await db
    .collection("agents")
    .find(
      { id: { $in: cortexIds } },
      { projection: { id: 1, name: 1 } },
    )
    .toArray();
  const names = new Map(cortexAgents.map((entry) => [entry.id, entry.name]));
  return {
    agent,
    hash: snapshotHash(agent),
    routes: cortices.map((entry) => ({
      idHash: shortHash(entry.agent_id),
      name: String(names.get(entry.agent_id) || "").trim(),
      provider: String(entry.activation?.provider || "").trim(),
      model: String(entry.activation?.model || "").trim(),
      fallbackCount: Array.isArray(entry.activation?.fallbacks)
        ? entry.activation.fallbacks.length
        : 0,
    })),
  };
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
    return {
      ok: response.ok,
      token: typeof body?.token === "string" ? body.token : "",
    };
  });
  const token = refreshed.token || fallbackToken;
  if (!token) throw new Error("Unable to establish browser QA auth");
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: value }));
  }, token);
}

function routeTextMatches(text, route) {
  const normalized = String(text || "").replace(/\s+/g, " ");
  return normalized.includes(route.model) && normalized.includes(route.provider);
}

async function openAgentBuilder(page) {
  const agentBuilder = page.getByRole("button", { name: "Agent Builder" });
  if (!(await agentBuilder.isVisible().catch(() => false))) {
    await page.locator("#toggle-right-nav").click();
  }
  await agentBuilder.waitFor({ state: "visible", timeout: 30_000 });
  if ((await agentBuilder.getAttribute("data-state")) !== "open") {
    await agentBuilder.click();
  }
  const agentSelect = page.getByRole("combobox", { name: "Agent" });
  await agentSelect.waitFor({ state: "visible", timeout: 30_000 });
  const selected = (await agentSelect.innerText()).trim();
  if (!selected) throw new Error("Agent Builder opened without a selected agent");
  await page.getByRole("button", { name: "Advanced" }).click();
  await page
    .getByText("Advanced Settings", { exact: true })
    .waitFor({ state: "visible", timeout: 30_000 });
  await page.getByText("Background Cortices", { exact: true }).first().waitFor();
}

async function inspectRoutes(page, routes, expand) {
  const cardVisibility = [];
  for (const route of routes) {
    if (!route.name) {
      cardVisibility.push(false);
      continue;
    }
    const expandButton = page.getByRole("button", {
      name: `Expand ${route.name}`,
      exact: true,
    });
    const visible = await expandButton.isVisible().catch(() => false);
    cardVisibility.push(visible);
    if (visible && expand) {
      if ((await expandButton.count()) !== 1) {
        throw new Error(`Missing accessible expand control for ${route.name}`);
      }
      await expandButton.click();
    }
  }
  const selectorTexts = await page
    .getByRole("combobox", { name: "Select activation model" })
    .allInnerTexts();
  return routes.map((route, index) => {
    const text = selectorTexts[index] || "";
    const selectorVisible = Boolean(text.trim());
    return {
      idHash: route.idHash,
      nameHash: shortHash(route.name),
      visible: cardVisibility[index] === true,
      selectorVisible,
      routeMatches: selectorVisible && routeTextMatches(text, route),
      displayHash: shortHash(text),
      fallbackCount: route.fallbackCount,
    };
  });
}

async function runtimeCatalogSummary(accessToken, currentRoute) {
  const response = await fetch(`${API_BASE}/api/models`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const body = await response.json();
  const providers = Object.entries(body || {}).filter(([, models]) =>
    Array.isArray(models),
  );
  const alternatives = providers.flatMap(([provider, models]) =>
    models.map((model) => ({ provider, model: String(model) })),
  );
  const alternative = alternatives.find(
    (route) =>
      route.provider !== currentRoute.provider || route.model !== currentRoute.model,
  );
  return {
    ok: response.ok,
    providerCount: providers.length,
    routeCount: providers.reduce((sum, [, models]) => sum + models.length, 0),
    alternative,
  };
}

async function main() {
  requireLocalOptIn();
  const env = loadLocalEnv();
  const auth = await createQaAuth(env);
  const before = await readAgentSnapshot(auth.db);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const outputDir = path.join(PRIVATE_ROOT, "background-agents", stamp);
  fs.mkdirSync(outputDir, { recursive: true });
  const result = {
    source: "local-dev-runtime",
    userHash: shortHash(auth.user._id),
    mainAgentHash: shortHash(MAIN_AGENT_ID),
    checks: {},
    metrics: {},
    artifacts: [],
  };
  let browser;
  try {
    if (!before.routes.length) throw new Error("No persisted background cortices found");
    if (before.routes.some((route) => !route.name || !route.provider || !route.model)) {
      throw new Error("Persisted cortex route/name inventory is incomplete");
    }
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
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
    page.setDefaultTimeout(30_000);
    const consoleErrors = [];
    const failedRequests = [];
    const criticalHttpErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(shortHash(message.text()));
    });
    page.on("requestfailed", (request) => {
      if (!/ERR_ABORTED|NS_BINDING_ABORTED/i.test(request.failure()?.errorText || "")) {
        failedRequests.push(shortHash(new URL(request.url()).pathname));
      }
    });
    page.on("response", (response) => {
      const pathname = new URL(response.url()).pathname;
      if (
        response.status() >= 400 &&
        /\/api\/(agents|models|auth\/refresh)/.test(pathname)
      ) {
        criticalHttpErrors.push(`${pathname} ${response.status()}`);
      }
    });

    await page.goto(CLIENT_BASE, { waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    await page.goto(`${CLIENT_BASE}/c/new`, { waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    await openAgentBuilder(page);
    const catalog = await runtimeCatalogSummary(auth.accessToken, before.routes[0]);
    const initial = await inspectRoutes(page, before.routes, true);
    const selectors = page.getByRole("combobox", { name: "Select activation model" });
    const firstSelector = selectors.first();
    await firstSelector.click();
    const search = page.locator('input[placeholder="Search models"]:visible');
    await search.fill(catalog.alternative?.model || "");
    const matchingAlternativeCount = catalog.alternative
      ? await page
          .getByRole("option")
          .filter({ hasText: catalog.alternative.model })
          .filter({ hasText: catalog.alternative.provider })
          .count()
      : 0;
    const optionCount = await page.getByRole("option").count();
    await page.keyboard.press("Escape");

    const initialPath = path.join(outputDir, "activation-routes-expanded.png");
    await page.screenshot({ path: initialPath, fullPage: true });
    result.artifacts.push(path.basename(initialPath));

    await page.reload({ waitUntil: "domcontentloaded" });
    await installAccessToken(page, auth.accessToken);
    await openAgentBuilder(page);
    const reloaded = await inspectRoutes(page, before.routes, true);
    const reloadPath = path.join(outputDir, "activation-routes-reloaded.png");
    await page.screenshot({ path: reloadPath, fullPage: true });
    result.artifacts.push(path.basename(reloadPath));

    const after = await readAgentSnapshot(auth.db);
    result.metrics = {
      cortexCount: before.routes.length,
      initialSelectorCount: initial.filter((row) => row.selectorVisible).length,
      reloadSelectorCount: reloaded.filter((row) => row.selectorVisible).length,
      fallbackCountMinimum: Math.min(...before.routes.map((route) => route.fallbackCount)),
      catalogProviderCount: catalog.providerCount,
      catalogRouteCount: catalog.routeCount,
      visibleOptionCount: optionCount,
      consoleErrorCount: consoleErrors.length,
      failedRequestCount: failedRequests.length,
      criticalHttpErrorCount: criticalHttpErrors.length,
    };
    result.checks = {
      nonblankPersistedRoutes: before.routes.every(
        (route) => route.provider && route.model,
      ),
      allCardsVisible: initial.every((row) => row.visible),
      allRoutesMatchPersistence: initial.every((row) => row.routeMatches),
      allRoutesHaveFallbacks: before.routes.every((route) => route.fallbackCount > 0),
      dynamicCatalogLoaded:
        catalog.ok && catalog.providerCount > 1 && catalog.routeCount > 4,
      dynamicAlternativesVisible: matchingAlternativeCount > 0,
      reloadPreservedEveryRoute: reloaded.every((row) => row.routeMatches),
      noAgentMutation: before.hash === after.hash,
      noConsoleErrors: consoleErrors.length === 0,
      noFailedRequests: failedRequests.length === 0,
      noCriticalHttpErrors: criticalHttpErrors.length === 0,
    };
    result.pass = Object.values(result.checks).every(Boolean);
    fs.writeFileSync(
      path.join(outputDir, "result.json"),
      `${JSON.stringify({ ...result, initial, reloaded }, null, 2)}\n`,
    );
    console.log(JSON.stringify(result, null, 2));
    if (!result.pass) process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => {});
    await auth.db.collection("sessions").deleteOne({ _id: auth.sessionId }).catch(() => {});
    await auth.client.close(true).catch(() => {});
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      pass: false,
      errorClass: shortHash(error?.message || "agent_builder_qa_failed"),
      error: publicError(error?.message),
    }),
  );
  process.exitCode = 1;
});
