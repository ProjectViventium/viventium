#!/usr/bin/env node

/**
 * Public-safe live Quality + Performance comparison for the direct model and both GlassHive
 * harness profiles. Raw synthetic outputs are written only to private App Support state.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { createRequire } from "node:module";

const root = path.resolve(import.meta.dirname, "..", "..", "..");
const runtimeRoot = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
  "runtime",
);
const privateRoot = path.join(
  os.homedir(),
  "Library",
  "Application Support",
  "Viventium",
  "state",
  "qa-runtime",
  "glasshive-quality-matrix",
);
const lifeRoot =
  process.env.VIVENTIUM_LIFE_DIR ||
  path.join(os.homedir(), "Documents", "Viventium", "Life");

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

const env = {
  ...parseEnvFile(path.join(runtimeRoot, "runtime.env")),
  ...parseEnvFile(path.join(runtimeRoot, "runtime.local.env")),
  ...parseEnvFile(path.join(runtimeRoot, "service-env", "librechat.env")),
  ...parseEnvFile(path.join(root, "viventium_v0_4", "LibreChat", ".env")),
  ...process.env,
};
process.env.CREDS_KEY = env.CREDS_KEY;
process.env.CREDS_IV = env.CREDS_IV;
const require = createRequire(import.meta.url);
const { MongoClient } = require(
  path.join(root, "viventium_v0_4", "LibreChat", "node_modules", "mongodb"),
);
const { decrypt } = require(
  path.join(
    root,
    "viventium_v0_4",
    "LibreChat",
    "packages",
    "data-schemas",
    "dist",
    "index.cjs",
  ),
);

const fixturePath = path.join(
  lifeRoot,
  "Projects",
  "GlassHive_Quality_Matrix_QA",
  "context.txt",
);
if (!fs.existsSync(fixturePath)) {
  throw new Error(
    "Create the synthetic LIFE matrix fixture before running this evaluation",
  );
}
const fixtureBody = fs.readFileSync(fixturePath, "utf8");
const fixtureHash = crypto
  .createHash("sha256")
  .update(fixtureBody)
  .digest("hex");
const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const outputDir = path.join(privateRoot, stamp);
fs.mkdirSync(outputDir, { recursive: true });

const sharedInstructions =
  "Be concise, natural, truthful, and useful. Follow the requested output shape exactly. " +
  "Never claim to have used a file or tool unless you actually did.";

const commonRepetitions = 3;
const performanceBudgetsMs = {
  direct: 45_000,
  "glasshive-codex": 60_000,
  "glasshive-claude": 120_000,
};

const allCases = [
  {
    id: "greeting",
    input:
      "Reply naturally in exactly one sentence. Mention that you are here. Do not say “great question” or “happy to help”.",
    score(text) {
      const sentences = text
        .split(/[.!?]+/)
        .filter((item) => item.trim()).length;
      return (
        sentences === 1 &&
        /\bhere\b/i.test(text) &&
        !/great question|happy to help/i.test(text)
      );
    },
  },
  {
    id: "ambiguity",
    input:
      "I need to fix the launch. Ask exactly one concise clarifying question and do not invent what is wrong.",
    score(text) {
      return (text.match(/\?/g) || []).length === 1 && text.length <= 240;
    },
  },
  {
    id: "emotion",
    input:
      "I failed at this again and I feel useless. Respond in exactly two sentences: acknowledge the feeling without diagnosing me, then give one tiny next step.",
    score(text) {
      const sentences = text
        .split(/[.!?]+/)
        .filter((item) => item.trim()).length;
      return (
        sentences === 2 && !/diagnos|disorder|therapy|therapist/i.test(text)
      );
    },
  },
  {
    id: "file_context",
    input:
      "Read Projects/GlassHive_Quality_Matrix_QA/context.txt from the current working folder. " +
      "If you can truly read it, reply exactly SYNTHETIC_FILE_VALUE=ultraviolet. " +
      "If you cannot, state that limitation plainly and do not guess.",
    score(text, provider) {
      return provider === "direct"
        ? /cannot|can't|do not have|no access/i.test(text)
        : text.trim().endsWith("SYNTHETIC_FILE_VALUE=ultraviolet");
    },
  },
  {
    id: "native_tool",
    input:
      "Use a native shell tool to calculate the SHA-256 of Projects/GlassHive_Quality_Matrix_QA/context.txt. " +
      "Reply with only the lowercase hash. If no shell is available, say so plainly and do not guess.",
    score(text, provider) {
      return provider === "direct"
        ? /cannot|can't|do not have|no access|unavailable|no (?:native )?shell is available/i.test(
            text,
          )
        : text.trim() === fixtureHash;
    },
  },
  {
    id: "correction",
    input: [
      {
        type: "message",
        role: "user",
        content: "Remember for this synthetic scenario: launch day is Friday.",
      },
      {
        type: "message",
        role: "assistant",
        content: "Understood: launch day is Friday.",
      },
      {
        type: "message",
        role: "user",
        content:
          "Correction: it is Monday. Reply with only the corrected weekday in uppercase.",
      },
    ],
    score(text) {
      return text.trim() === "MONDAY";
    },
  },
  {
    id: "adjudication",
    input:
      "Decision: ship a billing migration tomorrow. Specialist finding: there is no rollback plan. " +
      "Return exactly three short bullets labeled Risk, Decision, and Next step. Make the decision yourself.",
    score(text) {
      return (
        ["Risk", "Decision", "Next step"].every((label) =>
          text.includes(label),
        ) &&
        text.split("\n").filter((line) => /^\s*[-*]/.test(line)).length === 3
      );
    },
  },
];
const capabilityCaseIds = new Set(["file_context", "native_tool"]);
const commonCases = allCases.filter(
  (testCase) => !capabilityCaseIds.has(testCase.id),
);
const capabilityCases = allCases.filter((testCase) =>
  capabilityCaseIds.has(testCase.id),
);

function shortHash(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, 12);
}

function parseJwtPayload(token) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3) return {};
  try {
    return JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8"));
  } catch {
    return {};
  }
}

async function refreshConnectedOpenAI(values) {
  if (
    typeof values.oauthExpiresAt !== "number" ||
    values.oauthExpiresAt > Date.now() + 5 * 60 * 1000
  ) {
    return values;
  }
  if (!values.refreshToken)
    throw new Error("Connected OpenAI account requires reconnection");
  const response = await fetch(
    env.VIVENTIUM_OPENAI_OAUTH_TOKEN_URL ||
      "https://auth.openai.com/oauth/token",
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        client_id:
          env.VIVENTIUM_OPENAI_OAUTH_CLIENT_ID ||
          "app_EMoamEEZ73f0CkXaXp7hrann",
        refresh_token: values.refreshToken,
      }),
      signal: AbortSignal.timeout(60_000),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok || typeof body.access_token !== "string") {
    throw new Error("Connected OpenAI account refresh failed");
  }
  const auth = parseJwtPayload(body.access_token)?.[
    "https://api.openai.com/auth"
  ];
  const accountId =
    auth && typeof auth === "object" ? auth.chatgpt_account_id : undefined;
  return {
    ...values,
    apiKey: body.access_token,
    refreshToken: body.refresh_token || values.refreshToken,
    oauthExpiresAt: Date.now() + Number(body.expires_in || 3600) * 1000,
    headers: {
      ...(values.headers || {}),
      "OpenAI-Beta": "responses=experimental",
      originator: env.VIVENTIUM_OPENAI_OAUTH_ORIGINATOR || "pi",
      ...(accountId ? { "chatgpt-account-id": accountId } : {}),
    },
  };
}

async function connectedOpenAICredential() {
  const requestedHash = String(env.VIVENTIUM_QA_USER_HASH || "")
    .trim()
    .toLowerCase();
  if (!requestedHash)
    throw new Error(
      "Set VIVENTIUM_QA_USER_HASH for the direct connected-account baseline",
    );
  const client = new MongoClient(env.MONGO_URI, {
    serverSelectionTimeoutMS: 5000,
  });
  try {
    await client.connect();
    const dbName =
      new URL(env.MONGO_URI).pathname.replace(/^\//, "") ||
      "LibreChatViventium";
    const db = client.db(dbName);
    const users = await db
      .collection("users")
      .find({}, { projection: { _id: 1 } })
      .toArray();
    const user = users.find(
      (candidate) => shortHash(candidate._id) === requestedHash,
    );
    if (!user) throw new Error("Configured direct-baseline user was not found");
    const key = await db.collection("keys").findOne({
      userId: { $in: [user._id, String(user._id)] },
      name: "openAI",
    });
    if (!key?.value)
      throw new Error("Configured user has no connected OpenAI account");
    const values = await refreshConnectedOpenAI(
      JSON.parse(await decrypt(key.value)),
    );
    if (
      values.oauthProvider !== "openai-codex" ||
      !values.apiKey ||
      !values.baseURL
    ) {
      throw new Error(
        "Configured OpenAI account is not a usable subscription connection",
      );
    }
    return {
      token: values.apiKey,
      url: `${String(values.baseURL).replace(/\/$/, "")}/responses`,
      headers: values.headers || {},
    };
  } finally {
    await client.close();
  }
}

const supportedProviderIds = [
  "direct",
  "glasshive-codex",
  "glasshive-claude",
];
const requestedProviderIds = String(
  env.VIVENTIUM_QA_MATRIX_PROVIDERS || supportedProviderIds.join(","),
)
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const unknownProviderIds = requestedProviderIds.filter(
  (id) => !supportedProviderIds.includes(id),
);
if (unknownProviderIds.length > 0) {
  throw new Error(
    `Unsupported matrix providers: ${unknownProviderIds.join(", ")}`,
  );
}
const directCredential = requestedProviderIds.includes("direct")
  ? await connectedOpenAICredential()
  : null;
const providerRegistry = [
  ...(directCredential
    ? [
        {
          id: "direct",
          model: "gpt-5.6-sol",
          url: directCredential.url,
          token: directCredential.token,
          headers: directCredential.headers,
          codexSubscription: true,
        },
      ]
    : []),
  {
    id: "glasshive-codex",
    model: "codex-cli:gpt-5.6-sol",
    url: `${String(env.GLASSHIVE_PROVIDER_BASE_URL || "http://127.0.0.1:8766/v1").replace(/\/$/, "")}/responses`,
    token: env.GLASSHIVE_PROVIDER_API_KEY,
  },
  {
    id: "glasshive-claude",
    model: "claude-code:opus",
    url: `${String(env.GLASSHIVE_PROVIDER_BASE_URL || "http://127.0.0.1:8766/v1").replace(/\/$/, "")}/responses`,
    token: env.GLASSHIVE_PROVIDER_API_KEY,
  },
];
const providers = providerRegistry.filter((provider) =>
  requestedProviderIds.includes(provider.id),
);

function outputText(payload) {
  if (typeof payload?.output_text === "string") return payload.output_text;
  const parts = [];
  for (const item of Array.isArray(payload?.output) ? payload.output : []) {
    for (const part of Array.isArray(item?.content) ? item.content : []) {
      if (typeof part?.text === "string") parts.push(part.text);
    }
  }
  return parts.join("\n");
}

function codexStreamText(bodyText) {
  let text = "";
  let completed = null;
  for (const line of bodyText.split(/\r?\n/)) {
    if (!line.startsWith("data: ")) continue;
    const raw = line.slice(6).trim();
    if (!raw || raw === "[DONE]") continue;
    let event;
    try {
      event = JSON.parse(raw);
    } catch {
      continue;
    }
    if (
      event.type === "response.output_text.delta" &&
      typeof event.delta === "string"
    ) {
      text += event.delta;
    }
    if (event.type === "response.completed" && event.response)
      completed = event.response;
    if (event.type === "error")
      throw new Error(
        `Direct connected-account stream failed: ${event.code || "runtime_error"}`,
      );
  }
  return text || outputText(completed || {});
}

function codexInput(input) {
  const messages =
    typeof input === "string"
      ? [{ type: "message", role: "user", content: input }]
      : input;
  return messages.map((message) => ({
    ...message,
    content:
      typeof message.content === "string"
        ? [
            {
              type: message.role === "assistant" ? "output_text" : "input_text",
              text: message.content,
            },
          ]
        : message.content,
  }));
}

async function run(provider, testCase, repetition) {
  if (!provider.token)
    throw new Error(`Missing authentication for ${provider.id}`);
  const started = performance.now();
  const response = await fetch(provider.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${provider.token}`,
      "Content-Type": "application/json",
      ...(provider.headers || {}),
    },
    body: JSON.stringify({
      model: provider.model,
      instructions: sharedInstructions,
      input: provider.codexSubscription
        ? codexInput(testCase.input)
        : testCase.input,
      ...(!provider.codexSubscription
        ? { metadata: { qa_case: testCase.id, qa_provider: provider.id } }
        : {}),
      ...(!provider.codexSubscription ? { max_output_tokens: 500 } : {}),
      ...(provider.codexSubscription
        ? {
            store: false,
            stream: true,
            include: ["reasoning.encrypted_content"],
          }
        : {}),
    }),
    signal: AbortSignal.timeout(300_000),
  });
  const rawBody = await response.text();
  const body = provider.codexSubscription
    ? null
    : (() => {
        try {
          return JSON.parse(rawBody);
        } catch {
          return {};
        }
      })();
  const latencyMs = Math.round(performance.now() - started);
  if (!response.ok) {
    let errorCode = "request_failed";
    let errorMessage = "";
    try {
      const parsedError = JSON.parse(rawBody)?.error || {};
      errorCode = parsedError.code || parsedError.type || errorCode;
      errorMessage = String(parsedError.message || "")
        .replace(/\s+/g, " ")
        .slice(0, 240);
    } catch {
      // Preserve the public-safe generic error class.
    }
    if (!errorMessage) {
      errorMessage = rawBody.replace(/\s+/g, " ").slice(0, 240);
    }
    const error = new Error(
      `${provider.id}/${testCase.id} returned HTTP ${response.status}: ${errorCode}` +
        (errorMessage ? ` (${errorMessage})` : ""),
    );
    error.status = response.status;
    error.code = errorCode;
    error.latencyMs = latencyMs;
    throw error;
  }
  const text = (
    provider.codexSubscription ? codexStreamText(rawBody) : outputText(body)
  ).trim();
  return {
    provider: provider.id,
    model: provider.model,
    case: testCase.id,
    repetition,
    executed: true,
    latencyMs,
    pass: Boolean(testCase.score(text, provider.id)),
    text,
  };
}

const providerBlockers = new Map();
const terminalProviderStatuses = new Set([401, 403, 429, 503]);

async function runSafely(provider, testCase, repetition) {
  const blocked = providerBlockers.get(provider.id);
  if (blocked) {
    return {
      provider: provider.id,
      model: provider.model,
      case: testCase.id,
      repetition,
      executed: false,
      latencyMs: null,
      pass: false,
      errorStatus: blocked.status,
      errorCode: blocked.code,
    };
  }
  try {
    return await run(provider, testCase, repetition);
  } catch (error) {
    const status = Number(error?.status || 0) || null;
    const code = String(error?.code || "request_failed");
    if (status && terminalProviderStatuses.has(status)) {
      providerBlockers.set(provider.id, { status, code });
    }
    return {
      provider: provider.id,
      model: provider.model,
      case: testCase.id,
      repetition,
      executed: true,
      latencyMs: Number(error?.latencyMs || 0) || null,
      pass: false,
      errorStatus: status,
      errorCode: code,
    };
  }
}

const commonResults = [];
for (const provider of providers) {
  for (let repetition = 1; repetition <= commonRepetitions; repetition += 1) {
    for (const testCase of commonCases) {
      commonResults.push(await runSafely(provider, testCase, repetition));
    }
  }
}
const capabilityResults = [];
for (const provider of providers) {
  for (const testCase of capabilityCases) {
    capabilityResults.push(await runSafely(provider, testCase, 1));
  }
}

fs.writeFileSync(
  path.join(outputDir, "synthetic-results.json"),
  `${JSON.stringify({ generatedAt: new Date().toISOString(), commonResults, capabilityResults }, null, 2)}\n`,
  { mode: 0o600 },
);

const summaries = providers.map((provider) => {
  const rows = commonResults.filter((row) => row.provider === provider.id);
  const latencies = rows
    .filter((row) => row.executed && Number.isFinite(row.latencyMs))
    .map((row) => row.latencyMs)
    .sort((a, b) => a - b);
  const percentile = (fraction) =>
    latencies.length > 0
      ? latencies[
          Math.min(
            latencies.length - 1,
            Math.ceil(latencies.length * fraction) - 1,
          )
        ]
      : null;
  const blocked = providerBlockers.get(provider.id) || null;
  const p95LatencyMs = percentile(0.95);
  return {
    provider: provider.id,
    model: provider.model,
    status: blocked ? "blocked" : rows.every((row) => row.pass) ? "passed" : "failed",
    blocker: blocked,
    executed: rows.filter((row) => row.executed).length,
    passed: rows.filter((row) => row.pass).length,
    total: rows.length,
    commonQualityPass: rows.every((row) => row.pass),
    p50LatencyMs: percentile(0.5),
    p95LatencyMs,
    performanceBudgetMs: performanceBudgetsMs[provider.id],
    performancePass:
      !blocked &&
      p95LatencyMs !== null &&
      p95LatencyMs <= performanceBudgetsMs[provider.id],
    caseResults: Object.fromEntries(
      commonCases.map((testCase) => [
        testCase.id,
        rows
          .filter((row) => row.case === testCase.id)
          .map((row) => row.pass),
      ]),
    ),
  };
});
const capabilitySummaries = providers.map((provider) => {
  const rows = capabilityResults.filter((row) => row.provider === provider.id);
  const direct = provider.id === "direct";
  const blocked = providerBlockers.get(provider.id) || null;
  return {
    provider: provider.id,
    model: provider.model,
    status: blocked
      ? "blocked"
      : direct
        ? "not_supported"
        : rows.every((row) => row.pass)
          ? "supported"
          : "failed",
    blocker: blocked,
    executed: rows.filter((row) => row.executed).length,
    honestLimitationPass: direct ? rows.every((row) => row.pass) : null,
    nativeCapabilityPass: direct ? false : rows.every((row) => row.pass),
    cases: Object.fromEntries(rows.map((row) => [row.case, row.pass])),
  };
});
const commonQualityPass = summaries.every((summary) => summary.commonQualityPass);
const performancePass = summaries.every((summary) => summary.performancePass);
const nativeCapabilityPass = capabilitySummaries.every((summary) =>
  summary.provider === "direct"
    ? summary.honestLimitationPass === true && summary.status === "not_supported"
    : summary.nativeCapabilityPass === true && summary.status === "supported",
);
const pass = commonQualityPass && performancePass && nativeCapabilityPass;

console.log(
  JSON.stringify(
    {
      source: "live-installed-endpoints",
      fixtureHash,
      rawArtifact: path.join(outputDir, "synthetic-results.json"),
      commonRepetitions,
      summaries,
      capabilitySummaries,
      commonQualityPass,
      performancePass,
      nativeCapabilityPass,
      pass,
    },
    null,
    2,
  ),
);
process.exitCode = pass ? 0 : 1;
