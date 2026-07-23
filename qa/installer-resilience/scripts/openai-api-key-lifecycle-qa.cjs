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
const DEFAULT_PROVIDER_PORT = 14661;
const VALID_KEY = "synthetic-valid-provider-key";
const INVALID_KEY = "synthetic-invalid-provider-key";
const QA_PROVIDERS = Object.freeze({
  openai: Object.freeze({
    slug: "openai",
    protocol: "openai",
    modelId: "gpt-5.6-sol",
    regionName: "OpenAI account",
    keyButtonName: "Use OpenAI API key",
    keyInputLabel: "OpenAI API Key",
    keyName: "openAI",
    endpointItem: "",
    selectionText: "",
  }),
  anthropic: Object.freeze({
    slug: "anthropic",
    protocol: "anthropic",
    modelId: "claude-opus-4-8",
    regionName: "Anthropic account",
    keyButtonName: "Use Anthropic API key",
    keyInputLabel: "Key",
    keyName: "anthropic",
    endpointItem: "anthropic",
    selectionText: "Claude Opus 4 8",
  }),
  groq: Object.freeze({
    slug: "groq",
    protocol: "openai",
    modelId: "groq/compound-mini",
    regionName: "Groq account",
    keyButtonName: "Use Groq API key",
    keyInputLabel: "groq API Key",
    keyName: "groq",
    endpointItem: "groq",
    selectionText: "groq/compound-mini",
  }),
  xai: Object.freeze({
    slug: "xai",
    protocol: "openai",
    modelId: "grok-4-3",
    regionName: "Grok (xAI) account",
    keyButtonName: "Use Grok (xAI) API key",
    keyInputLabel: "xai API Key",
    keyName: "xai",
    endpointItem: "xai",
    selectionText: "Grok 4.3",
  }),
});
const REQUIRED_STAGES = Object.freeze([
  "valid_key_first_answer",
  "valid_key_second_answer",
  "browser_refresh_persistence",
  "runtime_restart_persistence",
  "invalid_key_repair",
  "quota_repair",
  "provider_outage_repair",
  "network_failure_repair",
  "local_disconnect",
  "disconnect_prevents_provider_request",
  "missing_key_one_click_recovery",
  "valid_key_readded",
]);
const ANSWERS = Object.freeze([
  "Synthetic API-key answer one is useful and local.",
  "Synthetic API-key answer two proves conversation continuity.",
  "Synthetic API-key recovery restored a useful answer.",
  "Synthetic API-key re-add restored a useful answer.",
]);

