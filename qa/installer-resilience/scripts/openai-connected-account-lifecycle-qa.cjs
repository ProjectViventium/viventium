#!/usr/bin/env node
"use strict";

const childProcess = require("child_process");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
const AUTHORIZE_URL = new URL("https://auth.openai.com/oauth/authorize");
const AUTHORIZE_ORIGIN = AUTHORIZE_URL.origin;
const AUTHORIZE_PATH = AUTHORIZE_URL.pathname;
const DEFAULT_PROVIDER_PORT = 14660;
const SYNTHETIC_ACCOUNT_ID = "acct_viventium_synthetic_qa";
const SYNTHETIC_CODE = "viventium-synthetic-authorization-code";
const GUIDANCE_PATTERN = /OpenAI.*needs reconnect.*Settings.*Account.*Connected Accounts/i;
const REQUIRED_STAGES = Object.freeze([
  "authorization_denied",
  "popup_cancelled",
  "first_useful_answer",
  "second_useful_answer",
  "browser_refresh_persistence",
  "runtime_restart_persistence",
  "proactive_expiry_refresh",
  "early_401_refresh",
  "failed_refresh_reconnect_guidance",
  "local_disconnect",
  "disconnect_answer_refusal",
  "regrant_after_disconnect",
]);
const ANSWERS = Object.freeze([
  "Synthetic answer one: the loopback connected account is useful.",
  "Synthetic answer two: conversation continuity is visible in the browser.",
  "Synthetic answer three: the connected account survived the runtime restart.",
  "Synthetic answer four: proactive expiry refresh succeeded locally.",
  "Synthetic answer five: reconnect restored useful chat.",
  "Synthetic answer six: regrant after disconnect restored useful chat.",
]);
const PROMPT_ANSWER_PAIRS = Object.freeze([
  ["first useful synthetic lifecycle answer", ANSWERS[0]],
  ["second useful synthetic lifecycle answer", ANSWERS[1]],
  ["early synthetic 401", ANSWERS[2]],
  ["intentionally expired synthetic grant", ANSWERS[3]],
  ["reconnect restored useful synthetic chat", ANSWERS[4]],
  ["regrant after disconnect restored useful chat", ANSWERS[5]],
]);

function fail(message) {
  throw new Error(message);
}

function base64UrlJson(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

function syntheticAccessToken(generation) {
  return [
    base64UrlJson({ alg: "none", typ: "JWT" }),
    base64UrlJson({
      sub: "synthetic-user",
      generation,
      "https://api.openai.com/auth": { chatgpt_account_id: SYNTHETIC_ACCOUNT_ID },
    }),
    "synthetic",
  ].join(".");
}

function assertLoopbackUrl(rawValue, label) {
  let parsed;
  try {
    parsed = new URL(rawValue);
  } catch {
    fail(`${label} must be a valid loopback URL`);
  }
  if (!new Set(["http:", "https:"]).has(parsed.protocol) || !LOOPBACK_HOSTS.has(parsed.hostname)) {
    fail(`${label} must target loopback only`);
  }
  if (parsed.username || parsed.password) {
    fail(`${label} must not contain credentials`);
  }
  return parsed;
}

function parseProviderPort() {
  const raw = process.env.VIVENTIUM_QA_PROVIDER_PORT || String(DEFAULT_PROVIDER_PORT);
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    fail("VIVENTIUM_QA_PROVIDER_PORT must be a valid loopback TCP port");
  }
  return port;
}

function parseRestartArgv(required) {
  const raw = process.env.VIVENTIUM_QA_RESTART_ARGV_JSON || "";
  if (!raw) {
    if (required) {
      fail("Set VIVENTIUM_QA_RESTART_ARGV_JSON to a JSON argv array for the disposable runtime");
    }
    return null;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    fail("VIVENTIUM_QA_RESTART_ARGV_JSON must be valid JSON");
  }
  if (
    !Array.isArray(parsed) ||
    parsed.length === 0 ||
    parsed.some((value) => typeof value !== "string" || !value || /[\r\n\0]/.test(value))
  ) {
    fail("VIVENTIUM_QA_RESTART_ARGV_JSON must be a non-empty string argv array");
  }
  return parsed;
}

