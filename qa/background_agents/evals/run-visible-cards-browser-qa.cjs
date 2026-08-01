#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * Browser QA for visible background-agent cards.
 *
 * Public-safe by design:
 * - Requires explicit local JWT opt-in.
 * - Defaults to a synthetic placeholder email; real local account email must come from env/args.
 * - Writes only counts, hashes, and generic verdicts. No screenshots, conversation IDs, raw replies,
 *   private URLs, or account identifiers are written to the public repo.
 */

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const {
  assertNonOwnerQaSelection,
  cleanupQaRunArtifacts,
  installQaRequestIsolation,
} = require("./browser-qa-safety.cjs");

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_ROOT = path.join(REPO_ROOT, "viventium_v0_4", "LibreChat");
const LOCAL_JWT_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_LOCAL_JWT";
const PHASE_B_EXPECTATION_ENV = "VIVENTIUM_QA_EXPECT_PHASE_B";
const DEFAULT_PROMPT =
  "I am evaluating whether to build a synthetic workflow analytics product because one example buyer already pays a lot for a generic tool. I have obvious confirmation bias about whether this product idea is worth doing. Please give me a fast answer, and let the Red Team and Confirmation Bias background checks run visibly by name.";
const REQUIRED_CARD_NAMES = ["Red Team", "Confirmation Bias"];
const DEFAULT_REQUIRED_CORTEX_AGENT_IDS_BY_NAME = {
  "Red Team": "agent_viventium_red_team_95aeb3",
  "Confirmation Bias": "agent_viventium_confirmation_bias_95aeb3",
};
const EXPECTED_ACTIVATION_PROVIDER = "groq";
const EXPECTED_ACTIVATION_MODEL = "qwen/qwen3.6-27b";
const FORBIDDEN_VISIBLE_PATTERNS = [
  /\bAdditional thought\b/i,
  /i (?:can'?t|cannot) control (?:the )?(?:background )?(?:cards|agents|cortices)/i,
  /there(?:'s| is) nothing (?:to show|visible)/i,
  /\b(?:spin up|launch|start|run) (?:the )?background (?:agents|cortices)\b/i,
];
const MAIN_ERROR_PATTERNS = [
  /something went wrong/i,
  /an error occurred while processing the request/i,
  /\bterminated\b/i,
  /\brate limit\b/i,
  /\brate_limit\b/i,
];
const CRITICAL_HTTP_PATH_PATTERNS = [
  /\/api\/agents\/chat\b/i,
  /\/api\/auth\/refresh\b/i,
  /\/api\/messages\b/i,
];

function parseArgs(argv) {
  const startedAt = new Date().toISOString();
  const promptMarker = `qa-${hashValue(startedAt)}`;
  const args = {
    startedAt,
    qaRunId: promptMarker,
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || "http://localhost:3190",
    apiBase: process.env.VIVENTIUM_QA_API_BASE || "http://localhost:3180",
    qaEmail: process.env.VIVENTIUM_QA_EMAIL || "qa@example.com",
    agentId: process.env.VIVENTIUM_QA_AGENT_ID || "agent_viventium_main_95aeb3",
    out:
      process.env.VIVENTIUM_QA_REPORT_PATH ||
      path.join(
        REPO_ROOT,
        "qa",
        "background_agents",
        "visible_cards_browser_qa_2026-05-10.md",
      ),
    headless: process.env.VIVENTIUM_QA_HEADLESS !== "0",
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 180000),
    expectedPhaseB: parseExpectedPhaseBExpectation(
      process.env[PHASE_B_EXPECTATION_ENV],
    ),
    privateTranscriptPath:
      process.env.VIVENTIUM_QA_PRIVATE_TRANSCRIPT_PATH || "",
    prompt:
      process.env.VIVENTIUM_QA_PROMPT ||
      `${DEFAULT_PROMPT} Synthetic QA marker: ${promptMarker}.`,
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
    } else if (arg === "--agent-id") {
      args.agentId = next;
      i += 1;
    } else if (arg === "--out") {
      args.out = next;
      i += 1;
    } else if (arg === "--headed") {
      args.headless = false;
    } else if (arg === "--headless") {
      args.headless = true;
    } else if (arg === "--prompt") {
      args.prompt = next;
      i += 1;
    }
  }
  return args;
}

function hashValue(value, length = 16) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, length);
}

function parseExpectedPhaseBExpectation(value) {
  const expectedPhaseB = String(value || "generated")
    .trim()
    .toLowerCase();
  if (!["generated", "nta"].includes(expectedPhaseB)) {
    throw new Error(
      `${PHASE_B_EXPECTATION_ENV} must be either generated or nta`,
    );
  }
  return expectedPhaseB;
}

function parseRequiredCortexAgentIdsByName() {
  const raw = process.env.VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON;
  if (!raw) {
    return { ...DEFAULT_REQUIRED_CORTEX_AGENT_IDS_BY_NAME };
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(
      `Invalid VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON: ${sanitizePublicError(error.message)}`,
    );
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(
      "Invalid VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON: expected object",
    );
  }

  const merged = { ...DEFAULT_REQUIRED_CORTEX_AGENT_IDS_BY_NAME };
  for (const name of REQUIRED_CARD_NAMES) {
    if (!Object.prototype.hasOwnProperty.call(parsed, name)) {
      continue;
    }
    const agentId = String(parsed[name] || "").trim();
    if (!agentId) {
      throw new Error(
        `Invalid VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON: missing agent id for ${name}`,
      );
    }
    merged[name] = agentId;
  }
  return merged;
}

function sanitizePublicError(value) {
  return String(value || "qa_failed")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "<email>")
    .replace(/https?:\/\/[^\s)]+/gi, "<url>")
    .replace(/\/Users\/[^\s)]+/g, "<path>")
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, "Bearer <redacted>")
    .replace(/sk-[A-Za-z0-9._-]+/g, "sk-<redacted>")
    .replace(/\s+/g, " ")
    .slice(0, 220);
}