function fail(message) {
  throw new Error(message);
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

function parseQAProvider() {
  const slug = (process.env.VIVENTIUM_QA_PROVIDER || "openai").trim().toLowerCase();
  const provider = QA_PROVIDERS[slug];
  if (!provider) {
    fail("VIVENTIUM_QA_PROVIDER must be openai, anthropic, groq, or xai");
  }
  return provider;
}

function parseRuntimeProviderTarget(qaProvider, providerPort) {
  const envName = {
    openai: "OPENAI_REVERSE_PROXY",
    anthropic: "ANTHROPIC_REVERSE_PROXY",
    groq: "GROQ_BASE_URL",
    xai: "XAI_BASE_URL",
  }[qaProvider.slug];
  const raw = process.env[envName] || "";
  if (!raw) {
    fail(`Set ${envName} to the synthetic loopback provider before lifecycle QA`);
  }
  const target = assertLoopbackUrl(raw, envName);
  const targetPort = Number(target.port || (target.protocol === "https:" ? 443 : 80));
  if (targetPort !== providerPort) {
    fail(`${envName} must use the same port as VIVENTIUM_QA_PROVIDER_PORT`);
  }
  return target.origin;
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
    fail("OpenAI API-key lifecycle QA is local-only and forbidden in CI/production");
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
  const providerPort = parseProviderPort();
  const qaProvider = parseQAProvider();
  return {
    clientBase,
    email,
    password,
    providerPort,
    qaProvider,
    runtimeProviderTarget: parseRuntimeProviderTarget(qaProvider, providerPort),
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

function pickAnswer(payload) {
  const serialized = JSON.stringify(payload).toLowerCase();
  if (serialized.includes("second useful")) {
    return ANSWERS[1];
  }
  if (serialized.includes("re-add")) {
    return ANSWERS[3];
  }
  if (serialized.includes("recovery restored")) {
    return ANSWERS[2];
  }
  return ANSWERS[0];
}

function chatCompletionSSE(answer, ordinal) {
  const id = `chatcmpl_synthetic_${ordinal}`;
  const chunks = [
    {
      id,
      object: "chat.completion.chunk",
      created: 1_800_000_000 + ordinal,
      model: "gpt-5.6-sol",
      choices: [{ index: 0, delta: { role: "assistant", content: answer }, finish_reason: null }],
    },
    {
      id,
      object: "chat.completion.chunk",
      created: 1_800_000_000 + ordinal,
      model: "gpt-5.6-sol",
      choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
    },
  ];
  return `${chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`).join("")}data: [DONE]\n\n`;
}

function responsesSSE(answer, ordinal) {
  const responseId = `resp_synthetic_key_${ordinal}`;
  const itemId = `msg_synthetic_key_${ordinal}`;
  const contentPart = { type: "output_text", text: answer, annotations: [] };
  const messageItem = {
    id: itemId,
    type: "message",
    role: "assistant",
    status: "completed",
    phase: null,
    content: [contentPart],
  };
  const response = {
    id: responseId,
    object: "response",
    created_at: 1_800_000_000 + ordinal,
    status: "completed",
    model: "gpt-5.6-sol",
    output: [messageItem],
    output_text: answer,
    error: null,
    incomplete_details: null,
    instructions: null,
    max_output_tokens: null,
    max_tool_calls: null,
    metadata: {},
    parallel_tool_calls: true,
    previous_response_id: null,
    prompt: null,
    reasoning: null,
    safety_identifier: null,
    service_tier: "default",
    store: false,
    temperature: 1,
    text: { format: { type: "text" } },
    tool_choice: "auto",
    tools: [],
    top_p: 1,
    truncation: "disabled",
    user: null,
    usage: {
      input_tokens: 12,
      input_tokens_details: { cached_tokens: 0 },
      output_tokens: 12,
      output_tokens_details: { reasoning_tokens: 0 },
      total_tokens: 24,
    },
  };
  const event = (name, value) => `event: ${name}\ndata: ${JSON.stringify(value)}\n\n`;
  return [
    event("response.created", {
      type: "response.created",
      sequence_number: 0,
      response: { ...response, status: "in_progress", output: [] },
    }),
    event("response.in_progress", {
      type: "response.in_progress",
      sequence_number: 1,
      response: { ...response, status: "in_progress", output: [] },
    }),
    event("response.output_item.added", {
      type: "response.output_item.added",
      sequence_number: 2,
      output_index: 0,
      item: { ...messageItem, status: "in_progress", content: [] },
    }),
    event("response.content_part.added", {
      type: "response.content_part.added",
      sequence_number: 3,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      part: { type: "output_text", text: "", annotations: [] },
    }),
    event("response.output_text.delta", {
      type: "response.output_text.delta",
      sequence_number: 4,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      delta: answer,
      logprobs: [],
    }),
    event("response.output_text.done", {
      type: "response.output_text.done",
      sequence_number: 5,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      text: answer,
      logprobs: [],
    }),
    event("response.content_part.done", {
      type: "response.content_part.done",
      sequence_number: 6,
      item_id: itemId,
      output_index: 0,
      content_index: 0,
      part: contentPart,
    }),
    event("response.output_item.done", {
      type: "response.output_item.done",
      sequence_number: 7,
      output_index: 0,
      item: messageItem,
    }),
    event("response.completed", { type: "response.completed", sequence_number: 8, response }),
    "data: [DONE]\n\n",
  ].join("");
}

function anthropicMessagesSSE(answer, ordinal, modelId) {
  const messageId = `msg_synthetic_anthropic_${ordinal}`;
  const event = (name, value) => `event: ${name}\ndata: ${JSON.stringify(value)}\n\n`;
  return [
    event("message_start", {
      type: "message_start",
      message: {
        id: messageId,
        type: "message",
        role: "assistant",
        model: modelId,
        content: [],
        stop_reason: null,
        stop_sequence: null,
        usage: { input_tokens: 12, output_tokens: 0 },
      },
    }),
    event("content_block_start", {
      type: "content_block_start",
      index: 0,
      content_block: { type: "text", text: "" },
    }),
    event("content_block_delta", {
      type: "content_block_delta",
      index: 0,
      delta: { type: "text_delta", text: answer },
    }),
    event("content_block_stop", { type: "content_block_stop", index: 0 }),
    event("message_delta", {
      type: "message_delta",
      delta: { stop_reason: "end_turn", stop_sequence: null },
      usage: { output_tokens: 12 },
    }),
    event("message_stop", { type: "message_stop" }),
  ].join("");
}

function createProviderState() {
  return {
    mode: "healthy",
    modelsRequests: 0,
    chatRequests: 0,
    successfulAnswers: 0,
  };
}

function sendProviderError(res, status, type, message, qaProvider) {
  if (qaProvider.protocol === "anthropic") {
    sendJson(res, status, { type: "error", error: { type, message } });
    return;
  }
  sendJson(res, status, { error: { message, type } });
}

async function handleProviderRequest(req, res, state, qaProvider) {
  const requestUrl = new URL(req.url || "/", "http://127.0.0.1");
  if (
    qaProvider.protocol === "openai" &&
    req.method === "GET" &&
    /\/models\/?$/.test(requestUrl.pathname)
  ) {
    state.modelsRequests += 1;
    sendJson(res, 200, {
      object: "list",
      data: [{ id: qaProvider.modelId, object: "model", created: 1_800_000_000, owned_by: "synthetic" }],
    });
    return;
  }
  const expectedPath =
    qaProvider.protocol === "anthropic"
      ? /\/messages\/?$/
      : /\/(?:chat\/completions|responses)\/?$/;
  if (req.method !== "POST" || !expectedPath.test(requestUrl.pathname)) {
    sendProviderError(res, 404, "not_found", "not_found", qaProvider);
    return;
  }

  state.chatRequests += 1;
  const providedKey =
    qaProvider.protocol === "anthropic"
      ? req.headers["x-api-key"]
      : req.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (providedKey !== VALID_KEY) {
    sendProviderError(res, 401, "authentication_error", "Synthetic API key is invalid.", qaProvider);
    return;
  }
  if (state.mode === "quota") {
    sendProviderError(res, 429, "rate_limit_error", "Synthetic quota exhausted.", qaProvider);
    return;
  }
  if (state.mode === "outage") {
    sendProviderError(res, 503, "api_error", "Synthetic provider unavailable.", qaProvider);
    return;
  }
  if (state.mode === "network") {
    req.socket.destroy();
    return;
  }

  const bodyText = await readRequestBody(req);
  let payload;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    sendProviderError(res, 400, "invalid_request_error", "invalid_json", qaProvider);
    return;
  }
  state.successfulAnswers += 1;
  const answer = pickAnswer(payload);
  const streamBody =
    qaProvider.protocol === "anthropic"
      ? anthropicMessagesSSE(answer, state.successfulAnswers, qaProvider.modelId)
      : requestUrl.pathname.endsWith("/responses")
        ? responsesSSE(answer, state.successfulAnswers)
        : chatCompletionSSE(answer, state.successfulAnswers);
  res.writeHead(200, {
    "content-type": "text/event-stream",
    "cache-control": "no-store",
    connection: "keep-alive",
  });
  res.end(streamBody);
}

function startSyntheticProvider(port, qaProvider = QA_PROVIDERS.openai) {
  const state = createProviderState();
  const server = http.createServer((req, res) => {
    void handleProviderRequest(req, res, state, qaProvider).catch(() => {
      if (!res.headersSent) {
        sendProviderError(res, 500, "api_error", "synthetic_provider_failure", qaProvider);
      } else {
        res.end();
      }
    });
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const address = server.address();
      resolve({ server, state, baseUrl: `http://127.0.0.1:${address.port}` });
    });
  });
}