function assertSafeInputs({ requireRestart }) {
  if (process.env.CI || process.env.NODE_ENV === "production") {
    fail("OpenAI lifecycle QA is local-only and forbidden in CI/production");
  }
  const clientBase = (process.env.VIVENTIUM_QA_CLIENT_BASE || "").replace(/\/$/, "");
  const email = process.env.VIVENTIUM_QA_EMAIL || "";
  const password = process.env.VIVENTIUM_QA_PASSWORD || "";
  if (!clientBase || !email || !password) {
    fail("Set the loopback client base and synthetic QA email/password");
  }
  assertLoopbackUrl(clientBase, "VIVENTIUM_QA_CLIENT_BASE");
  if (!email.endsWith(".invalid")) {
    fail("VIVENTIUM_QA_EMAIL must use a synthetic .invalid address");
  }
  if (password.length < 12) {
    fail("VIVENTIUM_QA_PASSWORD must be a synthetic value of at least 12 characters");
  }
  return {
    clientBase,
    email,
    password,
    providerPort: parseProviderPort(),
    restartArgv: parseRestartArgv(requireRestart),
  };
}

function readRequestBody(req, limit = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(new Error("request_too_large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  res.end(body);
}

function responseEvent(event, payload) {
  return `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}

function syntheticResponsesSSE(answer, ordinal) {
  const responseId = `resp_synthetic_${ordinal}`;
  const itemId = `msg_synthetic_${ordinal}`;
  const response = {
    id: responseId,
    object: "response",
    created_at: 1_800_000_000 + ordinal,
    status: "completed",
    model: "gpt-5.6-sol",
    output: [
      {
        id: itemId,
        type: "message",
        role: "assistant",
        status: "completed",
        content: [{ type: "output_text", text: answer, annotations: [] }],
      },
    ],
    output_text: answer,
    usage: { input_tokens: 12, output_tokens: 12, total_tokens: 24 },
  };
  return [
    responseEvent("response.created", {
      type: "response.created",
      sequence_number: 0,
      response: { ...response, status: "in_progress", output: [] },
    }),
    responseEvent("response.output_item.added", {
      type: "response.output_item.added",
      sequence_number: 1,
      output_index: 0,
      item: { id: itemId, type: "message", role: "assistant", status: "in_progress", content: [] },
    }),
    responseEvent("response.content_part.added", {
      type: "response.content_part.added",
      sequence_number: 2,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      part: { type: "output_text", text: "", annotations: [] },
    }),
    responseEvent("response.output_text.delta", {
      type: "response.output_text.delta",
      sequence_number: 3,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      delta: answer,
      logprobs: [],
    }),
    responseEvent("response.output_text.done", {
      type: "response.output_text.done",
      sequence_number: 4,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      text: answer,
      logprobs: [],
    }),
    responseEvent("response.output_item.done", {
      type: "response.output_item.done",
      sequence_number: 5,
      output_index: 0,
      item: response.output[0],
    }),
    responseEvent("response.completed", {
      type: "response.completed",
      sequence_number: 6,
      response,
    }),
    "data: [DONE]\n\n",
  ].join("");
}

function createProviderState() {
  return {
    authorizationCodeExchanges: 0,
    refreshExchanges: 0,
    responsesRequests: 0,
    successfulResponses: 0,
    accessGeneration: 0,
    refreshMode: "success",
    forceNextResponse401: false,
    nextAuthorizationExpiresIn: 3600,
    normalizedRequestFailures: [],
  };
}

function publicProviderSnapshot(state) {
  return {
    authorizationCodeExchanges: state.authorizationCodeExchanges,
    refreshExchanges: state.refreshExchanges,
    responsesRequests: state.responsesRequests,
    successfulResponses: state.successfulResponses,
    providerRevocation: "unsupported",
    normalizedRequestFailureCount: state.normalizedRequestFailures.length,
  };
}

async function handleProviderRequest(req, res, state) {
  const requestUrl = new URL(req.url || "/", "http://127.0.0.1");
  if (req.method === "GET" && requestUrl.pathname === "/__control/health") {
    sendJson(res, 200, { ok: true, provider: "synthetic-loopback" });
    return;
  }
  if (req.method === "GET" && requestUrl.pathname === "/__control/snapshot") {
    sendJson(res, 200, publicProviderSnapshot(state));
    return;
  }

  if (req.method === "POST" && requestUrl.pathname === "/oauth/token") {
    const form = new URLSearchParams(await readRequestBody(req));
    const grantType = form.get("grant_type");
    if (grantType === "authorization_code") {
      state.authorizationCodeExchanges += 1;
      if (form.get("code") !== SYNTHETIC_CODE || !form.get("code_verifier")) {
        sendJson(res, 400, { error: "invalid_grant" });
        return;
      }
      state.accessGeneration += 1;
      const expiresIn = state.nextAuthorizationExpiresIn;
      state.nextAuthorizationExpiresIn = 3600;
      sendJson(res, 200, {
        access_token: syntheticAccessToken(state.accessGeneration),
        refresh_token: `synthetic-refresh-${state.accessGeneration}`,
        expires_in: expiresIn,
        token_type: "Bearer",
      });
      return;
    }
    if (grantType === "refresh_token") {
      state.refreshExchanges += 1;
      if (state.refreshMode === "fail") {
        sendJson(res, 400, {
          error: "invalid_grant",
          error_description: "Synthetic refresh rejected; reconnect required.",
        });
        return;
      }
      state.accessGeneration += 1;
      sendJson(res, 200, {
        access_token: syntheticAccessToken(state.accessGeneration),
        refresh_token: `synthetic-refresh-${state.accessGeneration}`,
        expires_in: 3600,
        token_type: "Bearer",
      });
      return;
    }
    sendJson(res, 400, { error: "unsupported_grant_type" });
    return;
  }

  if (
    req.method === "POST" &&
    /^\/backend-api\/codex\/?responses\/?$/.test(requestUrl.pathname)
  ) {
    state.responsesRequests += 1;
    const authorization = req.headers.authorization || "";
    if (state.forceNextResponse401) {
      state.forceNextResponse401 = false;
      sendJson(res, 401, { error: { type: "invalid_token", message: "synthetic early expiry" } });
      return;
    }
    if (!authorization.startsWith("Bearer ey")) {
      sendJson(res, 401, { error: { type: "invalid_token", message: "synthetic token rejected" } });
      return;
    }
    const bodyText = await readRequestBody(req);
    let payload;
    try {
      payload = JSON.parse(bodyText);
    } catch {
      sendJson(res, 400, { error: { type: "invalid_json" } });
      return;
    }
    const normalized =
      payload.store === false &&
      payload.stream === true &&
      !Object.prototype.hasOwnProperty.call(payload, "user") &&
      Array.isArray(payload.include) &&
      payload.include.includes("reasoning.encrypted_content");
    if (!normalized) {
      state.normalizedRequestFailures.push("codex_request_not_normalized");
      sendJson(res, 400, { error: { type: "request_not_normalized" } });
      return;
    }
    state.successfulResponses += 1;
    const ordinal = state.successfulResponses;
    const serializedPayload = JSON.stringify(payload).toLowerCase();
    const answer =
      PROMPT_ANSWER_PAIRS.find(([promptFragment]) => serializedPayload.includes(promptFragment))?.[1] ||
      "Synthetic lifecycle auxiliary response.";
    const body = syntheticResponsesSSE(answer, ordinal);
    res.writeHead(200, {
      "content-type": "text/event-stream",
      "cache-control": "no-store",
      connection: "keep-alive",
    });
    res.end(body);
    return;
  }

  sendJson(res, 404, { error: "not_found" });
}

function startSyntheticProvider(port) {
  const state = createProviderState();
  const server = http.createServer((req, res) => {
    void handleProviderRequest(req, res, state).catch(() => {
      if (!res.headersSent) {
        sendJson(res, 500, { error: "synthetic_provider_failure" });
      } else {
        res.end();
      }
    });
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const address = server.address();
      resolve({
        server,
        state,
        baseUrl: `http://127.0.0.1:${address.port}`,
      });
    });
  });
}