function sanitizeRouteClass(url) {
  try {
    const parsed = new URL(url);
    const pathOnly = parsed.pathname || "/";
    if (/^\/c\//.test(pathOnly)) {
      return "/c/<conversation>";
    }
    return pathOnly
      .replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, "<uuid>")
      .slice(0, 120);
  } catch {
    return "<url>";
  }
}

function summarizeRouteClasses(items) {
  const counts = new Map();
  for (const item of items) {
    const key = item || "<unknown>";
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([route, count]) => `${route} (${count})`);
}

function publicInterpretation(result) {
  if (result.pass) {
    return "PASS: required cards were visible, the parent answer was visible and durable, and terminal insights persisted after reload.";
  }
  if (
    result.parentCortexOnly === true ||
    result.parentHasVisibleMainAnswer === false
  ) {
    return (
      "FAIL: required cards may be present, but the originating assistant parent did not preserve " +
      "or recover visible answer text. Cortex-only parent messages are not acceptable."
    );
  }
  if (
    result.initialMainAnswerVisible === false ||
    result.reloadMainAnswerVisible === false
  ) {
    return (
      "FAIL: stored parent answer exists, but the browser did not prove the parent answer stayed " +
      "visible before and after reload."
    );
  }
  if ((result.storedErrorNames || []).length > 0) {
    return (
      "FAIL: card visibility and persistence were present, but one or more required cortex parts " +
      "stored terminal errors instead of successful insights. Treat as a provider/fallback or " +
      "background-execution blocker, not a UI-only pass."
    );
  }
  if ((result.cardNames || []).length === REQUIRED_CARD_NAMES.length) {
    return (
      "FAIL: required cards were visible, but stored message verification did not prove successful " +
      "terminal insights."
    );
  }
  return "FAIL: required browser-visible card evidence was incomplete.";
}

function isCriticalHttpRoute(url) {
  const route = sanitizeRouteClass(url);
  return CRITICAL_HTTP_PATH_PATTERNS.some((pattern) => pattern.test(route));
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
  return {
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, ".env")),
    ...parseEnvFile(path.join(REPO_ROOT, ".env")),
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
    userObjectId: user._id,
    accessToken,
    refreshToken,
    meiliClient:
      env.MEILI_HOST && env.MEILI_MASTER_KEY
        ? new MeiliSearch({
            host: env.MEILI_HOST,
            apiKey: env.MEILI_MASTER_KEY,
          })
        : null,
    userEmailHash: hashValue(user.email),
    async close() {
      await db
        .collection("sessions")
        .deleteOne({ _id: sessionId })
        .catch(() => {});
      await client.close();
    },
  };
}

async function verifyQaAgentProvisioning({
  qaAuth,
  mainAgentId,
  requiredCortexAgentIdsByName,
}) {
  const requiredIds = [
    mainAgentId,
    ...Object.values(requiredCortexAgentIdsByName),
  ];
  const agents = await qaAuth.db
    .collection("agents")
    .find(
      {
        id: { $in: requiredIds },
      },
      {
        projection: {
          id: 1,
          name: 1,
          background_cortices: 1,
          fallback_llm_provider: 1,
          fallback_llm_model: 1,
          fallback_llm_model_parameters: 1,
        },
      },
    )
    .toArray();
  const byId = new Map(agents.map((agent) => [agent.id, agent]));
  const missingRequiredAgentHashes = requiredIds
    .filter((id) => !byId.has(id))
    .map((id) => hashValue(id));
  const requiredCortexFallbackNames = REQUIRED_CARD_NAMES.filter((name) => {
    const agent = byId.get(requiredCortexAgentIdsByName[name]);
    return (
      String(agent?.fallback_llm_provider || "").trim() &&
      String(
        agent?.fallback_llm_model ||
          agent?.fallback_llm_model_parameters?.model ||
          "",
      ).trim()
    );
  });
  const mainAgent = byId.get(mainAgentId);
  const liveCortexEntries = new Map(
    (Array.isArray(mainAgent?.background_cortices)
      ? mainAgent.background_cortices
      : []
    )
      .filter((entry) => entry?.agent_id)
      .map((entry) => [entry.agent_id, entry]),
  );
  const activationDriftNames = REQUIRED_CARD_NAMES.filter((name) => {
    const agentId = requiredCortexAgentIdsByName[name];
    const activation = liveCortexEntries.get(agentId)?.activation || {};
    return (
      String(activation.provider || "").trim() !==
        EXPECTED_ACTIVATION_PROVIDER ||
      String(activation.model || "").trim() !== EXPECTED_ACTIVATION_MODEL
    );
  });
  const attachedCortexIds = [...liveCortexEntries.keys()];
  const attachedCortexAgents = attachedCortexIds.length
    ? await qaAuth.db
        .collection("agents")
        .find(
          { id: { $in: attachedCortexIds } },
          { projection: { id: 1, name: 1 } },
        )
        .toArray()
    : [];
  const runtimeAttachedCortexNames = attachedCortexAgents
    .map((agent) => String(agent?.name || "").trim())
    .filter(Boolean)
    .sort();
  return {
    runtimeRequiredAgentCount: agents.length,
    runtimeMissingRequiredAgentHashes: missingRequiredAgentHashes,
    runtimeCortexFallbackNames: requiredCortexFallbackNames,
    runtimeActivationExpectedProvider: EXPECTED_ACTIVATION_PROVIDER,
    runtimeActivationExpectedModelHash: hashValue(EXPECTED_ACTIVATION_MODEL),
    runtimeActivationDriftNames: activationDriftNames,
    runtimeAttachedCortexNames,
    runtimeActivationConfigPass: activationDriftNames.length === 0,
    runtimeProvisioningPass:
      missingRequiredAgentHashes.length === 0 &&
      requiredCortexFallbackNames.length === REQUIRED_CARD_NAMES.length &&
      activationDriftNames.length === 0,
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

async function installAccessToken(page, localAccessToken = "") {
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
      hasToken: Boolean(
        payload &&
        typeof payload.token === "string" &&
        payload.token.length > 0,
      ),
      token: payload && typeof payload.token === "string" ? payload.token : "",
    };
  });
  if (!refresh.ok || !refresh.hasToken) {
    if (!localAccessToken) {
      throw new Error(`auth_refresh_failed_status_${refresh.status}`);
    }
    await page.evaluate((token) => {
      window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: token }));
    }, localAccessToken);
    await page.waitForTimeout(250);
    return {
      mode: "direct_access_token_fallback",
      refreshStatus: refresh.status,
    };
  }
  await page.evaluate((token) => {
    window.dispatchEvent(new CustomEvent("tokenUpdated", { detail: token }));
  }, refresh.token);
  await page.waitForTimeout(250);
  return { mode: "refresh_cookie", refreshStatus: refresh.status };
}