function stopServer(server) {
  return new Promise((resolve) => server.close(resolve));
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
    if (LOOPBACK_HOSTS.has(requestUrl.hostname)) {
      await route.continue();
      return;
    }
    externalNetworkAttempts.push({ origin: "<external>", path: requestUrl.pathname });
    await route.abort("blockedbyclient");
  });
}

function assertSerializedCredentialAbsent(state, forbiddenSecrets) {
  const serialized = JSON.stringify(state);
  const leaked = forbiddenSecrets
    .filter((value) => typeof value === "string" && value.length > 0)
    .some((value) => serialized.includes(value));
  if (leaked) {
    fail("Provider credential leaked into browser persistence");
  }
}

async function assertBrowserCredentialAbsent(page, context, forbiddenSecrets) {
  const storageState = await context.storageState();
  const pageState = await page.evaluate(async () => {
    const readStorage = (storage) =>
      Object.fromEntries(
        Array.from({ length: storage.length }, (_, index) => {
          const key = storage.key(index) || "";
          return [key, storage.getItem(key)];
        }),
      );
    const state = {
      documentCookie: document.cookie,
      localStorage: readStorage(window.localStorage),
      sessionStorage: readStorage(window.sessionStorage),
      cacheStorage: [],
      indexedDb: [],
    };

    if (typeof caches !== "undefined") {
      for (const cacheName of await caches.keys()) {
        const cache = await caches.open(cacheName);
        const entries = [];
        for (const request of await cache.keys()) {
          const response = await cache.match(request);
          entries.push({
            requestUrl: request.url,
            responseText: response ? (await response.clone().text()).slice(0, 2_000_000) : "",
          });
        }
        state.cacheStorage.push({ cacheName, entries });
      }
    }

    if (typeof indexedDB.databases === "function") {
      for (const descriptor of await indexedDB.databases()) {
        if (!descriptor.name) {
          continue;
        }
        const databaseState = await new Promise((resolve) => {
          const openRequest = indexedDB.open(descriptor.name);
          openRequest.onerror = () => resolve({ name: descriptor.name, stores: [] });
          openRequest.onsuccess = async () => {
            const database = openRequest.result;
            const storeNames = Array.from(database.objectStoreNames);
            if (storeNames.length === 0) {
              database.close();
              resolve({ name: descriptor.name, stores: [] });
              return;
            }
            try {
              const transaction = database.transaction(storeNames, "readonly");
              const stores = await Promise.all(
                storeNames.map(
                  (storeName) =>
                    new Promise((storeResolve) => {
                      const request = transaction.objectStore(storeName).getAll();
                      request.onerror = () => storeResolve({ name: storeName, values: [] });
                      request.onsuccess = () =>
                        storeResolve({ name: storeName, values: request.result });
                    }),
                ),
              );
              database.close();
              resolve({ name: descriptor.name, stores });
            } catch {
              database.close();
              resolve({ name: descriptor.name, stores: [] });
            }
          };
        });
        state.indexedDb.push(databaseState);
      }
    }
    return state;
  });
  assertSerializedCredentialAbsent({ storageState, pageState }, forbiddenSecrets);
}