function stopServer(server) {
  return new Promise((resolve) => server.close(resolve));
}

function syntheticAuthorizeHtml() {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Synthetic OpenAI authorization</title></head>
<body>
  <main>
    <h1>Synthetic OpenAI account</h1>
    <p>No provider or cloud traffic is used by this disposable QA page.</p>
    <button id="authorize">Authorize synthetic OpenAI account</button>
    <button id="deny">Deny authorization</button>
  </main>
  <script>
    const current = new URL(window.location.href);
    const redirect = current.searchParams.get('redirect_uri');
    const state = current.searchParams.get('state');
    function finish(values) {
      const target = new URL(redirect);
      Object.entries(values).forEach(([key, value]) => target.searchParams.set(key, value));
      target.searchParams.set('state', state);
      window.location.href = target.toString();
    }
    document.getElementById('authorize').addEventListener('click', () => finish({code: '${SYNTHETIC_CODE}'}));
    document.getElementById('deny').addEventListener('click', () => finish({error: 'access_denied'}));
  </script>
</body></html>`;
}

function sanitizePathname(rawUrl) {
  try {
    return new URL(rawUrl).pathname
      .replace(/[a-f0-9]{24,}/gi, "<id>")
      .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, "<id>");
  } catch {
    return "<invalid-url>";
  }
}

async function installNetworkFence(context, externalNetworkAttempts) {
  await context.route('**/*', async (route) => {
    const requestUrl = new URL(route.request().url());
    if (requestUrl.origin === AUTHORIZE_ORIGIN && requestUrl.pathname === AUTHORIZE_PATH) {
      await route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        headers: { "cache-control": "no-store" },
        body: syntheticAuthorizeHtml(),
      });
      return;
    }
    if (LOOPBACK_HOSTS.has(requestUrl.hostname)) {
      await route.continue();
      return;
    }
    externalNetworkAttempts.push({ origin: "<external>", path: requestUrl.pathname });
    await route.abort("blockedbyclient");
  });
}

async function register(page, inputs) {
  await page.goto(`${inputs.clientBase}/register`, { waitUntil: "domcontentloaded" });
  const nativeForm = page.locator("form#f");
  if (await nativeForm.isVisible()) {
    await nativeForm.locator('input[name="name"]').fill("Synthetic Connected Account QA");
    await nativeForm.locator('input[name="email"]').fill(inputs.email);
    await nativeForm.locator('input[name="password"]').fill(inputs.password);
    await nativeForm.locator('input[name="confirm_password"]').fill(inputs.password);
    await nativeForm.getByRole("button", { name: "Create admin" }).click();
  } else {
    await page.getByLabel("Full name").fill("Synthetic Connected Account QA");
    await page.getByLabel("Username (optional)").fill(`synthetic-openai-qa-${Date.now()}`);
    await page.getByLabel("Email").fill(inputs.email);
    await page.getByTestId("password").fill(inputs.password);
    await page.getByTestId("confirm_password").fill(inputs.password);
    await page.getByLabel("Submit registration").click();
  }
  await page.waitForURL(/\/login(?:\?|$)/, { timeout: 20_000 });
}

async function login(page, inputs) {
  const destination = encodeURIComponent("/c/new?setup=accounts");
  await page.goto(`${inputs.clientBase}/login?redirect_to=${destination}`, {
    waitUntil: "domcontentloaded",
  });
  await page.locator('input[name="email"]').fill(inputs.email);
  await page.locator('input[name="password"]').fill(inputs.password);
  await page.locator('input[name="password"]').press("Enter");
  await page.locator("#connected-accounts-label").waitFor({ state: "visible", timeout: 25_000 });
}

async function openConnectedAccounts(page, clientBase) {
  await page.goto(`${clientBase}/c/new?setup=accounts`, { waitUntil: "domcontentloaded" });
  await page.locator("#connected-accounts-label").waitFor({ state: "visible", timeout: 25_000 });
  return page.getByRole("region", { name: "OpenAI account" });
}

async function startConnection(page, buttonName) {
  const [popup, startResponse] = await Promise.all([
    page.waitForEvent("popup", { timeout: 15_000 }),
    page.waitForResponse(
      (response) => response.url().includes("/api/connected-accounts/openai/start"),
      { timeout: 15_000 },
    ),
    page.getByRole("button", { name: buttonName, exact: true }).click(),
  ]);
  if (startResponse.status() !== 200) {
    fail(`Connected-account start returned HTTP ${startResponse.status()}`);
  }
  await popup.getByRole("heading", { name: "Synthetic OpenAI account" }).waitFor({
    state: "visible",
    timeout: 15_000,
  });
  return popup;
}

async function waitForConnectionState(section, expected) {
  await section.getByText(expected, { exact: true }).waitFor({ state: "visible", timeout: 25_000 });
}

async function grantConnection(page, section, buttonName) {
  const popup = await startConnection(page, buttonName);
  await popup.getByRole("button", { name: "Authorize synthetic OpenAI account" }).click();
  await waitForConnectionState(section, "Connected");
  if (!popup.isClosed()) {
    await popup.close();
  }
}

async function closeSettingsIfVisible(page) {
  const close = page.getByRole("button", { name: "Close Settings" });
  if (await close.isVisible()) {
    await close.click();
  }
}

async function sendPrompt(page, prompt, expectedAnswer) {
  const input = page.getByTestId("text-input");
  await input.waitFor({ state: "visible", timeout: 25_000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").click();
  await page.getByText(expectedAnswer, { exact: true }).waitFor({ state: "visible", timeout: 45_000 });
}

async function runRestart(argv) {
  await new Promise((resolve, reject) => {
    const restartEnv = { ...process.env };
    for (const secretName of [
      "VIVENTIUM_QA_EMAIL",
      "VIVENTIUM_QA_PASSWORD",
      "VIVENTIUM_QA_RESTART_ARGV_JSON",
      "VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR",
    ]) {
      delete restartEnv[secretName];
    }
    const child = childProcess.spawn(argv[0], argv.slice(1), {
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      env: restartEnv,
    });
    let combinedSize = 0;
    const count = (chunk) => {
      combinedSize += chunk.length;
      if (combinedSize > 4 * 1024 * 1024) {
        child.kill("SIGTERM");
      }
    };
    child.stdout.on("data", count);
    child.stderr.on("data", count);
    const timeout = setTimeout(() => child.kill("SIGTERM"), 180_000);
    child.once("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timeout);
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Disposable runtime restart failed with exit ${code}`));
      }
    });
  });
}