async function submitPrompt(page, prompt) {
  const input = page
    .getByLabel("Message input")
    .or(page.getByPlaceholder(/^Message Viventium$/))
    .last();
  await input.waitFor({ state: "visible", timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId("send-button").last().click({ timeout: 30000 });
  await page
    .waitForFunction(
      () => /^\/c\/(?!new$)[^/?#]+/.test(window.location.pathname),
      undefined,
      { timeout: 60000 },
    )
    .catch(() => {});
}

async function visibleBodyText(page) {
  return page.locator("body").innerText({ timeout: 10000 });
}

async function visibleCortexRowTexts(page) {
  return page
    .locator(".progress-text-wrapper button")
    .evaluateAll((buttons) =>
      buttons
        .map((button) => (button.innerText || "").replace(/\s+/g, " ").trim())
        .filter(Boolean),
    );
}

function evaluateVisibleState(text, cortexRowTexts = [], knownCortexNames = REQUIRED_CARD_NAMES) {
  const cardNames = [...new Set(knownCortexNames)].filter((name) =>
    cortexRowTexts.some((rowText) => rowText.includes(name)),
  ).sort();
  const forbiddenMatches = FORBIDDEN_VISIBLE_PATTERNS.filter((pattern) =>
    pattern.test(text),
  ).map((pattern) => pattern.toString());
  const mainErrorMatches = MAIN_ERROR_PATTERNS.filter((pattern) =>
    pattern.test(text),
  ).map((pattern) => pattern.toString());
  return {
    cardNames,
    forbiddenMatches,
    mainErrorMatches,
    hasBackgroundAgentFooter:
      /Background agent:\s*(Red Team|Confirmation Bias)/i.test(text),
    hasTerminalState: /Analysis complete|Error occurred|Did not activate/i.test(
      text,
    ),
    hasWhyThisRan: /Why this ran/i.test(text),
  };
}

function extractConversationIdFromUrl(url) {
  try {
    const match = new URL(url).pathname.match(/^\/c\/([^/?#]+)$/);
    return match ? match[1] : "";
  } catch {
    return "";
  }
}

function normalizeCortexName(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function extractTextFromContentPart(part) {
  if (!part || part.type !== "text") {
    return "";
  }
  if (typeof part.text === "string") {
    return part.text;
  }
  if (typeof part.text?.value === "string") {
    return part.text.value;
  }
  return "";
}

function extractVisibleAnswerTextFromMessage(message) {
  if (!message || typeof message !== "object") {
    return "";
  }
  const text = typeof message.text === "string" ? message.text : "";
  const partText = Array.isArray(message.content)
    ? message.content.map(extractTextFromContentPart).filter(Boolean).join("\n")
    : "";
  const parts = [text, partText]
    .filter((part) => typeof part === "string" && part.trim().length > 0)
    .map((part) => part.trim());
  return [...new Set(parts)].join("\n").trim();
}

function isNoVisibleAnswerMarker(text) {
  return String(text || "").trim() === "{NTA}";
}

function normalizeVisibleTextForAssertion(value) {
  return String(value || "")
    .replace(/[`*_#>\\-]+/g, " ")
    .replace(/\s+([:;,.!?])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function novelTokenRatio(candidate, baseline) {
  const tokenize = (value) =>
    String(value || "")
      .toLowerCase()
      .match(/[a-z0-9]{3,}/g) || [];
  const candidateTokens = tokenize(candidate);
  if (candidateTokens.length === 0) {
    return 0;
  }
  const baselineTokens = new Set(tokenize(baseline));
  return candidateTokens.filter((token) => !baselineTokens.has(token)).length /
    candidateTokens.length;
}

function isSubstantiveCortexInsight({ insight, parentText } = {}) {
  const candidate = normalizeVisibleTextForAssertion(insight);
  const baseline = normalizeVisibleTextForAssertion(parentText);
  if (!candidate || /^\{NTA\}$/i.test(candidate)) {
    return false;
  }
  let residual = candidate;
  if (baseline) {
    const candidateLower = candidate.toLowerCase();
    const baselineLower = baseline.toLowerCase();
    const overlapIndex = candidateLower.indexOf(baselineLower);
    if (overlapIndex >= 0) {
      residual = `${candidate.slice(0, overlapIndex)} ${candidate.slice(
        overlapIndex + baseline.length,
      )}`.trim();
    }
  }
  const baselineTokens = new Set(
    baseline.toLowerCase().match(/[a-z0-9]{3,}/g) || [],
  );
  const novelTokens = (residual.toLowerCase().match(/[a-z0-9]{3,}/g) || []).filter(
    (token) => !baselineTokens.has(token),
  );
  return residual.length >= 20 && new Set(novelTokens).size >= 3;
}

function phaseBExpectationPass({
  expectedPhaseB,
  phaseBFollowUpCount,
  phaseBStructuredFollowUpCount,
  phaseBDecisionResult,
  phaseBLlmResult,
  phaseBSuppressionReason,
  phaseBFollowUpTextLength,
  phaseBNovelTokenRatio,
  phaseBInitialVisible,
  phaseBReloadVisible,
  phaseBNtaMarkerVisible,
}) {
  if (expectedPhaseB === "generated") {
    return (
      phaseBStructuredFollowUpCount === 1 &&
      phaseBDecisionResult === "persisted" &&
      phaseBLlmResult === "generated" &&
      phaseBFollowUpTextLength > 0 &&
      phaseBNovelTokenRatio >= 0.1 &&
      phaseBInitialVisible &&
      phaseBReloadVisible
    );
  }
  if (expectedPhaseB === "nta") {
    return (
      phaseBFollowUpCount === 0 &&
      phaseBStructuredFollowUpCount === 0 &&
      phaseBDecisionResult === "suppressed" &&
      phaseBLlmResult === "nta" &&
      phaseBSuppressionReason === "no_response_tag" &&
      phaseBFollowUpTextLength === 0 &&
      !phaseBInitialVisible &&
      !phaseBReloadVisible &&
      !phaseBNtaMarkerVisible
    );
  }
  return false;
}

function requiredCortexCoveragePass({
  requiredNames,
  initialNames,
  reloadNames,
  storedNames,
  terminalNames,
  completeInsightNames,
}) {
  const toNameSet = (values) =>
    new Set((Array.isArray(values) ? values : []).map((value) => String(value)));
  const required = toNameSet(requiredNames);
  const initial = toNameSet(initialNames);
  const reload = toNameSet(reloadNames);
  const stored = toNameSet(storedNames);
  const terminal = toNameSet(terminalNames);
  const complete = toNameSet(completeInsightNames);
  const containsAll = (haystack, needles) =>
    [...needles].every((name) => haystack.has(name));
  const sameNames = (left, right) =>
    left.size === right.size && containsAll(left, right);

  return (
    required.size > 0 &&
    containsAll(initial, required) &&
    containsAll(stored, required) &&
    sameNames(initial, reload) &&
    sameNames(initial, stored) &&
    sameNames(stored, terminal) &&
    sameNames(stored, complete)
  );
}

function bodyContainsMainAnswer(bodyText, answerText) {
  const answer = normalizeVisibleTextForAssertion(answerText);
  if (answer.length < 24) {
    return false;
  }
  const body = normalizeVisibleTextForAssertion(bodyText);
  const snippet = answer.slice(0, Math.min(answer.length, 80));
  return body.includes(snippet);
}

async function waitForVisibleAnswerText(page, answerText, timeoutMs) {
  if (!normalizeVisibleTextForAssertion(answerText)) {
    return false;
  }
  return page
    .waitForFunction(
      (expectedText) => {
        const normalize = (value) =>
          String(value || "")
            .replace(/[`*_#>\\-]+/g, " ")
            .replace(/\s+([:;,.!?])/g, "$1")
            .replace(/\s+/g, " ")
            .trim();
        const answer = normalize(expectedText);
        const snippet = answer.slice(0, Math.min(answer.length, 80));
        return Boolean(snippet) && normalize(document.body.innerText || "").includes(snippet);
      },
      answerText,
      { timeout: timeoutMs },
    )
    .then(() => true)
    .catch(() => false);
}

function uniqueNamesFromParts(parts, predicate) {
  const names = new Set();
  for (const part of parts) {
    const name = normalizeCortexName(
      part?.cortex_name || part?.cortexName || part?.name,
    );
    if (!name) {
      continue;
    }
    if (!predicate(part)) {
      continue;
    }
    names.add(name);
  }
  return [...names].sort();
}

async function verifyStoredCortexParts({ qaAuth, conversationId, prompt }) {
  if (!conversationId) {
    throw new Error("missing_conversation_id_for_db_verification");
  }
  const allMessages = await qaAuth.db
    .collection("messages")
    .find({
      user: qaAuth.userId,
      conversationId,
    })
    .sort({ createdAt: 1, _id: 1 })
    .toArray();
  const messages = allMessages.filter(
    (message) => message.isCreatedByUser === false,
  );
  const userMessages = allMessages.filter(
    (message) => message.isCreatedByUser === true,
  );
  const originatingUserMessage = [...userMessages]
    .reverse()
    .find((message) => (prompt ? message.text === prompt : true));
  const parentMessage = originatingUserMessage
    ? messages.find(
        (message) =>
          message.parentMessageId === originatingUserMessage.messageId,
      )
    : messages[0];
  const parentText = extractVisibleAnswerTextFromMessage(parentMessage);
  const parentCortexParts = Array.isArray(parentMessage?.content)
    ? parentMessage.content.filter(
        (part) => part && String(part.type || "").startsWith("cortex_"),
      )
    : [];
  const parentHasVisibleMainAnswer =
    parentText.trim().length > 0 && !isNoVisibleAnswerMarker(parentText);
  const parentCortexOnly =
    Boolean(parentMessage) &&
    parentCortexParts.length > 0 &&
    !parentHasVisibleMainAnswer;
  const phaseBFollowUpCount = parentMessage
    ? messages.filter(
        (message) =>
          message.parentMessageId === parentMessage.messageId &&
          extractVisibleAnswerTextFromMessage(message).trim().length > 0,
      ).length
    : 0;
  const phaseBFollowUps = parentMessage
    ? messages.filter((message) => {
        const metadata = message?.metadata;
        return (
          metadata?.viventium?.type === "cortex_followup" &&
          metadata?.viventium?.parentMessageId === parentMessage.messageId
        );
      })
    : [];
  const phaseBFollowUpText = phaseBFollowUps
    .map(extractVisibleAnswerTextFromMessage)
    .filter(Boolean)
    .join("\n")
    .trim();
  const phaseBDecision =
    parentMessage?.metadata?.viventium?.cortexFollowUpDecision ||
    phaseBFollowUps[0]?.metadata?.viventium?.cortexFollowUpDecision ||
    null;
  const cortexParts = messages.flatMap((message) =>
    Array.isArray(message.content)
      ? message.content.filter(
          (part) => part && String(part.type || "").startsWith("cortex_"),
        )
      : [],
  );
  const storedCardNames = uniqueNamesFromParts(cortexParts, () => true);
  const storedTerminalNames = uniqueNamesFromParts(
    cortexParts,
    (part) =>
      part.type === "cortex_insight" &&
      ["complete", "error", "skipped", "did_not_activate"].includes(
        String(part.status || ""),
      ),
  );
  const storedCompleteInsightNames = uniqueNamesFromParts(
    cortexParts,
    (part) =>
      part.type === "cortex_insight" &&
      String(part.status || "") === "complete" &&
      typeof part.insight === "string" &&
      part.insight.trim().length > 0,
  );
  const storedSubstantiveInsightNames = uniqueNamesFromParts(
    cortexParts,
    (part) =>
      part.type === "cortex_insight" &&
      String(part.status || "") === "complete" &&
      isSubstantiveCortexInsight({ insight: part.insight, parentText }),
  );
  const storedErrorNames = uniqueNamesFromParts(
    cortexParts,
    (part) =>
      part.type === "cortex_insight" && String(part.status || "") === "error",
  );
  const publicState = {
    conversationIdHash: hashValue(conversationId),
    parentMessageHash: hashValue(parentMessage?.messageId || ""),
    parentMainAnswerTextLength: parentText.length,
    parentHasVisibleMainAnswer,
    parentCortexOnly,
    phaseBFollowUpCount,
    phaseBStructuredFollowUpCount: phaseBFollowUps.length,
    phaseBDecisionResult: String(phaseBDecision?.result || ""),
    phaseBLlmResult: String(phaseBDecision?.llmResult || ""),
    phaseBSelectedStrategy: String(phaseBDecision?.selectedStrategy || ""),
    phaseBSuppressionReason: String(phaseBDecision?.suppressionReason || ""),
    phaseBFollowUpTextLength: phaseBFollowUpText.length,
    phaseBNovelTokenRatio: novelTokenRatio(phaseBFollowUpText, parentText),
    assistantMessageCount: messages.length,
    storedCortexPartCount: cortexParts.length,
    storedCardNames,
    storedTerminalNames,
    storedCompleteInsightNames,
    storedSubstantiveInsightNames,
    storedErrorNames,
  };
  Object.defineProperty(publicState, "parentMainAnswerText", {
    value: parentText,
    enumerable: false,
  });
  Object.defineProperty(publicState, "phaseBFollowUpText", {
    value: phaseBFollowUpText,
    enumerable: false,
  });
  Object.defineProperty(publicState, "cortexInsightTexts", {
    value: cortexParts
      .filter((part) => part?.type === "cortex_insight" && part?.status === "complete")
      .map((part) => ({
        name: normalizeCortexName(part.cortex_name || part.cortexName || part.name),
        insight: String(part.insight || ""),
      })),
    enumerable: false,
  });
  return publicState;
}

async function waitForStoredCortexParts({
  qaAuth,
  conversationId,
  prompt,
  timeoutMs,
}) {
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() < deadline) {
    latest = await verifyStoredCortexParts({ qaAuth, conversationId, prompt });
    const hasTerminalCards = requiredCortexCoveragePass({
      requiredNames: REQUIRED_CARD_NAMES,
      initialNames: latest.storedCardNames,
      reloadNames: latest.storedCardNames,
      storedNames: latest.storedCardNames,
      terminalNames: latest.storedTerminalNames,
      completeInsightNames: latest.storedTerminalNames,
    });
    const hasSuccessfulCards = requiredCortexCoveragePass({
      requiredNames: REQUIRED_CARD_NAMES,
      initialNames: latest.storedCardNames,
      reloadNames: latest.storedCardNames,
      storedNames: latest.storedCardNames,
      terminalNames: latest.storedCompleteInsightNames,
      completeInsightNames: latest.storedCompleteInsightNames,
    });
    const hasTerminalDecision = ["persisted", "suppressed", "empty", "skipped"].includes(
      latest.phaseBDecisionResult,
    );
    const decisionIsDurable =
      hasTerminalDecision &&
      (latest.phaseBDecisionResult !== "persisted" ||
        latest.phaseBStructuredFollowUpCount === 1);
    if (
      (hasTerminalCards || hasSuccessfulCards) &&
      latest.parentHasVisibleMainAnswer === true &&
      latest.parentCortexOnly !== true &&
      decisionIsDurable
    ) {
      return latest;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return latest || verifyStoredCortexParts({ qaAuth, conversationId, prompt });
}

async function waitForConversationForPrompt({
  qaAuth,
  prompt,
  startedAt,
  timeoutMs = 60000,
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
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("missing_current_qa_conversation_for_prompt");
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const requiredCortexAgentIdsByName = parseRequiredCortexAgentIdsByName();
  const env = localEnv();
  let qaAuth;
  let browser;
  let privateTranscript = null;
  const trackedConversationIds = new Set();
  const startedAt = args.startedAt;
  const result = {
    startedAt,
    expectedPhaseB: args.expectedPhaseB,
    clientBaseHash: hashValue(args.clientBase),
    apiBaseHash: hashValue(args.apiBase),
    qaEmailHash: hashValue(args.qaEmail),
    agentIdHash: hashValue(args.agentId),
    promptHash: hashValue(args.prompt),
    conversationIdHash: "",
    cardNames: [],
    forbiddenMatches: [],
    mainErrorMatches: [],
    reloadCardNames: [],
    parentMessageHash: "",
    parentMainAnswerTextLength: 0,
    parentHasVisibleMainAnswer: false,
    parentCortexOnly: false,
    initialMainAnswerVisible: false,
    reloadMainAnswerVisible: false,
    phaseBFollowUpCount: 0,
    phaseBStructuredFollowUpCount: 0,
    phaseBDecisionResult: "",
    phaseBLlmResult: "",
    phaseBSelectedStrategy: "",
    phaseBSuppressionReason: "",
    phaseBFollowUpTextLength: 0,
    phaseBNovelTokenRatio: 0,
    phaseBInitialVisible: false,
    phaseBReloadVisible: false,
    phaseBNtaMarkerVisible: false,
    storedCardNames: [],
    storedTerminalNames: [],
    storedCompleteInsightNames: [],
    storedErrorNames: [],
    runtimeRequiredAgentCount: 0,
    runtimeMissingRequiredAgentHashes: [],
    runtimeCortexFallbackNames: [],
    runtimeActivationExpectedProvider: EXPECTED_ACTIVATION_PROVIDER,
    runtimeActivationExpectedModelHash: hashValue(EXPECTED_ACTIVATION_MODEL),
    runtimeActivationDriftNames: [],
    runtimeAttachedCortexNames: [],
    runtimeActivationConfigPass: false,
    runtimeProvisioningPass: false,
    usedConversationFallbackNavigation: false,
    directAccessTokenFallbackUsed: false,
    expectedLocalQaBootstrapHttpErrorCount: 0,
    pass: false,
    error: null,
  };

  try {
    qaAuth = await createQaAuth({ args, env });
    const provisioningState = await verifyQaAgentProvisioning({
      qaAuth,
      mainAgentId: args.agentId,
      requiredCortexAgentIdsByName,
    });
    Object.assign(result, provisioningState);
    if (!provisioningState.runtimeProvisioningPass) {
      throw new Error("runtime_agent_bundle_not_provisioned");
    }
    const { chromium } = require(
      path.join(LIBRECHAT_ROOT, "node_modules", "playwright"),
    );
    browser = await chromium.launch({
      channel: "chrome",
      headless: args.headless,
    });
    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1440, height: 1100 },
    });
    await attachAuthCookies({ context, args, qaAuth });
    const page = await context.newPage();
    await installQaRequestIsolation(page, { qaRunId: args.qaRunId });
    const consoleErrors = [];
    const failedRequests = [];
    const failedRequestRoutes = [];
    const httpErrorRoutes = [];
    const recordAuthState = (state) => {
      if (state?.mode !== "direct_access_token_fallback") {
        return;
      }
      result.directAccessTokenFallbackUsed = true;
      if (state.refreshStatus !== 401) {
        return;
      }
      for (let index = httpErrorRoutes.length - 1; index >= 0; index -= 1) {
        if (httpErrorRoutes[index] !== "/api/auth/refresh 401") {
          continue;
        }
        httpErrorRoutes.splice(index, 1);
        result.expectedLocalQaBootstrapHttpErrorCount += 1;
      }
    };
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(hashValue(message.text()));
      }
    });
    page.on("requestfailed", (request) => {
      const failureText = request.failure()?.errorText || "";
      if (/ERR_ABORTED|NS_BINDING_ABORTED|Target closed/i.test(failureText)) {
        return;
      }
      const routeClass = sanitizeRouteClass(request.url());
      failedRequests.push(hashValue(`${routeClass} ${failureText}`));
      failedRequestRoutes.push(routeClass);
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && isCriticalHttpRoute(response.url())) {
        httpErrorRoutes.push(
          `${sanitizeRouteClass(response.url())} ${response.status()}`,
        );
      }
    });

    await page.goto(args.clientBase, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    let authState = await installAccessToken(page, qaAuth.accessToken);
    recordAuthState(authState);
    await page.goto(`${args.clientBase}/c/new`, {
      waitUntil: "domcontentloaded",
      timeout: 60000,
    });
    authState = await installAccessToken(page, qaAuth.accessToken);
    recordAuthState(authState);
    if (!/\/c\/new$/.test(new URL(page.url()).pathname)) {
      await page.goto(`${args.clientBase}/c/new`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      authState = await installAccessToken(page, qaAuth.accessToken);
      recordAuthState(authState);
    }
    await page.waitForFunction(
      () => window.location.pathname === "/c/new",
      undefined,
      { timeout: 10000 },
    );
    await submitPrompt(page, args.prompt);
    const conversationId = await waitForConversationForPrompt({
      qaAuth,
      prompt: args.prompt,
      startedAt,
    });
    trackedConversationIds.add(conversationId);
    result.conversationIdHash = hashValue(conversationId);
    let usedConversationFallbackNavigation = false;
    if (extractConversationIdFromUrl(page.url()) !== conversationId) {
      await page
        .waitForFunction(
          (expectedConversationId) =>
            window.location.pathname === `/c/${expectedConversationId}`,
          conversationId,
          { timeout: 30000 },
        )
        .catch(() => {});
    }
    if (extractConversationIdFromUrl(page.url()) !== conversationId) {
      usedConversationFallbackNavigation = true;
      await waitForStoredCortexParts({
        qaAuth,
        conversationId,
        prompt: args.prompt,
        timeoutMs: args.timeoutMs,
      });
      await page.goto(`${args.clientBase}/c/${conversationId}`, {
        waitUntil: "domcontentloaded",
        timeout: 60000,
      });
      authState = await installAccessToken(page, qaAuth.accessToken);
      recordAuthState(authState);
      await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    }

    await page.waitForFunction(
      (requiredNames) => {
        const rowTexts = Array.from(
          document.querySelectorAll(".progress-text-wrapper button"),
        ).map((button) => button.textContent || "");
        return requiredNames.every((name) =>
          rowTexts.some((rowText) => rowText.includes(name)),
        );
      },
      REQUIRED_CARD_NAMES,
      { timeout: args.timeoutMs },
    );
    Object.assign(
      result,
      evaluateVisibleState(
        await visibleBodyText(page),
        await visibleCortexRowTexts(page),
        provisioningState.runtimeAttachedCortexNames,
      ),
    );
    for (const name of REQUIRED_CARD_NAMES) {
      const header = page
        .locator(".progress-text-wrapper button")
        .filter({ hasText: name })
        .first();
      if (await header.isVisible({ timeout: 5000 }).catch(() => false)) {
        await header.click({ timeout: 5000 }).catch(() => {});
      }
    }
    await page.evaluate((requiredNames) => {
      for (const name of requiredNames) {
        const candidates = Array.from(
          document.querySelectorAll(".progress-text-wrapper button"),
        )
          .filter((element) => (element.textContent || "").includes(name))
          .sort(
            (a, b) =>
              (a.textContent || "").length - (b.textContent || "").length,
          );
        const button = candidates.find(
          (element) => element.getAttribute("aria-expanded") !== "true",
        );
        button?.dispatchEvent(
          new MouseEvent("click", { bubbles: true, cancelable: true }),
        );
      }
    }, REQUIRED_CARD_NAMES);
    await page.waitForFunction(
      (requiredNames) => {
        const body = document.body.innerText || "";
        return (
          requiredNames.every((name) =>
            body.includes(`Background agent: ${name}`),
          ) && /Analysis complete|Error occurred|Did not activate/i.test(body)
        );
      },
      REQUIRED_CARD_NAMES,
      { timeout: args.timeoutMs },
    );
    const storedState = await waitForStoredCortexParts({
      qaAuth,
      conversationId,
      prompt: args.prompt,
      timeoutMs: args.timeoutMs,
    });
    const parentMainAnswerText = storedState.parentMainAnswerText || "";
    const phaseBFollowUpText = storedState.phaseBFollowUpText || "";
    privateTranscript = {
      conversationId,
      capturedAt: new Date().toISOString(),
      expectedPhaseB: args.expectedPhaseB,
      prompt: args.prompt,
      parentMainAnswerText,
      cortexInsights: storedState.cortexInsightTexts || [],
      phaseBFollowUpText,
    };
    await waitForVisibleAnswerText(
      page,
      parentMainAnswerText,
      Math.min(args.timeoutMs, 60000),
    );
    if (args.expectedPhaseB === "generated") {
      await waitForVisibleAnswerText(
        page,
        phaseBFollowUpText,
        Math.min(args.timeoutMs, 60000),
      );
    }
    const text = await visibleBodyText(page);
    const state = evaluateVisibleState(
      text,
      await visibleCortexRowTexts(page),
      provisioningState.runtimeAttachedCortexNames,
    );
    Object.assign(result, state, {
      ...storedState,
      usedConversationFallbackNavigation,
      initialMainAnswerVisible: bodyContainsMainAnswer(
        text,
        parentMainAnswerText,
      ),
      phaseBInitialVisible: bodyContainsMainAnswer(text, phaseBFollowUpText),
      consoleErrorCount: consoleErrors.length,
      failedRequestCount: failedRequests.length,
      failedRequestRoutes: summarizeRouteClasses(failedRequestRoutes),
    });

    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    authState = await installAccessToken(page, qaAuth.accessToken);
    recordAuthState(authState);
    await page.waitForFunction(
      (requiredNames) => {
        const rowTexts = Array.from(
          document.querySelectorAll(".progress-text-wrapper button"),
        ).map((button) => button.textContent || "");
        return requiredNames.every((name) =>
          rowTexts.some((rowText) => rowText.includes(name)),
        );
      },
      REQUIRED_CARD_NAMES,
      { timeout: 60000 },
    );
    const reloadState = evaluateVisibleState(
      await visibleBodyText(page),
      await visibleCortexRowTexts(page),
      provisioningState.runtimeAttachedCortexNames,
    );
    const reloadBodyText = await visibleBodyText(page);
    result.reloadCardNames = reloadState.cardNames;
    result.reloadMainAnswerVisible = bodyContainsMainAnswer(
      reloadBodyText,
      parentMainAnswerText,
    );
    result.phaseBReloadVisible = bodyContainsMainAnswer(
      reloadBodyText,
      phaseBFollowUpText,
    );
    result.phaseBNtaMarkerVisible = /\{NTA\}/.test(
      `${text}\n${reloadBodyText}`,
    );
    const unexpectedCriticalHttpErrorRoutes = [...httpErrorRoutes];
    result.consoleErrorCount = consoleErrors.length;
    result.failedRequestCount = failedRequests.length;
    result.failedRequestRoutes = summarizeRouteClasses(failedRequestRoutes);
    result.criticalHttpErrorCount = unexpectedCriticalHttpErrorRoutes.length;
    result.criticalHttpErrorRoutes = summarizeRouteClasses(
      unexpectedCriticalHttpErrorRoutes,
    );
    const commonPass =
      requiredCortexCoveragePass({
        requiredNames: REQUIRED_CARD_NAMES,
        initialNames: state.cardNames,
        reloadNames: reloadState.cardNames,
        storedNames: storedState.storedCardNames,
        terminalNames: storedState.storedTerminalNames,
        completeInsightNames: storedState.storedCompleteInsightNames,
      }) &&
      REQUIRED_CARD_NAMES.every((name) =>
        storedState.storedSubstantiveInsightNames.includes(name),
      ) &&
      state.forbiddenMatches.length === 0 &&
      state.mainErrorMatches.length === 0 &&
      storedState.parentHasVisibleMainAnswer &&
      !storedState.parentCortexOnly &&
      result.initialMainAnswerVisible &&
      result.reloadMainAnswerVisible &&
      state.hasBackgroundAgentFooter &&
      state.hasTerminalState &&
      state.hasWhyThisRan &&
      result.runtimeProvisioningPass &&
      result.criticalHttpErrorCount === 0;
    result.pass =
      commonPass &&
      phaseBExpectationPass({
        expectedPhaseB: args.expectedPhaseB,
        ...result,
      });
  } catch (error) {
    result.error = sanitizePublicError(error?.message || error || "qa_failed");
  } finally {
    if (args.privateTranscriptPath && privateTranscript) {
      try {
        fs.mkdirSync(path.dirname(args.privateTranscriptPath), { recursive: true });
        fs.writeFileSync(
          args.privateTranscriptPath,
          `${JSON.stringify(
            privateTranscript,
            null,
            2,
          )}\n`,
          "utf8",
        );
      } catch (transcriptError) {
        result.pass = false;
        result.error = sanitizePublicError(transcriptError?.message || transcriptError);
      }
    }
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
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (qaAuth) {
      await qaAuth.close().catch(() => {});
    }
  }

  const report = [
    "# Background Agent Visible Cards Browser QA",
    "",
    `- Started: ${result.startedAt}`,
    `- Expected Phase B outcome: ${result.expectedPhaseB}`,
    "- Scope: local synthetic browser run with public-safe hashes only; release approval still requires committed diffs, nested pin agreement, scans, and review-only gates.",
    "- Agent ID configuration: default local QA agent IDs are used unless VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON overrides them.",
    `- Client hash: \`${result.clientBaseHash}\``,
    `- API hash: \`${result.apiBaseHash}\``,
    `- QA user hash: \`${result.qaEmailHash}\``,
    `- Agent hash: \`${result.agentIdHash}\``,
    `- Prompt hash: \`${result.promptHash}\``,
    `- Conversation hash: \`${result.conversationIdHash || "unverified"}\``,
    `- Required visible cards: ${REQUIRED_CARD_NAMES.join(", ")}`,
    `- Runtime required agents: ${result.runtimeRequiredAgentCount}`,
    `- Runtime missing required agent hashes: ${result.runtimeMissingRequiredAgentHashes?.join(", ") || "none"}`,
    `- Runtime cortex fallback agents configured: ${result.runtimeCortexFallbackNames?.join(", ") || "none"}`,
    `- Runtime activation expected provider: ${result.runtimeActivationExpectedProvider}`,
    `- Runtime activation expected model hash: \`${result.runtimeActivationExpectedModelHash}\``,
    `- Runtime activation drift agents: ${result.runtimeActivationDriftNames?.join(", ") || "none"}`,
    `- Runtime activation config pass: ${Boolean(result.runtimeActivationConfigPass)}`,
    `- Runtime provisioning pass: ${Boolean(result.runtimeProvisioningPass)}`,
    `- Conversation fallback navigation used: ${Boolean(result.usedConversationFallbackNavigation)}`,
    `- Direct local access-token fallback used: ${Boolean(result.directAccessTokenFallbackUsed)}`,
    `- Expected local-QA bootstrap HTTP 401s: ${result.expectedLocalQaBootstrapHttpErrorCount ?? 0}`,
    `- Initial visible cards: ${result.cardNames.join(", ") || "none"}`,
    `- Reload visible cards: ${result.reloadCardNames.join(", ") || "none"}`,
    `- Parent assistant hash: \`${result.parentMessageHash || "unverified"}\``,
    `- Parent visible answer text length: ${result.parentMainAnswerTextLength ?? 0}`,
    `- Parent visible answer present: ${Boolean(result.parentHasVisibleMainAnswer)}`,
    `- Parent cortex-only failure: ${Boolean(result.parentCortexOnly)}`,
    `- Initial parent answer visible: ${Boolean(result.initialMainAnswerVisible)}`,
    `- Reload parent answer visible: ${Boolean(result.reloadMainAnswerVisible)}`,
    `- Phase B follow-up message count: ${result.phaseBFollowUpCount ?? 0}`,
    `- Phase B structured follow-up count: ${result.phaseBStructuredFollowUpCount ?? 0}`,
    `- Phase B decision result: ${result.phaseBDecisionResult || "missing"}`,
    `- Phase B LLM result: ${result.phaseBLlmResult || "missing"}`,
    `- Phase B selected strategy: ${result.phaseBSelectedStrategy || "missing"}`,
    `- Phase B suppression reason: ${result.phaseBSuppressionReason || "none"}`,
    `- Phase B follow-up text length: ${result.phaseBFollowUpTextLength ?? 0}`,
    `- Phase B novel-token ratio: ${(result.phaseBNovelTokenRatio ?? 0).toFixed(3)}`,
    `- Phase B initially visible: ${Boolean(result.phaseBInitialVisible)}`,
    `- Phase B visible after reload: ${Boolean(result.phaseBReloadVisible)}`,
    `- NTA marker visible: ${Boolean(result.phaseBNtaMarkerVisible)}`,
    `- Background-agent footer visible: ${Boolean(result.hasBackgroundAgentFooter)}`,
    `- Terminal state visible: ${Boolean(result.hasTerminalState)}`,
    `- Why-this-ran visible: ${Boolean(result.hasWhyThisRan)}`,
    `- Forbidden main-agent wording matches: ${result.forbiddenMatches?.length || 0}`,
    `- Main error banner matches: ${result.mainErrorMatches?.length || 0}`,
    `- Stored assistant message count: ${result.assistantMessageCount ?? 0}`,
    `- Stored cortex part count: ${result.storedCortexPartCount ?? 0}`,
    `- Stored cortex cards: ${result.storedCardNames?.join(", ") || "none"}`,
    `- Stored terminal cortex results: ${result.storedTerminalNames?.join(", ") || "none"}`,
    `- Stored successful cortex insights: ${result.storedCompleteInsightNames?.join(", ") || "none"}`,
    `- Stored cortex errors: ${result.storedErrorNames?.join(", ") || "none"}`,
    `- Console error count: ${result.consoleErrorCount ?? 0}`,
    `- Failed request count: ${result.failedRequestCount ?? 0}`,
    `- Failed request route classes: ${result.failedRequestRoutes?.join(", ") || "none"}`,
    `- Critical HTTP error count: ${result.criticalHttpErrorCount ?? 0}`,
    `- Critical HTTP error routes: ${result.criticalHttpErrorRoutes?.join(", ") || "none"}`,
    `- Result: ${result.pass ? "PASS" : "FAIL"}`,
    `- Interpretation: ${publicInterpretation(result)}`,
    result.error ? `- Error: ${result.error}` : "",
    "",
  ]
    .filter(Boolean)
    .join("\n");
  fs.mkdirSync(path.dirname(args.out), { recursive: true });
  fs.writeFileSync(args.out, `${report}\n`, "utf8");
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.pass ? 0 : 1);
}

if (require.main === module) {
  run();
}

module.exports = {
  extractVisibleAnswerTextFromMessage,
  isSubstantiveCortexInsight,
  parseExpectedPhaseBExpectation,
  phaseBExpectationPass,
  requiredCortexCoveragePass,
  waitForVisibleAnswerText,
};