async function register(page, inputs) {
  await page.goto(`${inputs.clientBase}/register`, { waitUntil: "domcontentloaded" });
  const nativeForm = page.locator("form#f");
  if (await nativeForm.isVisible()) {
    await nativeForm.locator('input[name="name"]').fill("Synthetic API Key QA");
    await nativeForm.locator('input[name="email"]').fill(inputs.email);
    await nativeForm.locator('input[name="password"]').fill(inputs.password);
    await nativeForm.locator('input[name="confirm_password"]').fill(inputs.password);
    await nativeForm.getByRole("button", { name: "Create admin" }).click();
  } else {
    await page.getByLabel("Full name").fill("Synthetic API Key QA");
    await page.getByLabel("Username (optional)").fill(`synthetic-api-key-qa-${Date.now()}`);
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
  try {
    await page.locator("#connected-accounts-label").waitFor({ state: "visible", timeout: 10_000 });
  } catch (error) {
    if (inputs.qaProvider.slug === "openai") {
      throw error;
    }
    await page.getByTestId("nav-user").waitFor({ state: "visible", timeout: 25_000 });
    await page.getByTestId("nav-user").click();
    await page.getByText("Connected Accounts", { exact: true }).click();
    await page.locator("#connected-accounts-label").waitFor({ state: "visible", timeout: 25_000 });
  }
}

async function openConnectedAccounts(page, clientBase, qaProvider) {
  await page.goto(`${clientBase}/c/new`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("nav-user").waitFor({ state: "visible", timeout: 25_000 });
  await page.getByTestId("nav-user").click();
  await page.getByText("Connected Accounts", { exact: true }).click();
  await page.locator("#connected-accounts-label").waitFor({ state: "visible", timeout: 25_000 });
  return page.getByRole("region", { name: qaProvider.regionName });
}

async function saveProviderKey(page, section, value, qaProvider) {
  await section.getByRole("button", { name: qaProvider.keyButtonName, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(qaProvider.keyInputLabel).fill(value);
  const [saveResponse] = await Promise.all([
    page.waitForResponse(
      (response) =>
        response.request().method() === "PUT" && response.url().includes("/api/keys"),
      { timeout: 15_000 },
    ),
    dialog.getByRole("button", { name: "Submit", exact: true }).click(),
  ]);
  if (!saveResponse.ok()) {
    fail(`Local key save returned HTTP ${saveResponse.status()}`);
  }
  await dialog.waitFor({ state: "hidden", timeout: 15_000 });
  await section.getByText("Saved locally — send a message to test it", { exact: true }).waitFor({
    state: "visible",
    timeout: 15_000,
  });
}

async function selectChatProvider(page, qaProvider) {
  if (!qaProvider.endpointItem) {
    return;
  }
  await page.getByRole("button", { name: "Select a model", exact: true }).click();
  const search = page.locator("#model-search");
  await search.waitFor({ state: "visible", timeout: 25_000 });
  await search.fill(qaProvider.selectionText);
  const selection = page.getByText(qaProvider.selectionText, { exact: true }).last();
  await selection.waitFor({ state: "visible", timeout: 25_000 });
  await selection.click();
}

async function closeSettingsIfVisible(page) {
  const close = page.getByRole("button", { name: "Close Settings", exact: true });
  await close.waitFor({ state: "visible", timeout: 15_000 });
  await close.click();
  await close.waitFor({ state: "hidden", timeout: 15_000 });
}

async function sendPrompt(page, prompt, expectedAnswer) {
  const input = page.getByTestId("text-input");
  await input.waitFor({ state: "visible", timeout: 25_000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").click();
  await waitForConversationAnswer(page, expectedAnswer, 45_000);
}

async function waitForConversationAnswer(page, expectedAnswer, timeout) {
  await page
    .locator('[aria-label^="Message "]')
    .getByText(expectedAnswer, { exact: true })
    .first()
    .waitFor({ state: "visible", timeout });
}

async function sendPromptExpectingFailure(page, prompt, pattern) {
  const before = await page.getByText(pattern).count();
  const input = page.getByTestId("text-input");
  await input.waitFor({ state: "visible", timeout: 25_000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").click();
  await page.getByText(pattern).nth(before).waitFor({ state: "visible", timeout: 45_000 });
}

async function startFreshConversation(page, clientBase) {
  await page.goto(`${clientBase}/c/new`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("text-input").waitFor({ state: "visible", timeout: 25_000 });
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
    return fs.mkdtempSync(path.join(os.tmpdir(), "viventium-api-key-lifecycle-qa-"));
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
  const configured = process.env.VIVENTIUM_QA_PLAYWRIGHT_MODULE || bundled;
  const resolved = path.resolve(configured);
  if (!fs.existsSync(resolved)) {
    fail("Integrated LibreChat Playwright dependency is not ready");
  }
  return require(resolved);
}

async function runBrowserLifecycle(inputs) {
  const provider = await startSyntheticProvider(inputs.providerPort, inputs.qaProvider);
  const evidenceDir = createEvidenceDir();
  const ledger = {
    schemaVersion: 1,
    result: "RUNNING",
    provider: `synthetic-${inputs.qaProvider.slug}-compatible-loopback`,
    stages: Object.fromEntries(REQUIRED_STAGES.map((stage) => [stage, "NOT_RUN"])),
    providerSnapshot: {},
    externalNetworkAttemptCount: 0,
    unexpectedHttpFailures: [],
    browserCredentialResidueChecks: 0,
  };
  const mark = (stage) => {
    if (!Object.prototype.hasOwnProperty.call(ledger.stages, stage)) {
      fail(`Unknown lifecycle stage: ${stage}`);
    }
    ledger.stages[stage] = "PASS";
  };
  let browser;
  let page;

  try {
    const { chromium } = loadPlaywright();
    browser = await chromium.launch({
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
    page = await context.newPage();
    page.on("response", (response) => {
      const status = response.status();
      if (status >= 400 && !new Set([400, 401, 429, 503]).has(status)) {
        unexpectedHttpFailures.push({ status, path: sanitizePathname(response.url()) });
      }
    });

    // Force the disposable backend to inherit the verified loopback provider target before any
    // credential is saved or prompt can be sent. This closes the backend-egress gap that a
    // browser-only network fence cannot cover.
    await runRestart(inputs.restartArgv);
    await waitForRuntime(inputs.clientBase);

    if (process.argv.includes("--register")) {
      await register(page, inputs);
    }
    await login(page, inputs);
    let section = page.getByRole("region", { name: inputs.qaProvider.regionName });
    await section.waitFor({ state: "visible", timeout: 25_000 });
    if (
      inputs.qaProvider.slug !== "openai" &&
      (await section
        .getByText("Saved locally — send a message to test it", { exact: true })
        .isVisible())
    ) {
      const [cleanupResponse] = await Promise.all([
        page.waitForResponse(
          (response) =>
            response.request().method() === "DELETE" &&
            new URL(response.url()).pathname.endsWith(`/api/keys/${inputs.qaProvider.keyName}`),
          { timeout: 15_000 },
        ),
        section.getByRole("button", { name: "Disconnect", exact: true }).click(),
      ]);
      if (cleanupResponse.status() !== 204) {
        fail(`Initial local key cleanup returned HTTP ${cleanupResponse.status()}`);
      }
    }
    await section.getByText("No local credential saved", { exact: true }).waitFor({
      state: "visible",
      timeout: 25_000,
    });
    if ((await page.getByText("Experimental account connection", { exact: true }).count()) > 0) {
      fail("Stable Easy Install lifecycle exposed the experimental account connection control");
    }

    await saveProviderKey(page, section, VALID_KEY, inputs.qaProvider);
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    await page.screenshot({ path: path.join(evidenceDir, "01-local-credential-saved.png"), fullPage: true });
    await closeSettingsIfVisible(page);
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    if (await page.getByRole("button", { name: "Close Settings", exact: true }).isVisible()) {
      fail("Selecting the saved provider unexpectedly reopened Connected Accounts");
    }

    await sendPrompt(page, "Give the first useful API-key lifecycle answer.", ANSWERS[0]);
    mark("valid_key_first_answer");
    await sendPrompt(page, "Give the second useful API-key lifecycle answer.", ANSWERS[1]);
    mark("valid_key_second_answer");
    const conversationUrl = page.url();
    await page.screenshot({ path: path.join(evidenceDir, "02-two-persistent-answers.png"), fullPage: true });

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForConversationAnswer(page, ANSWERS[0], 25_000);
    await waitForConversationAnswer(page, ANSWERS[1], 25_000);
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    mark("browser_refresh_persistence");

    await runRestart(inputs.restartArgv);
    await waitForRuntime(inputs.clientBase);
    await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    if (page.url().includes("/login")) {
      await login(page, inputs);
      await page.goto(conversationUrl, { waitUntil: "domcontentloaded" });
    }
    await waitForConversationAnswer(page, ANSWERS[0], 30_000);
    await waitForConversationAnswer(page, ANSWERS[1], 30_000);
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    mark("runtime_restart_persistence");

    section = await openConnectedAccounts(page, inputs.clientBase, inputs.qaProvider);
    await saveProviderKey(page, section, INVALID_KEY, inputs.qaProvider);
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    await closeSettingsIfVisible(page);
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    const invalidBefore = provider.state.chatRequests;
    await sendPromptExpectingFailure(page, "Reject the intentionally invalid synthetic key.", /invalid|API key|401/i);
    const invalidRequestDelta = provider.state.chatRequests - invalidBefore;
    if (invalidRequestDelta < 0 || invalidRequestDelta > 1) {
      fail(
        `Invalid key path request delta was ${invalidRequestDelta}; expected local rejection or one provider request`,
      );
    }
    section = await openConnectedAccounts(page, inputs.clientBase, inputs.qaProvider);
    await saveProviderKey(page, section, VALID_KEY, inputs.qaProvider);
    await closeSettingsIfVisible(page);
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    await sendPrompt(page, "Confirm API-key recovery restored a useful answer.", ANSWERS[2]);
    mark("invalid_key_repair");

    provider.state.mode = "quota";
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    await sendPromptExpectingFailure(page, "Show a repair action for synthetic quota exhaustion.", /quota|rate limit|429|billing/i);
    provider.state.mode = "healthy";
    mark("quota_repair");

    provider.state.mode = "outage";
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    await sendPromptExpectingFailure(page, "Show a repair action for synthetic provider outage.", /unavailable|try again|503|provider/i);
    provider.state.mode = "healthy";
    mark("provider_outage_repair");

    provider.state.mode = "network";
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    await sendPromptExpectingFailure(page, "Show a repair action for synthetic network failure.", /network|connection|unavailable|try again/i);
    provider.state.mode = "healthy";
    mark("network_failure_repair");

    section = await openConnectedAccounts(page, inputs.clientBase, inputs.qaProvider);
    const [disconnectResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          new URL(response.url()).pathname.endsWith(`/api/keys/${inputs.qaProvider.keyName}`),
        { timeout: 15_000 },
      ),
      section.getByRole("button", { name: "Disconnect", exact: true }).click(),
    ]);
    if (disconnectResponse.status() !== 204) {
      fail(`Local Disconnect returned HTTP ${disconnectResponse.status()}`);
    }
    await section.getByText("No local credential saved", { exact: true }).waitFor({
      state: "visible",
      timeout: 15_000,
    });
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    mark("local_disconnect");

    await closeSettingsIfVisible(page);
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    const requestsBeforeDisconnectedSend = provider.state.chatRequests;
    const recoveryButtonsBefore = await page
      .getByRole("button", { name: "Connected Accounts", exact: true })
      .count();
    const disconnectedInput = page.getByTestId("text-input");
    await disconnectedInput.fill("Do not contact the provider while disconnected.");
    await page.getByTestId("send-button").click();
    const keyDialog = page.getByRole("dialog");
    await Promise.race([
      keyDialog.waitFor({ state: "visible", timeout: 25_000 }),
      page.getByText(/API key|required|Connected Accounts/i).last().waitFor({ state: "visible", timeout: 25_000 }),
    ]);
    await page.waitForTimeout(1000);
    if (provider.state.chatRequests !== requestsBeforeDisconnectedSend) {
      fail("Disconnected chat still contacted the synthetic provider");
    }
    if (await keyDialog.isVisible()) {
      await page.keyboard.press("Escape");
    }
    mark("disconnect_prevents_provider_request");

    const recovery = page
      .getByRole("button", { name: "Connected Accounts", exact: true })
      .nth(recoveryButtonsBefore);
    await recovery.waitFor({ state: "visible", timeout: 25_000 });
    await page.screenshot({
      path: path.join(evidenceDir, "03-missing-key-one-click-recovery.png"),
      fullPage: true,
    });
    await recovery.focus();
    await page.keyboard.press("Enter");
    await page.locator("#connected-accounts-label").waitFor({
      state: "visible",
      timeout: 25_000,
    });
    section = page.getByRole("region", { name: inputs.qaProvider.regionName });
    await section.getByText("No local credential saved", { exact: true }).waitFor({
      state: "visible",
      timeout: 15_000,
    });
    mark("missing_key_one_click_recovery");

    await saveProviderKey(page, section, VALID_KEY, inputs.qaProvider);
    await assertBrowserCredentialAbsent(page, context, [VALID_KEY, INVALID_KEY]);
    ledger.browserCredentialResidueChecks += 1;
    await closeSettingsIfVisible(page);
    await startFreshConversation(page, inputs.clientBase);
    await selectChatProvider(page, inputs.qaProvider);
    await sendPrompt(page, "Confirm key re-add restored a useful answer.", ANSWERS[3]);
    mark("valid_key_readded");
    await page.screenshot({ path: path.join(evidenceDir, "04-readded-key-answer.png"), fullPage: true });

    if (externalNetworkAttempts.length > 0) {
      fail("Browser attempted non-loopback traffic during the fenced lifecycle");
    }
    if (unexpectedHttpFailures.length > 0) {
      fail("Unexpected browser-visible HTTP failures occurred during lifecycle QA");
    }
    if (Object.values(ledger.stages).some((status) => status !== "PASS")) {
      fail("One or more required lifecycle stages did not pass");
    }

    ledger.result = "PASS";
    ledger.providerSnapshot = {
      modelsRequests: provider.state.modelsRequests,
      chatRequests: provider.state.chatRequests,
      successfulAnswers: provider.state.successfulAnswers,
    };
    ledger.externalNetworkAttemptCount = externalNetworkAttempts.length;
    ledger.unexpectedHttpFailures = unexpectedHttpFailures;
    fs.writeFileSync(path.join(evidenceDir, "sanitized-ledger.json"), `${JSON.stringify(ledger, null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    return {
      result: "PASS",
      mode: "browser-lifecycle",
      provider: ledger.provider,
      stages: ledger.stages,
      providerSnapshot: ledger.providerSnapshot,
      externalNetworkAttemptCount: 0,
      unexpectedHttpFailures: [],
      browserCredentialResidueChecks: ledger.browserCredentialResidueChecks,
      evidenceDirectory: "<private>",
    };
  } catch (error) {
    ledger.result = "FAIL";
    ledger.providerSnapshot = {
      modelsRequests: provider.state.modelsRequests,
      chatRequests: provider.state.chatRequests,
      successfulAnswers: provider.state.successfulAnswers,
    };
    if (page) {
      await page
        .screenshot({ path: path.join(evidenceDir, "99-failure.png"), fullPage: true })
        .catch(() => undefined);
    }
    fs.writeFileSync(path.join(evidenceDir, "sanitized-ledger.json"), `${JSON.stringify(ledger, null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    throw error;
  } finally {
    if (browser) {
      await browser.close();
    }
    await stopServer(provider.server);
  }
}

async function runSelfTest() {
  const qaProvider = parseQAProvider();
  const provider = await startSyntheticProvider(0, qaProvider);
  try {
    if (qaProvider.protocol === "openai") {
      const models = await fetch(`${provider.baseUrl}/v1/models`);
      if (!models.ok || (await models.json()).data?.[0]?.id !== qaProvider.modelId) {
        fail("Synthetic model inventory self-test failed");
      }
    }
    const requestPath = qaProvider.protocol === "anthropic" ? "/v1/messages" : "/v1/chat/completions";
    const authHeaders =
      qaProvider.protocol === "anthropic"
        ? { "x-api-key": INVALID_KEY, "anthropic-version": "2023-06-01" }
        : { authorization: `Bearer ${INVALID_KEY}` };
    const invalid = await fetch(`${provider.baseUrl}${requestPath}`, {
      method: "POST",
      headers: {
        ...authHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify({ model: qaProvider.modelId, max_tokens: 128, stream: true, messages: [] }),
    });
    if (invalid.status !== 401) {
      fail("Synthetic invalid-key self-test failed");
    }
    const validAuthHeaders =
      qaProvider.protocol === "anthropic"
        ? { "x-api-key": VALID_KEY, "anthropic-version": "2023-06-01" }
        : { authorization: `Bearer ${VALID_KEY}` };
    const valid = await fetch(`${provider.baseUrl}${requestPath}`, {
      method: "POST",
      headers: {
        ...validAuthHeaders,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: qaProvider.modelId,
        max_tokens: 128,
        stream: true,
        messages: [{ role: "user", content: "first useful" }],
      }),
    });
    if (!valid.ok || !(await valid.text()).includes(ANSWERS[0])) {
      fail("Synthetic useful-answer self-test failed");
    }
    return {
      result: "PASS",
      mode: "self-test",
      provider: `synthetic-${qaProvider.slug}-compatible-loopback`,
      modelsRequests: provider.state.modelsRequests,
      chatRequests: provider.state.chatRequests,
      successfulAnswers: provider.state.successfulAnswers,
      evidenceDirectory: "<private>",
    };
  } finally {
    await stopServer(provider.server);
  }
}

function runStorageSelfTest() {
  assertSerializedCredentialAbsent(
    {
      storageState: {
        cookies: [],
        origins: [{ localStorage: [{ name: "theme", value: "dark" }] }],
      },
      pageState: { indexedDb: [], sessionStorage: {} },
    },
    [VALID_KEY, INVALID_KEY],
  );

  let localStorageLeakRejected = false;
  try {
    assertSerializedCredentialAbsent(
      { pageState: { localStorage: { providerDraft: VALID_KEY } } },
      [VALID_KEY, INVALID_KEY],
    );
  } catch (error) {
    localStorageLeakRejected =
      error.message === "Provider credential leaked into browser persistence" &&
      !error.message.includes(VALID_KEY);
  }

  let indexedDbLeakRejected = false;
  try {
    assertSerializedCredentialAbsent(
      { pageState: { indexedDb: [{ values: [{ credential: INVALID_KEY }] }] } },
      [VALID_KEY, INVALID_KEY],
    );
  } catch (error) {
    indexedDbLeakRejected =
      error.message === "Provider credential leaked into browser persistence" &&
      !error.message.includes(INVALID_KEY);
  }

  if (!localStorageLeakRejected || !indexedDbLeakRejected) {
    fail("Browser credential persistence guard did not fail closed");
  }
  return {
    result: "PASS",
    mode: "storage-self-test",
    cleanStateAccepted: true,
    localStorageLeakRejected,
    indexedDbLeakRejected,
  };
}

async function main() {
  if (process.argv.includes("--storage-self-test")) {
    process.stdout.write(`${JSON.stringify(runStorageSelfTest())}\n`);
    return;
  }
  if (process.argv.includes("--self-test")) {
    process.stdout.write(`${JSON.stringify(await runSelfTest())}\n`);
    return;
  }
  if (process.argv.includes("--contract-check")) {
    assertSafeInputs({ requireRestart: false });
    process.stdout.write(`${JSON.stringify({ result: "PASS", mode: "contract-check" })}\n`);
    return;
  }
  const inputs = assertSafeInputs({ requireRestart: true });
  process.stdout.write(`${JSON.stringify(await runBrowserLifecycle(inputs))}\n`);
}

main().catch((error) => {
  process.stderr.write(`API-key lifecycle QA failed: ${error.message}\n`);
  process.exitCode = 1;
});