async function waitForRuntime(clientBase) {
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${clientBase}/health`);
      if (response.ok || response.status === 404) {
        return;
      }
    } catch {
      // Expected while the disposable runtime restarts.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  fail("Disposable runtime did not return after restart");
}

function createEvidenceDir() {
  const configured = process.env.VIVENTIUM_QA_PRIVATE_EVIDENCE_DIR || "";
  if (!configured) {
    return fs.mkdtempSync(path.join(os.tmpdir(), "viventium-openai-lifecycle-qa-"));
  }
  const resolved = path.resolve(configured);
  const relative = path.relative(REPO_ROOT, resolved);
  if (relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))) {
    fail("Private browser evidence must stay outside the public repository");
  }
  fs.mkdirSync(resolved, { recursive: true, mode: 0o700 });
  return resolved;
}

function loadPlaywright() {
  const bundled = path.join(LIBRECHAT_ROOT, "node_modules", "playwright");
  if (!fs.existsSync(bundled)) {
    fail("Integrated LibreChat Playwright dependency is not ready");
  }
  return require(bundled);
}

async function runBrowserLifecycle(inputs) {
  const provider = await startSyntheticProvider(inputs.providerPort);
  const evidenceDir = createEvidenceDir();
  const ledger = {
    schemaVersion: 1,
    result: "RUNNING",
    provider: "synthetic-loopback",
    stages: Object.fromEntries(REQUIRED_STAGES.map((stage) => [stage, "NOT_RUN"])),
    providerSnapshot: {},
    externalNetworkAttemptCount: 0,
    unexpectedHttpFailures: [],
  };
  const mark = (stage) => {
    if (!Object.prototype.hasOwnProperty.call(ledger.stages, stage)) {
      fail(`Unknown lifecycle stage: ${stage}`);
    }
    ledger.stages[stage] = "PASS";
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: !process.argv.includes("--headed"),
    args: [
      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1, EXCLUDE ::1",
    ],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    serviceWorkers: "block",
  });
  const externalNetworkAttempts = [];
  const unexpectedHttpFailures = [];
  await installNetworkFence(context, externalNetworkAttempts);
  const page = await context.newPage();
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 400 && !new Set([400, 401]).has(status)) {
      unexpectedHttpFailures.push({ status, path: sanitizePathname(response.url()) });
    }
  });

  try {
    if (process.argv.includes("--register")) {
      await register(page, inputs);
    }
    await login(page, inputs);
    let section = page.getByRole("region", { name: "OpenAI account" });
    await waitForConnectionState(section, "Disconnected");

    let popup = await startConnection(page, "Connect OpenAI Account");
    await popup.getByRole("button", { name: "Deny authorization" }).click();
    await popup.waitForLoadState("domcontentloaded");
    if (!popup.isClosed()) {
      await popup.close();
    }
    await page.getByRole("button", { name: "Connect OpenAI Account", exact: true }).waitFor();
    mark("authorization_denied");

    popup = await startConnection(page, "Connect OpenAI Account");
    await popup.close();
    await page.getByRole("button", { name: "Connect OpenAI Account", exact: true }).waitFor();
    mark("popup_cancelled");

    await grantConnection(page, section, "Connect OpenAI Account");
    if (provider.state.authorizationCodeExchanges !== 1) {
      fail("Synthetic provider did not receive exactly one authorization-code exchange");
    }
    await page.screenshot({ path: path.join(evidenceDir, "01-connected.png"), fullPage: true });
    await closeSettingsIfVisible(page);

    await sendPrompt(page, "Give the first useful synthetic lifecycle answer.", ANSWERS[0]);
    mark("first_useful_answer");
    await sendPrompt(page, "Give the second useful synthetic lifecycle answer.", ANSWERS[1]);
    mark("second_useful_answer");
    const conversationUrl = page.url();
    await page.screenshot({ path: path.join(evidenceDir, "02-two-answers.png"), fullPage: true });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByText(ANSWERS[0], { exact: true }).waitFor({ state: "visible", timeout: 25_000 });
    await page.getByText(ANSWERS[1], { exact: true }).waitFor({ state: "visible", timeout: 25_000 });
    mark("browser_refresh_persistence");

    await runRestart(inputs.restartArgv);
    await waitForRuntime(inputs.clientBase);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    if (page.url().includes("/login")) {
      await login(page, inputs);
      await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    }
    await page.getByText(ANSWERS[0], { exact: true }).waitFor({ state: "visible", timeout: 30_000 });
    await page.getByText(ANSWERS[1], { exact: true }).waitFor({ state: "visible", timeout: 30_000 });
    mark("runtime_restart_persistence");

    const refreshBefore401 = provider.state.refreshExchanges;
    provider.state.refreshMode = "success";
    provider.state.forceNextResponse401 = true;
    await sendPrompt(page, "Recover once from an early synthetic 401.", ANSWERS[2]);
    if (provider.state.refreshExchanges !== refreshBefore401 + 1) {
      fail("Early provider 401 did not cause exactly one refresh and replay");
    }
    mark("early_401_refresh");

    section = await openConnectedAccounts(page, inputs.clientBase);
    provider.state.nextAuthorizationExpiresIn = 1;
    await grantConnection(page, section, "Reconnect");
    await closeSettingsIfVisible(page);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    const refreshBeforeExpiry = provider.state.refreshExchanges;
    await page.waitForTimeout(1500);
    await sendPrompt(page, "Refresh the intentionally expired synthetic grant.", ANSWERS[3]);
    if (provider.state.refreshExchanges !== refreshBeforeExpiry + 1) {
      fail("Expired connected account did not refresh before the useful answer");
    }
    mark("proactive_expiry_refresh");

    provider.state.refreshMode = "fail";
    provider.state.forceNextResponse401 = true;
    const input = page.getByTestId("text-input");
    await input.fill("Show actionable reconnect guidance after refresh fails.");
    await page.getByTestId("send-button").click();
    await page.getByText(GUIDANCE_PATTERN).waitFor({ state: "visible", timeout: 45_000 });
    mark("failed_refresh_reconnect_guidance");

    provider.state.refreshMode = "success";
    section = await openConnectedAccounts(page, inputs.clientBase);
    await grantConnection(page, section, "Reconnect");
    await closeSettingsIfVisible(page);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    await sendPrompt(page, "Confirm reconnect restored useful synthetic chat.", ANSWERS[4]);

    section = await openConnectedAccounts(page, inputs.clientBase);
    const responsesBeforeDisconnect = provider.state.responsesRequests;
    const [disconnectResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" && response.url().includes("/api/keys/"),
        { timeout: 15_000 },
      ),
      section.getByRole("button", { name: "Disconnect", exact: true }).click(),
    ]);
    if (disconnectResponse.status() !== 204) {
      fail(`Local connected-account deletion returned HTTP ${disconnectResponse.status()}`);
    }
    await waitForConnectionState(section, "Disconnected");
    mark("local_disconnect");

    await closeSettingsIfVisible(page);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    const guidanceCountBeforeDisconnect = await page.getByText(GUIDANCE_PATTERN).count();
    const disconnectedInput = page.getByTestId("text-input");
    await disconnectedInput.fill("Refuse chat until the locally disconnected account is reconnected.");
    await page.getByTestId("send-button").click();
    await page
      .getByText(GUIDANCE_PATTERN)
      .nth(guidanceCountBeforeDisconnect)
      .waitFor({ state: "visible", timeout: 45_000 });
    if (provider.state.responsesRequests !== responsesBeforeDisconnect) {
      fail("Locally disconnected chat still contacted the synthetic provider");
    }
    mark("disconnect_answer_refusal");

    section = await openConnectedAccounts(page, inputs.clientBase);
    await grantConnection(page, section, "Connect OpenAI Account");
    await closeSettingsIfVisible(page);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    await sendPrompt(page, "Confirm regrant after disconnect restored useful chat.", ANSWERS[5]);
    mark("regrant_after_disconnect");
    await page.screenshot({ path: path.join(evidenceDir, "03-regrant-answer.png"), fullPage: true });

    if (externalNetworkAttempts.length > 0) {
      fail("Browser attempted non-loopback traffic outside the locally intercepted authorize URL");
    }
    if (unexpectedHttpFailures.length > 0) {
      fail("Unexpected browser-visible HTTP failures occurred during lifecycle QA");
    }
    if (provider.state.normalizedRequestFailures.length > 0) {
      fail("LibreChat sent a non-normalized Codex Responses request");
    }
    if (Object.values(ledger.stages).some((status) => status !== "PASS")) {
      fail("One or more required lifecycle stages did not pass");
    }

    ledger.result = "PASS";
    ledger.providerSnapshot = publicProviderSnapshot(provider.state);
    ledger.externalNetworkAttemptCount = externalNetworkAttempts.length;
    ledger.unexpectedHttpFailures = unexpectedHttpFailures;
    fs.writeFileSync(path.join(evidenceDir, "sanitized-ledger.json"), `${JSON.stringify(ledger, null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    return {
      result: "PASS",
      mode: "browser-lifecycle",
      provider: "synthetic-loopback",
      stages: ledger.stages,
      providerSnapshot: ledger.providerSnapshot,
      externalNetworkAttemptCount: 0,
      unexpectedHttpFailures: [],
      evidenceDirectory: "<private>",
    };
  } finally {
    await browser.close();
    await stopServer(provider.server);
  }
}

async function runSelfTest() {
  const provider = await startSyntheticProvider(0);
  try {
    const authorization = await fetch(`${provider.baseUrl}/oauth/token`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code: SYNTHETIC_CODE,
        code_verifier: "synthetic-verifier",
        redirect_uri: "http://localhost:1455/auth/callback",
      }),
    });
    if (!authorization.ok) {
      fail("Synthetic authorization-code exchange self-test failed");
    }
    const authorizationBody = await authorization.json();
    const refresh = await fetch(`${provider.baseUrl}/oauth/token`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: authorizationBody.refresh_token,
        client_id: "synthetic-client",
      }),
    });
    const refreshBody = await refresh.json();
    if (!refresh.ok) {
      fail("Synthetic refresh exchange self-test failed");
    }
    const responses = await fetch(`${provider.baseUrl}/backend-api/codex/responses`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${refreshBody.access_token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-5.6-sol",
        input: [{ role: "user", content: "synthetic self-test" }],
        store: false,
        stream: true,
        include: ["reasoning.encrypted_content"],
      }),
    });
    if (!responses.ok || !(await responses.text()).includes("response.completed")) {
      fail("Synthetic Responses SSE self-test failed");
    }
    return {
      result: "PASS",
      mode: "self-test",
      provider: "synthetic-loopback",
      authorizationCodeExchanges: provider.state.authorizationCodeExchanges,
      refreshExchanges: provider.state.refreshExchanges,
      responsesRequests: provider.state.responsesRequests,
      providerRevocation: "unsupported",
      evidenceDirectory: "<private>",
    };
  } finally {
    await stopServer(provider.server);
  }
}

async function main() {
  if (process.argv.includes("--self-test")) {
    console.log(JSON.stringify(await runSelfTest(), null, 2));
    return;
  }
  if (process.argv.includes("--contract-check")) {
    const inputs = assertSafeInputs({ requireRestart: false });
    console.log(
      JSON.stringify(
        {
          result: "PASS",
          mode: "contract-check",
          target: "loopback",
          providerPort: inputs.providerPort,
          evidenceDirectory: "<private>",
        },
        null,
        2,
      ),
    );
    return;
  }
  const inputs = assertSafeInputs({ requireRestart: true });
  console.log(JSON.stringify(await runBrowserLifecycle(inputs), null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(JSON.stringify({ result: "FAIL", error: error.message }, null, 2));
    process.exitCode = 1;
  });
}

module.exports = {
  assertLoopbackUrl,
  createProviderState,
  publicProviderSnapshot,
  runSelfTest,
  startSyntheticProvider,
  syntheticResponsesSSE,
};
