#!/usr/bin/env node
/*
 * Real fake-microphone LiveKit QA harness.
 *
 * It seeds one canonical synthetic call session, opens the modern playground with a WAV file as
 * Chromium's microphone input, verifies the zero-second-action auto-connect path, waits for the
 * real voice worker/STT path to persist transcript evidence, and cleans up only the synthetic
 * records it created.
 */

const fs = require("fs");
const crypto = require("crypto");
const path = require("path");
const { createRequire } = require("module");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const LIBRECHAT_DIR =
  process.env.LIBRECHAT_DIR || path.join(ROOT, "viventium_v0_4", "LibreChat");
const librechatRequire = createRequire(
  path.join(LIBRECHAT_DIR, "package.json"),
);
const { chromium } = librechatRequire("playwright");
const { MongoClient, ObjectId } = librechatRequire("mongodb");

const CALL_CAPABILITY_HEADER = "X-VIVENTIUM-CALL-CAPABILITY";
const CALL_CAPABILITY_STORAGE_PREFIX = "viventium.call.capability.v1:";
const CALL_CAPABILITY_SCOPE = "call_browser_v1";
const CALL_SESSION_TTL_MS = 15 * 60 * 1000;
const SAFE_CALL_ID = /^[A-Za-z0-9._:-]{1,160}$/;
const SAFE_BROWSER_CAPABILITY = /^[A-Za-z0-9_-]{43}$/;

function createBrowserCallCapability(now = new Date()) {
  const capability = crypto.randomBytes(32).toString("base64url");
  return {
    capability,
    hash: crypto.createHash("sha256").update(capability).digest("hex"),
    expiresAt: new Date(now.getTime() + CALL_SESSION_TTL_MS),
    version: 1,
    scope: CALL_CAPABILITY_SCOPE,
  };
}

function browserCapabilityHeaders(browserCapability) {
  if (!SAFE_BROWSER_CAPABILITY.test(String(browserCapability || ""))) {
    throw new Error("A valid browser capability is required");
  }
  return { [CALL_CAPABILITY_HEADER]: browserCapability };
}

function buildCallBootstrapUrl(playgroundUrl, callSessionId, browserCapability) {
  if (!SAFE_CALL_ID.test(String(callSessionId || ""))) {
    throw new Error("A valid call session id is required");
  }
  browserCapabilityHeaders(browserCapability);
  const url = new URL("/call-bootstrap", playgroundUrl);
  url.searchParams.set("callSessionId", callSessionId);
  url.searchParams.set("autoConnect", "1");
  url.hash = new URLSearchParams({ viventiumCallCapability: browserCapability }).toString();
  return url;
}

async function assertCallBootstrapStripped(page, callSessionId) {
  await page.waitForFunction(
    ({ expectedCallSessionId, storagePrefix }) => {
      const stored = window.sessionStorage.getItem(`${storagePrefix}${expectedCallSessionId}`) || "";
      return (
        window.location.hash === "" &&
        !window.location.pathname.endsWith("/call-bootstrap") &&
        /^[A-Za-z0-9_-]{43}$/.test(stored)
      );
    },
    { expectedCallSessionId: callSessionId, storagePrefix: CALL_CAPABILITY_STORAGE_PREFIX },
    { timeout: 10_000 },
  );
  const safeState = await page.evaluate(
    ({ expectedCallSessionId, storagePrefix }) => ({
      fragmentStripped: window.location.hash === "",
      bootstrapExited: !window.location.pathname.endsWith("/call-bootstrap"),
      capabilityStored: /^[A-Za-z0-9_-]{43}$/.test(
        window.sessionStorage.getItem(`${storagePrefix}${expectedCallSessionId}`) || "",
      ),
    }),
    { expectedCallSessionId: callSessionId, storagePrefix: CALL_CAPABILITY_STORAGE_PREFIX },
  );
  if (!safeState.fragmentStripped || !safeState.bootstrapExited || !safeState.capabilityStored) {
    throw new Error("call_capability_bootstrap_failed");
  }
}

function assertPrivateOutputRoot(outputRoot) {
  if (outputRoot === path.parse(outputRoot).root) {
    throw new Error("--output-root cannot be a filesystem root");
  }
  const relative = path.relative(ROOT, outputRoot);
  if (!relative.startsWith("..") && !path.isAbsolute(relative)) {
    throw new Error("--output-root must stay outside the public repository");
  }
}

function resolveOutputPath(value, label, outputRoot) {
  const resolved = path.resolve(value);
  const relative = path.relative(outputRoot, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`${label} must stay under --output-root`);
  }
  return resolved;
}

function safeCaseSlug(value) {
  return String(value || "synthetic-audio")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "synthetic-audio";
}

function safeErrorCode(error) {
  const name = String(error?.name || "").toLowerCase();
  if (name === "timeouterror") {
    return "timeout";
  }
  if (name === "aborterror") {
    return "aborted";
  }
  return "synthetic_audio_qa_failed";
}

function envFlag(name, fallback = false) {
  const value = String(process.env[name] || "").trim().toLowerCase();
  if (!value) {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(value);
}

function commaSeparatedEnv(name) {
  return String(process.env[name] || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function parseArgs(argv) {
  const defaultPlaygroundUrl =
    process.env.PLAYGROUND_URL || "http://localhost:3300";
  const args = {
    audio: "",
    expect: "",
    caseId: "synthetic-audio",
    playgroundUrl: defaultPlaygroundUrl,
    browserPlaygroundUrl:
      process.env.VIVENTIUM_QA_BROWSER_PLAYGROUND_URL ||
      defaultPlaygroundUrl,
    browserProxy: String(
      process.env.VIVENTIUM_QA_BROWSER_PROXY || "",
    ).trim(),
    disableNonProxiedUdp: envFlag(
      "VIVENTIUM_QA_DISABLE_NON_PROXIED_UDP",
    ),
    agentName: process.env.LIVEKIT_AGENT_NAME || "librechat-voice-gateway",
    agentId:
      process.env.VIVENTIUM_QA_AGENT_ID || "agent_viventium_main_95aeb3",
    mode: process.env.VIVENTIUM_QA_CALL_MODE || "",
    sttProvider: process.env.VIVENTIUM_QA_STT_PROVIDER || "pywhispercpp",
    sttVariant:
      process.env.VIVENTIUM_QA_STT_VARIANT || "large-v3-turbo",
    ttsProvider:
      process.env.VIVENTIUM_QA_TTS_PROVIDER ||
      "local_chatterbox_turbo_mlx_8bit",
    ttsVariant:
      process.env.VIVENTIUM_QA_TTS_VARIANT ||
      "mlx-community/chatterbox-turbo-8bit",
    interactive: false,
    waitMs: Number(process.env.VIVENTIUM_SYNTHETIC_AUDIO_QA_WAIT_MS || 90000),
    minTokenRatio: Number(
      process.env.VIVENTIUM_SYNTHETIC_AUDIO_QA_MIN_TOKEN_RATIO || 0.6,
    ),
    maxTranscriptCount: Number(
      process.env.VIVENTIUM_SYNTHETIC_AUDIO_QA_MAX_TRANSCRIPT_COUNT || 1,
    ),
    headed: false,
    cleanup: true,
    allowNonLocalMongo: false,
    outputRoot: String(process.env.VIVENTIUM_QA_OUTPUT_ROOT || "").trim(),
    result: "",
    screenshot: "",
    externalTurnUrls: commaSeparatedEnv("VIVENTIUM_QA_EXTERNAL_TURN_URLS"),
    externalTurnUsername: String(
      process.env.VIVENTIUM_QA_EXTERNAL_TURN_USERNAME || "",
    ).trim(),
    externalTurnCredential: String(
      process.env.VIVENTIUM_QA_EXTERNAL_TURN_CREDENTIAL || "",
    ).trim(),
    forceRelay: envFlag("VIVENTIUM_QA_FORCE_RELAY"),
    publicMediaCandidate: String(
      process.env.VIVENTIUM_QA_PUBLIC_MEDIA_CANDIDATE || "",
    ).trim(),
    publicMediaProxy: String(
      process.env.VIVENTIUM_QA_PUBLIC_MEDIA_PROXY || "",
    ).trim(),
    turnProxyUrl: String(
      process.env.VIVENTIUM_QA_TURN_PROXY_URL || "",
    ).trim(),
    turnProxyHostRule: String(
      process.env.VIVENTIUM_QA_TURN_PROXY_HOST_RULE || "",
    ).trim(),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    const next = argv[i + 1];
    if (item === "--audio") {
      args.audio = next || "";
      i += 1;
    } else if (item === "--expect") {
      args.expect = next || "";
      i += 1;
    } else if (item === "--case-id") {
      args.caseId = next || args.caseId;
      i += 1;
    } else if (item === "--playground-url") {
      args.playgroundUrl = next || args.playgroundUrl;
      i += 1;
    } else if (item === "--agent-name") {
      args.agentName = next || args.agentName;
      i += 1;
    } else if (item === "--agent-id") {
      args.agentId = next || args.agentId;
      i += 1;
    } else if (item === "--mode") {
      args.mode = next || args.mode;
      i += 1;
    } else if (item === "--stt-provider") {
      args.sttProvider = next || args.sttProvider;
      i += 1;
    } else if (item === "--stt-variant") {
      args.sttVariant = next || args.sttVariant;
      i += 1;
    } else if (item === "--tts-provider") {
      args.ttsProvider = next || args.ttsProvider;
      i += 1;
    } else if (item === "--tts-variant") {
      args.ttsVariant = next || args.ttsVariant;
      i += 1;
    } else if (item === "--wait-ms") {
      args.waitMs = Number(next || args.waitMs);
      i += 1;
    } else if (item === "--min-token-ratio") {
      args.minTokenRatio = Number(next || args.minTokenRatio);
      i += 1;
    } else if (item === "--max-transcript-count") {
      args.maxTranscriptCount = Number(next || args.maxTranscriptCount);
      i += 1;
    } else if (item === "--result") {
      args.result = next || "";
      i += 1;
    } else if (item === "--screenshot") {
      args.screenshot = next || "";
      i += 1;
    } else if (item === "--output-root") {
      args.outputRoot = next || "";
      i += 1;
    } else if (item === "--headed") {
      args.headed = true;
    } else if (item === "--interactive") {
      args.interactive = true;
    } else if (item === "--no-cleanup") {
      args.cleanup = false;
    } else if (item === "--allow-non-local-mongo") {
      args.allowNonLocalMongo = true;
    }
  }

  if (!args.audio) {
    throw new Error("--audio is required");
  }
  if (!args.outputRoot) {
    throw new Error(
      "--output-root or VIVENTIUM_QA_OUTPUT_ROOT is required",
    );
  }
  args.outputRoot = path.resolve(args.outputRoot);
  assertPrivateOutputRoot(args.outputRoot);
  args.mode = args.mode || (args.interactive ? "call" : "listen_only");
  if (!["call", "wing", "listen_only"].includes(args.mode)) {
    throw new Error("--mode must be call, wing, or listen_only");
  }
  args.audio = path.resolve(args.audio);
  if (!fs.existsSync(args.audio)) {
    throw new Error(`audio file does not exist: ${args.audio}`);
  }
  const externalTurnFieldCount = [
    args.externalTurnUrls.length > 0,
    Boolean(args.externalTurnUsername),
    Boolean(args.externalTurnCredential),
  ].filter(Boolean).length;
  if (externalTurnFieldCount > 0 && externalTurnFieldCount < 3) {
    throw new Error(
      "External TURN QA requires URLs, username, and credential together",
    );
  }
  if (
    args.forceRelay &&
    externalTurnFieldCount !== 3 &&
    !args.turnProxyUrl
  ) {
    throw new Error(
      "VIVENTIUM_QA_FORCE_RELAY requires external TURN credentials or a TURN proxy",
    );
  }
  if (Boolean(args.publicMediaCandidate) !== Boolean(args.publicMediaProxy)) {
    throw new Error(
      "Public media QA requires candidate and proxy endpoints together",
    );
  }
  if (Boolean(args.turnProxyUrl) !== Boolean(args.turnProxyHostRule)) {
    throw new Error(
      "TURN proxy QA requires a proxy URL and Chromium host rule together",
    );
  }
  const caseSlug = safeCaseSlug(args.caseId);
  args.caseId = caseSlug;
  args.result = resolveOutputPath(
    args.result || path.join(args.outputRoot, `${caseSlug}-result.json`),
    "--result",
    args.outputRoot,
  );
  args.screenshot = resolveOutputPath(
    args.screenshot || path.join(args.outputRoot, `${caseSlug}.png`),
    "--screenshot",
    args.outputRoot,
  );
  return args;
}

function assertLocalMongoUri(mongoUri, allowNonLocalMongo) {
  if (allowNonLocalMongo) {
    return;
  }
  let parsed;
  try {
    parsed = new URL(mongoUri);
  } catch {
    throw new Error("MONGO_URI must be a valid MongoDB URI");
  }
  const host = parsed.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (!["localhost", "127.0.0.1", "::1"].includes(host)) {
    throw new Error(
      "MONGO_URI must point at localhost unless --allow-non-local-mongo is set",
    );
  }
}

function createRoomName(callSessionId) {
  const short = String(callSessionId)
    .replace(/[^a-zA-Z0-9]/g, "")
    .slice(0, 12);
  return `lc-${short || "call"}`;
}

function expectedTokens(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .split(/\s+/)
    .filter((token) => token.length >= 3);
}

function tokenMatch(text, expected, minRatio = 0.6) {
  const haystack = String(text || "").toLowerCase();
  const tokens = expectedTokens(expected);
  if (!tokens.length) {
    return true;
  }
  const matched = tokens.filter((token) => haystack.includes(token));
  return matched.length >= Math.max(1, Math.ceil(tokens.length * minRatio));
}

function orderedTokenMatch(text, expected, minRatio = 0.6) {
  const haystack = expectedTokens(text);
  const tokens = expectedTokens(expected);
  if (!tokens.length) {
    return true;
  }
  let haystackIndex = 0;
  let matched = 0;
  for (const token of tokens) {
    let searchIndex = haystackIndex;
    while (searchIndex < haystack.length && haystack[searchIndex] !== token) {
      searchIndex += 1;
    }
    if (searchIndex >= haystack.length) {
      continue;
    }
    matched += 1;
    haystackIndex = searchIndex + 1;
  }
  return matched >= Math.max(1, Math.ceil(tokens.length * minRatio));
}

async function seedCallSession(
  db,
  {
    caseId,
    agentName,
    agentId,
    interactive,
    mode,
    sttProvider,
    sttVariant,
    ttsProvider,
    ttsVariant,
  },
) {
  const now = new Date();
  const callSessionId = crypto.randomUUID();
  const userId = new ObjectId();
  const qaSlug =
    `${caseId}-${Date.now()}-${crypto.randomBytes(3).toString("hex")}`
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .slice(0, 80);
  const email = `viventium-voice-qa-${qaSlug}@example.com`;
  const roomName = createRoomName(callSessionId);
  const ownerParticipantIdentity = `owner-${crypto.randomUUID()}`;
  const browserCapability = createBrowserCallCapability(now);
  const expiresAt = browserCapability.expiresAt;
  const requestedVoiceRoute = {
    stt: {
      provider: sttProvider,
      variant: sttVariant || null,
    },
    tts: {
      provider: ttsProvider,
      variant: ttsVariant || null,
    },
  };

  await db.collection("users").insertOne({
    _id: userId,
    name: "Viventium Voice QA",
    username: `voice-qa-${qaSlug}`.slice(0, 120),
    email,
    emailVerified: true,
    provider: "local",
    role: "USER",
    termsAccepted: true,
    createdAt: now,
    updatedAt: now,
    personalization: { memories: false, conversation_recall: false },
    viventiumApprovalStatus: "approved",
    viventiumVoicePreferences: {},
  });

  await db.collection("viventiumcallsessions").insertOne({
    callSessionId,
    userId: userId.toString(),
    agentId: interactive ? agentId : agentName,
    conversationId: "new",
    roomName,
    gatewayAgentName: agentName,
    ownerParticipantIdentity,
    expiresAt,
    browserCapabilityHash: browserCapability.hash,
    browserCapabilityExpiresAt: expiresAt,
    browserCapabilityVersion: 1,
    browserCapabilityScope: 'call_browser_v1',
    mode,
    callStatus: "created",
    callModeRevision: 0,
    wingModeEnabled: mode === "wing",
    shadowModeEnabled: mode === "wing",
    listenOnlyModeEnabled: mode === "listen_only",
    requestedVoiceRoute,
    createdAt: now,
    updatedAt: now,
  });

  const seeded = {
    callSessionId,
    roomName,
    ownerParticipantIdentity,
    requestedVoiceRoute,
    mode,
    userId: userId.toString(),
    email,
  };
  Object.defineProperty(seeded, "browserCapability", {
    value: browserCapability.capability,
    enumerable: false,
  });
  return seeded;
}

async function fetchJsonStatus(url, headers = {}) {
  try {
    const response = await fetch(url.toString(), { cache: "no-store", headers });
    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { message: text.slice(0, 500) };
      }
    }
    return { ok: response.ok, status: response.status, payload };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      payload: { message: String(error?.message || error) },
    };
  }
}

async function preflightPlaygroundProxies(playgroundUrl, callSessionId, browserCapability) {
  const stateUrl = new URL("/api/call-session-state", playgroundUrl);
  stateUrl.searchParams.set("callSessionId", callSessionId);
  const settingsUrl = new URL(
    "/api/call-session-voice-settings",
    playgroundUrl,
  );
  settingsUrl.searchParams.set("callSessionId", callSessionId);
  const headers = browserCapabilityHeaders(browserCapability);
  const [state, voiceSettings] = await Promise.all([
    fetchJsonStatus(stateUrl, headers),
    fetchJsonStatus(settingsUrl, headers),
  ]);
  return { state, voiceSettings };
}

async function cleanupSyntheticRecords(db, seeded) {
  const syntheticUser = await db.collection("users").findOne({
    _id: new ObjectId(seeded.userId),
    email: seeded.email,
  });
  if (
    !syntheticUser ||
    !String(seeded.email || "").startsWith("viventium-voice-qa-") ||
    !String(seeded.email || "").endsWith("@example.com")
  ) {
    throw new Error("Refusing cleanup because the synthetic QA user guard did not match");
  }
  const messageFilter = { user: seeded.userId };
  const messages = await db
    .collection("messages")
    .find(messageFilter, { projection: { _id: 1 } })
    .toArray();
  const messageIds = messages.map((message) => message._id);
  const conversationDeletePromise = db
    .collection("conversations")
    .deleteMany({ user: seeded.userId });

  const [
    messageDelete,
    conversationDelete,
    ingressDelete,
    speakerDelete,
    sessionDelete,
    userDelete,
  ] = await Promise.all([
    db.collection("messages").deleteMany(messageFilter),
    conversationDeletePromise,
    db
      .collection("viventiumvoiceingressevents")
      .deleteMany({ callSessionId: seeded.callSessionId }),
    db
      .collection("viventiumvoicespeakersegments")
      .deleteMany({ callSessionId: seeded.callSessionId }),
    db
      .collection("viventiumcallsessions")
      .deleteOne({ callSessionId: seeded.callSessionId }),
    db
      .collection("users")
      .deleteOne({ _id: new ObjectId(seeded.userId), email: seeded.email }),
  ]);

  return {
    messages: messageDelete.deletedCount,
    messageIds: messageIds.length,
    conversations: conversationDelete.deletedCount || 0,
    ingressEvents: ingressDelete.deletedCount,
    speakerSegments: speakerDelete.deletedCount,
    callSessions: sessionDelete.deletedCount,
    users: userDelete.deletedCount,
  };
}

async function waitForTranscript(db, seeded, expected, waitMs, minTokenRatio) {
  const started = Date.now();
  let latest = [];
  let latestCombined = "";
  while (Date.now() - started < waitMs) {
    latest = await db
      .collection("messages")
      .find({
        user: seeded.userId,
        "metadata.viventium.callSessionId": seeded.callSessionId,
        "metadata.viventium.type": "listen_only_transcript",
      })
      .sort({ createdAt: 1 })
      .toArray();
    latestCombined = latest.map((message) => message.text || "").join(" ");
    if (
      latest.length > 0 &&
      orderedTokenMatch(latestCombined, expected, minTokenRatio)
    ) {
      return {
        ok: true,
        unorderedOk: tokenMatch(latestCombined, expected, minTokenRatio),
        messages: latest,
        combinedText: latestCombined,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return {
    ok: false,
    unorderedOk: tokenMatch(latestCombined, expected, minTokenRatio),
    messages: latest,
    combinedText: latestCombined,
  };
}

function messageText(message) {
  if (typeof message?.text === "string") {
    return message.text;
  }
  if (!Array.isArray(message?.content)) {
    return "";
  }
  return message.content
    .map((part) =>
      typeof part === "string"
        ? part
        : typeof part?.text === "string"
          ? part.text
          : "",
    )
    .filter(Boolean)
    .join("\n");
}

async function waitForInteractiveTurn(db, seeded, expected, waitMs, minTokenRatio) {
  const started = Date.now();
  let latest = [];
  while (Date.now() - started < waitMs) {
    latest = await db
      .collection("messages")
      .find({ user: seeded.userId })
      .sort({ createdAt: 1, _id: 1 })
      .toArray();
    const userText = latest
      .filter((message) => message.isCreatedByUser === true)
      .map(messageText)
      .join(" ");
    const assistantMessages = latest.filter(
      (message) =>
        message.isCreatedByUser !== true &&
        message.metadata?.viventium?.type !== "listen_only_transcript" &&
        messageText(message).trim(),
    );
    if (
      tokenMatch(userText, expected, minTokenRatio) &&
      assistantMessages.length > 0
    ) {
      return {
        ok: true,
        userText,
        assistantMessages,
        assistantText: assistantMessages.map(messageText).join("\n\n"),
        messages: latest,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return {
    ok: false,
    userText: latest
      .filter((message) => message.isCreatedByUser === true)
      .map(messageText)
      .join(" "),
    assistantMessages: [],
    assistantText: "",
    messages: latest,
  };
}

async function waitForCompletedInteractiveTask(db, seeded, waitMs) {
  const started = Date.now();
  let latest = null;
  while (Date.now() - started < waitMs) {
    latest = await db.collection("viventiumvoicetasks").findOne(
      {
        callSessionId: seeded.callSessionId,
        userId: seeded.userId,
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    const state = String(latest?.payload?.state || "");
    if (
      state === "completed" &&
      String(latest?.payload?.current?.resultMessageId || "").trim()
    ) {
      return { ok: true, state, task: latest };
    }
    if (["failed", "cancelled"].includes(state)) {
      return { ok: false, state, task: latest };
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return {
    ok: false,
    state: String(latest?.payload?.state || ""),
    task: latest,
  };
}

async function installExternalTurnProbeAndPublicMediaProxy(page, args) {
  await page.addInitScript(
    ({
      turnUrls,
      username,
      credential,
      forceRelay,
      publicMediaCandidate,
      publicMediaProxy,
      turnProxyUrl,
    }) => {
      const callStates = [];
      Object.defineProperty(globalThis, "__viventiumQaCallStates", {
        value: callStates,
        configurable: true,
      });
      const recordCallState = () => {
        const text = [...document.querySelectorAll('[role="status"]')]
          .map((item) => item.textContent || "")
          .join(" ")
          .trim()
          .toLowerCase();
        if (!text || callStates.at(-1)?.text === text) {
          return;
        }
        callStates.push({ atMs: Date.now(), text });
      };
      const observeCallState = () => {
        recordCallState();
        const target = document.body || document.documentElement;
        if (!target) {
          return;
        }
        new MutationObserver(recordCallState).observe(target, {
          childList: true,
          subtree: true,
          characterData: true,
        });
      };
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", observeCallState, {
          once: true,
        });
      } else {
        observeCallState();
      }

      const OriginalRTCPeerConnection = globalThis.RTCPeerConnection;
      if (!OriginalRTCPeerConnection) {
        return;
      }

      function parseEndpoint(value) {
        const separator = value.lastIndexOf(":");
        if (separator <= 0) {
          return null;
        }
        const address = value.slice(0, separator);
        const port = Number(value.slice(separator + 1));
        return address && Number.isInteger(port) && port > 0
          ? { address, port }
          : null;
      }

      const targetEndpoint = parseEndpoint(publicMediaCandidate);
      const proxyEndpoint = parseEndpoint(publicMediaProxy);

      function rewriteRemoteCandidate(candidateValue) {
        if (!targetEndpoint || !proxyEndpoint || !candidateValue) {
          return { candidate: candidateValue, matched: false, allowed: true };
        }
        const prefix = candidateValue.startsWith("a=") ? "a=" : "";
        const fields = candidateValue.slice(prefix.length).trim().split(/\s+/);
        const protocol = String(fields[2] || "").toLowerCase();
        const address = fields[4] || "";
        const port = Number(fields[5] || 0);
        if (
          protocol !== "tcp" ||
          address !== targetEndpoint.address ||
          port !== targetEndpoint.port
        ) {
          return { candidate: candidateValue, matched: false, allowed: false };
        }
        fields[4] = proxyEndpoint.address;
        fields[5] = String(proxyEndpoint.port);
        return {
          candidate: `${prefix}${fields.join(" ")}`,
          matched: true,
          allowed: true,
        };
      }

      function rewriteRemoteSdp(sdp, entry) {
        if (!targetEndpoint || !proxyEndpoint || !sdp) {
          return sdp;
        }
        const lines = sdp.split(/\r?\n/);
        const rewritten = [];
        for (const line of lines) {
          if (!line.startsWith("a=candidate:")) {
            rewritten.push(line);
            continue;
          }
          const result = rewriteRemoteCandidate(line);
          if (!result.allowed) {
            continue;
          }
          if (result.matched) {
            entry.publicCandidateRewriteCount += 1;
          }
          rewritten.push(result.candidate);
        }
        return rewritten.join("\r\n");
      }

      const peerConnections = [];
      Object.defineProperty(globalThis, "__viventiumQaPeerConnections", {
        value: peerConnections,
        configurable: true,
      });

      function QaRTCPeerConnection(configuration, constraints) {
        const nextConfiguration = { ...(configuration || {}) };
        let turnProxyCredentialsAvailable = false;
        if (turnUrls.length) {
          Object.assign(nextConfiguration, {
            iceServers: [{ urls: turnUrls, username, credential }],
            iceTransportPolicy: forceRelay ? "relay" : configuration?.iceTransportPolicy,
          });
        }
        if (turnProxyUrl) {
          const dynamicTurnServer = (configuration?.iceServers || []).find(
            (server) => server?.username && server?.credential,
          );
          turnProxyCredentialsAvailable = Boolean(dynamicTurnServer);
          Object.assign(nextConfiguration, {
            iceServers: [
              {
                ...(dynamicTurnServer || {}),
                urls: turnProxyUrl,
              },
            ],
            iceTransportPolicy: forceRelay ? "relay" : configuration?.iceTransportPolicy,
          });
        }
        const peerConnection = new OriginalRTCPeerConnection(
          nextConfiguration,
          constraints,
        );
        const entry = {
          peerConnection,
          states: [],
          localCandidateTypes: [],
          publicCandidateRewriteCount: 0,
          turnProxyCredentialsAvailable,
        };
        const originalSetRemoteDescription =
          peerConnection.setRemoteDescription.bind(peerConnection);
        peerConnection.setRemoteDescription = (description) => {
          if (!description?.sdp || !targetEndpoint || !proxyEndpoint) {
            return originalSetRemoteDescription(description);
          }
          return originalSetRemoteDescription({
            type: description.type,
            sdp: rewriteRemoteSdp(description.sdp, entry),
          });
        };
        const originalAddIceCandidate =
          peerConnection.addIceCandidate.bind(peerConnection);
        peerConnection.addIceCandidate = (candidate) => {
          if (!candidate?.candidate || !targetEndpoint || !proxyEndpoint) {
            return originalAddIceCandidate(candidate);
          }
          const rewritten = rewriteRemoteCandidate(candidate.candidate);
          if (!rewritten.allowed) {
            return Promise.resolve();
          }
          if (rewritten.matched) {
            entry.publicCandidateRewriteCount += 1;
          }
          const nextCandidate = candidate.toJSON
            ? candidate.toJSON()
            : { ...candidate };
          nextCandidate.candidate = rewritten.candidate;
          return originalAddIceCandidate(nextCandidate);
        };
        const recordState = () => {
          entry.states.push({
            connectionState: peerConnection.connectionState,
            iceConnectionState: peerConnection.iceConnectionState,
            iceGatheringState: peerConnection.iceGatheringState,
          });
        };
        peerConnection.addEventListener("connectionstatechange", recordState);
        peerConnection.addEventListener("iceconnectionstatechange", recordState);
        peerConnection.addEventListener("icecandidate", (event) => {
          const match = event.candidate?.candidate?.match(/\btyp\s+([a-z]+)/i);
          if (match) {
            entry.localCandidateTypes.push(match[1].toLowerCase());
          }
        });
        recordState();
        peerConnections.push(entry);
        return peerConnection;
      }

      QaRTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;
      Object.setPrototypeOf(QaRTCPeerConnection, OriginalRTCPeerConnection);
      globalThis.RTCPeerConnection = QaRTCPeerConnection;
      if (globalThis.webkitRTCPeerConnection) {
        globalThis.webkitRTCPeerConnection = QaRTCPeerConnection;
      }
    },
    {
      turnUrls: args.externalTurnUrls,
      username: args.externalTurnUsername,
      credential: args.externalTurnCredential,
      forceRelay: args.forceRelay,
      publicMediaCandidate: args.publicMediaCandidate,
      publicMediaProxy: args.publicMediaProxy,
      turnProxyUrl: args.turnProxyUrl,
    },
  );
  return true;
}

function normalizeCallReadinessEvidence(value = {}) {
  const statusText = String(value.statusText || "").toLowerCase();
  const peerStates = (Array.isArray(value.peers) ? value.peers : [])
    .slice(0, 4)
    .map((peer) => ({
      connectionState: String(peer?.connectionState || "").slice(0, 32),
      iceConnectionState: String(peer?.iceConnectionState || "").slice(0, 32),
    }));
  return {
    controlReady: value.endButtonReady === true,
    settledVisibleState: ["listening", "speaking", "working", "needs input"].some(
      (state) => statusText.includes(state),
    ),
    peerConnected: peerStates.some(
      (peer) =>
        peer.connectionState === "connected" &&
        ["connected", "completed"].includes(peer.iceConnectionState),
    ),
    peerCount: peerStates.length,
    peerStates,
  };
}

async function collectCallReadinessEvidence(page) {
  const raw = await page.evaluate(() => {
    const endButton = [...document.querySelectorAll("button")].find(
      (button) => button.getAttribute("aria-label")?.toLowerCase() === "end call",
    );
    const callStatus = [...document.querySelectorAll('[role="status"][aria-label]')].find(
      (item) =>
        (item.getAttribute("aria-label") || "")
          .toLowerCase()
          .startsWith("call status:"),
    );
    const peers = (globalThis.__viventiumQaPeerConnections || []).map((entry) => ({
      connectionState: entry.peerConnection.connectionState,
      iceConnectionState: entry.peerConnection.iceConnectionState,
    }));
    return {
      endButtonReady: Boolean(endButton && !endButton.disabled),
      statusText: callStatus?.textContent || "",
      peers,
    };
  });
  return normalizeCallReadinessEvidence(raw);
}

async function waitForCallReadiness(page, timeoutMs = 45000) {
  const deadlineMs = Date.now() + timeoutMs;
  let latest = normalizeCallReadinessEvidence();
  while (Date.now() < deadlineMs) {
    latest = await collectCallReadinessEvidence(page);
    if (latest.controlReady && latest.settledVisibleState && latest.peerConnected) {
      return latest;
    }
    await page.waitForTimeout(100);
  }
  const error = new Error("Call connection readiness timed out");
  error.connectionReadiness = latest;
  throw error;
}

async function collectRtcEvidence(page) {
  return page.evaluate(async () => {
    const entries = globalThis.__viventiumQaPeerConnections || [];
    const evidence = [];
    for (const entry of entries) {
      const peerConnection = entry.peerConnection;
      const stats = await peerConnection.getStats().catch(() => null);
      const byId = new Map();
      if (stats) {
        stats.forEach((stat) => byId.set(stat.id, stat));
      }
      const selectedPairIds = new Set();
      for (const stat of byId.values()) {
        if (stat.type === "transport" && stat.selectedCandidatePairId) {
          selectedPairIds.add(stat.selectedCandidatePairId);
        }
        if (
          stat.type === "candidate-pair" &&
          stat.state === "succeeded" &&
          (stat.nominated || stat.selected)
        ) {
          selectedPairIds.add(stat.id);
        }
      }
      const selectedCandidatePairs = [];
      let inboundAudioBytesReceived = 0;
      let inboundAudioPacketsReceived = 0;
      let receivedAudioEnergy = 0;
      let receivedAudioDurationSeconds = 0;
      for (const stat of byId.values()) {
        if (stat.type !== "inbound-rtp" || stat.kind !== "audio") {
          continue;
        }
        inboundAudioBytesReceived += Number(stat.bytesReceived || 0);
        inboundAudioPacketsReceived += Number(stat.packetsReceived || 0);
        receivedAudioEnergy += Number(stat.totalAudioEnergy || 0);
        receivedAudioDurationSeconds += Number(stat.totalSamplesDuration || 0);
      }
      for (const pairId of selectedPairIds) {
        const pair = byId.get(pairId);
        const local = pair ? byId.get(pair.localCandidateId) : null;
        const remote = pair ? byId.get(pair.remoteCandidateId) : null;
        if (!pair) {
          continue;
        }
        selectedCandidatePairs.push({
          state: pair.state || "",
          nominated: Boolean(pair.nominated || pair.selected),
          localCandidateType: local?.candidateType || "",
          remoteCandidateType: remote?.candidateType || "",
          protocol: local?.protocol || remote?.protocol || "",
          localRelayProtocol: local?.relayProtocol || "",
          remoteRelayProtocol: remote?.relayProtocol || "",
        });
      }
      evidence.push({
        connectionState: peerConnection.connectionState,
        iceConnectionState: peerConnection.iceConnectionState,
        iceGatheringState: peerConnection.iceGatheringState,
        signalingState: peerConnection.signalingState,
        localCandidateTypes: [...new Set(entry.localCandidateTypes)],
        publicCandidateRewriteCount: entry.publicCandidateRewriteCount || 0,
        turnProxyCredentialsAvailable: Boolean(
          entry.turnProxyCredentialsAvailable,
        ),
        inboundAudioBytesReceived,
        inboundAudioPacketsReceived,
        receivedAudioEnergy,
        receivedAudioDurationSeconds,
        selectedCandidatePairs,
        states: entry.states,
      });
    }
    return evidence;
  });
}

function sumRtcAudioEvidence(rtcPeerConnections) {
  return rtcPeerConnections.reduce(
    (current, peer) => ({
      bytes: current.bytes + Number(peer.inboundAudioBytesReceived || 0),
      packets: current.packets + Number(peer.inboundAudioPacketsReceived || 0),
      energy: current.energy + Number(peer.receivedAudioEnergy || 0),
      durationSeconds:
        current.durationSeconds + Number(peer.receivedAudioDurationSeconds || 0),
    }),
    { bytes: 0, packets: 0, energy: 0, durationSeconds: 0 },
  );
}

async function waitForDeliveredAudio(page, waitMs, baseline) {
  const started = Date.now();
  let rtcPeerConnections = [];
  let totals = { bytes: 0, packets: 0, energy: 0, durationSeconds: 0 };
  while (Date.now() - started < waitMs) {
    rtcPeerConnections = await collectRtcEvidence(page);
    totals = sumRtcAudioEvidence(rtcPeerConnections);
    const delta = {
      bytes: totals.bytes - baseline.bytes,
      packets: totals.packets - baseline.packets,
      energy: totals.energy - baseline.energy,
      durationSeconds: totals.durationSeconds - baseline.durationSeconds,
    };
    if (delta.bytes > 0 && delta.packets > 0 && delta.energy > 0) {
      return { ok: true, rtcPeerConnections, totals, delta };
    }
    await page.waitForTimeout(250);
  }
  return {
    ok: false,
    rtcPeerConnections,
    totals,
    delta: {
      bytes: totals.bytes - baseline.bytes,
      packets: totals.packets - baseline.packets,
      energy: totals.energy - baseline.energy,
      durationSeconds: totals.durationSeconds - baseline.durationSeconds,
    },
  };
}

async function waitForCompletedPlayback(page, sinceMs, waitMs) {
  const started = Date.now();
  let states = [];
  while (Date.now() - started < waitMs) {
    states = await page.evaluate(
      () => globalThis.__viventiumQaCallStates || [],
    );
    const relevant = states.filter((state) => state.atMs >= sinceMs);
    const latestSpeakingIndex = relevant.findLastIndex((state) =>
      state.text.includes("speaking"),
    );
    if (
      latestSpeakingIndex >= 0 &&
      relevant
        .slice(latestSpeakingIndex + 1)
        .some((state) => state.text.includes("listening"))
    ) {
      return { ok: true, states };
    }
    await page.waitForTimeout(250);
  }
  return { ok: false, states };
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const mongoUri = process.env.MONGO_URI;
  if (!mongoUri) {
    throw new Error("MONGO_URI is required");
  }
  assertLocalMongoUri(mongoUri, args.allowNonLocalMongo);

  const client = new MongoClient(mongoUri);
  await client.connect();
  const db = client.db();
  let browser;
  let page;
  let seeded;
  let cleanup = null;
  const consoleMessages = [];
  const pageErrors = [];
  const result = {
    caseId: args.caseId,
    ok: false,
    transportOk: false,
    semanticEvaluationStatus: "not_evaluated",
    seeded: false,
    proxyPreflight: null,
    pageMatchedExpected: false,
    transcriptMatchedExpected: false,
    transcriptUnorderedMatchedExpected: false,
    transcriptCount: 0,
    transcriptCountWithinLimit: true,
    mode: args.mode,
    zeroSetupStartActions: 0,
    autoConnected: false,
    connectionReadiness: normalizeCallReadinessEvidence(),
    connectionReadinessAfterFailure: null,
    interactive: args.interactive,
    interactiveTurnCompleted: false,
    completedVoiceTask: false,
    completedVoiceTaskState: "",
    assistantResponsePresent: false,
    deliveredAudioPresent: false,
    playbackCompleted: false,
    callStateTransitions: [],
    inboundAudioBytesReceived: 0,
    inboundAudioPacketsReceived: 0,
    receivedAudioEnergy: 0,
    receivedAudioDurationSeconds: 0,
    deliveredAudioBytesDelta: 0,
    deliveredAudioPacketsDelta: 0,
    deliveredAudioEnergyDelta: 0,
    deliveredAudioDurationSecondsDelta: 0,
    assistantRoute: null,
    voiceLlmProviderIsIndependent: false,
    activeJobPresent: false,
    speakerSegmentCount: 0,
    speakerLabelCount: 0,
    speakerActorTrust: [],
    sessionStatus: "",
    sessionRevision: 0,
    micToggleClicked: false,
    externalTurnConfigured: args.externalTurnUrls.length > 0,
    forceRelay: args.forceRelay,
    externalRelaySelected: false,
    publicMediaProxyConfigured: Boolean(args.publicMediaCandidate),
    publicCandidateRewriteCount: 0,
    externalTcpMediaSelected: false,
    turnProxyConfigured: Boolean(args.turnProxyUrl),
    turnTlsRelaySelected: false,
    browserProxyConfigured: Boolean(args.browserProxy),
    browserProxyMediaSelected: false,
    disableNonProxiedUdp: args.disableNonProxiedUdp,
    rtcConnected: false,
    rtcPeerConnections: [],
    cleanup: null,
    errorCodes: [],
  };

  try {
    seeded = await seedCallSession(db, args);
    result.seeded = true;
    const proxyPreflight = await preflightPlaygroundProxies(
      args.playgroundUrl,
      seeded.callSessionId,
      seeded.browserCapability,
    );
    result.proxyPreflight = {
      state: {
        ok: proxyPreflight.state.ok,
        status: proxyPreflight.state.status,
      },
      voiceSettings: {
        ok: proxyPreflight.voiceSettings.ok,
        status: proxyPreflight.voiceSettings.status,
      },
    };
    const voiceSettingsPreflightUsable =
      proxyPreflight.voiceSettings.ok ||
      proxyPreflight.voiceSettings.status === 504;
    if (!proxyPreflight.state.ok || !voiceSettingsPreflightUsable) {
      throw new Error(
        `call session proxy preflight failed: state=${proxyPreflight.state.status} ` +
          `voiceSettings=${proxyPreflight.voiceSettings.status}`,
      );
    }
    const url = buildCallBootstrapUrl(
      args.browserPlaygroundUrl,
      seeded.callSessionId,
      seeded.browserCapability,
    );

    const chromiumArgs = [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--disable-features=LocalNetworkAccessChecks",
      `--use-file-for-fake-audio-capture=${args.audio}`,
    ];
    if (args.turnProxyHostRule) {
      chromiumArgs.push(
        `--host-resolver-rules=${args.turnProxyHostRule}`,
      );
    }
    if (args.disableNonProxiedUdp) {
      chromiumArgs.push(
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
      );
    }
    const launchOptions = {
      headless: !args.headed,
      args: chromiumArgs,
    };
    if (args.browserProxy) {
      launchOptions.proxy = { server: args.browserProxy };
    }
    browser = await chromium.launch({
      channel: "chrome",
      ...launchOptions,
    });
    const context = await browser.newContext();
    await context.grantPermissions(["microphone"], {
      origin: args.browserPlaygroundUrl,
    });
    page = await context.newPage();
    page.on("console", (message) => {
      const type = message.type();
      const text = message.text();
      consoleMessages.push({ type, text });
    });
    page.on("pageerror", (error) => {
      pageErrors.push(String(error?.message || error));
    });
    await installExternalTurnProbeAndPublicMediaProxy(page, args);

    await page.goto(url.toString(), {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await assertCallBootstrapStripped(page, seeded.callSessionId);
    result.connectionReadiness = await waitForCallReadiness(page);
    result.autoConnected = true;
    await page.waitForTimeout(1500);
    const micPromptVisible = await page
      .getByText(/turn on your microphone/i)
      .isVisible({ timeout: 1000 })
      .catch(() => false);
    if (micPromptVisible) {
      const micToggle = page
        .locator(
          'button[data-lk-source="microphone"], button[aria-label*="microphone" i], button[title*="microphone" i]',
        )
        .first();
      if ((await micToggle.count().catch(() => 0)) > 0) {
        await micToggle.click({ timeout: 10000 }).catch(() => {});
        result.micToggleClicked = true;
        await page.waitForTimeout(1500);
      }
    }

    const transcript = args.interactive
      ? await waitForInteractiveTurn(
          db,
          seeded,
          args.expect,
          args.waitMs,
          args.minTokenRatio,
        )
      : await waitForTranscript(
          db,
          seeded,
          args.expect,
          args.waitMs,
          args.minTokenRatio,
        );
    const audioBaselineAtMs = Date.now();
    const audioBaseline = sumRtcAudioEvidence(await collectRtcEvidence(page));
    const completedVoiceTask = args.interactive
      ? await waitForCompletedInteractiveTask(
          db,
          seeded,
          args.waitMs,
        )
      : { ok: true, state: "not_applicable", task: null };
    const deliveredAudio = args.interactive
      ? await waitForDeliveredAudio(page, args.waitMs, audioBaseline)
      : {
          ok: true,
          rtcPeerConnections: await collectRtcEvidence(page),
          totals: audioBaseline,
          delta: { bytes: 0, packets: 0, energy: 0, durationSeconds: 0 },
        };
    const completedPlayback = args.interactive
      ? await waitForCompletedPlayback(page, audioBaselineAtMs, args.waitMs)
      : { ok: true, states: [] };
    const finalInteractiveMessages = args.interactive
      ? await db
          .collection("messages")
          .find({ user: seeded.userId })
          .sort({ createdAt: 1, _id: 1 })
          .toArray()
      : transcript.messages;
    const finalUserText = finalInteractiveMessages
      .filter((message) => message.isCreatedByUser === true)
      .map(messageText)
      .join(" ");
    const finalAssistantText = finalInteractiveMessages
      .filter(
        (message) =>
          message.isCreatedByUser !== true &&
          message.metadata?.viventium?.type !== "listen_only_transcript",
      )
      .map(messageText)
      .filter(Boolean)
      .join("\n\n");
    const bodyText = await page
      .locator("body")
      .innerText({ timeout: 5000 })
      .catch(() => "");
    result.pageMatchedExpected = tokenMatch(
      bodyText,
      args.expect,
      args.minTokenRatio,
    );
    result.transcriptMatchedExpected = args.interactive
      ? tokenMatch(finalUserText, args.expect, args.minTokenRatio)
      : transcript.ok;
    result.transcriptUnorderedMatchedExpected = args.interactive
      ? result.transcriptMatchedExpected
      : transcript.unorderedOk;
    result.completedVoiceTask = Boolean(completedVoiceTask.ok);
    result.completedVoiceTaskState = completedVoiceTask.state;
    result.interactiveTurnCompleted =
      args.interactive && result.transcriptMatchedExpected && completedVoiceTask.ok;
    result.assistantResponsePresent =
      args.interactive && Boolean(finalAssistantText.trim());
    result.transcriptCount = args.interactive
      ? finalInteractiveMessages.filter((message) => message.isCreatedByUser === true)
          .length
      : transcript.messages.length;
    result.transcriptCountWithinLimit =
      !Number.isFinite(args.maxTranscriptCount) ||
      args.maxTranscriptCount <= 0 ||
      result.transcriptCount <= args.maxTranscriptCount;

    const sessionAfter = await db
      .collection("viventiumcallsessions")
      .findOne({ callSessionId: seeded.callSessionId });
    const speakerSegments = await db
      .collection("viventiumvoicespeakersegments")
      .find({ callSessionId: seeded.callSessionId })
      .sort({ "payload.sequence": 1, "payload.revision": 1 })
      .toArray();
    result.speakerSegmentCount = speakerSegments.length;
    result.speakerLabelCount = new Set(
      speakerSegments
        .map((segment) => segment?.payload?.speaker?.label)
        .filter(Boolean),
    ).size;
    result.speakerActorTrust = [
      ...new Set(
        speakerSegments
          .map((segment) => segment?.payload?.speaker?.actorTrust)
          .filter(Boolean),
      ),
    ];
    result.sessionStatus = String(sessionAfter?.callStatus || "");
    result.sessionRevision = Number(sessionAfter?.callModeRevision || 0);
    const resolvedAssistantRoute =
      sessionAfter?.assistantRoute ||
      proxyPreflight?.voiceSettings?.payload?.assistantRoute;
    const effectiveAssistantRoute =
      resolvedAssistantRoute?.effective || resolvedAssistantRoute;
    result.assistantRoute = effectiveAssistantRoute
      ? {
          provider: effectiveAssistantRoute.provider || "",
          model: effectiveAssistantRoute.model || "",
        }
      : null;
    result.voiceLlmProviderIsIndependent =
      args.interactive &&
      Boolean(result.assistantRoute?.provider) &&
      result.assistantRoute.provider !== "glasshive-harness";
    result.activeJobPresent = Boolean(
      sessionAfter?.activeJobId || sessionAfter?.activeWorkerId,
    );
    result.deliveredAudioPresent = args.interactive && deliveredAudio.ok;
    result.playbackCompleted = args.interactive && completedPlayback.ok;
    result.callStateTransitions = completedPlayback.states;
    result.inboundAudioBytesReceived = deliveredAudio.totals.bytes;
    result.inboundAudioPacketsReceived = deliveredAudio.totals.packets;
    result.receivedAudioEnergy = deliveredAudio.totals.energy;
    result.receivedAudioDurationSeconds = deliveredAudio.totals.durationSeconds;
    result.deliveredAudioBytesDelta = deliveredAudio.delta.bytes;
    result.deliveredAudioPacketsDelta = deliveredAudio.delta.packets;
    result.deliveredAudioEnergyDelta = deliveredAudio.delta.energy;
    result.deliveredAudioDurationSecondsDelta = deliveredAudio.delta.durationSeconds;
    result.rtcPeerConnections = deliveredAudio.rtcPeerConnections;
    result.rtcConnected = result.rtcPeerConnections.some(
      (peer) =>
        peer.connectionState === "connected" &&
        ["connected", "completed"].includes(peer.iceConnectionState),
    );
    result.externalRelaySelected = result.rtcPeerConnections.some((peer) =>
      peer.selectedCandidatePairs.some(
        (pair) => pair.localCandidateType === "relay",
      ),
    );
    result.publicCandidateRewriteCount = result.rtcPeerConnections.reduce(
      (count, peer) => count + peer.publicCandidateRewriteCount,
      0,
    );
    result.externalTcpMediaSelected = result.rtcPeerConnections.some(
      (peer) =>
        peer.publicCandidateRewriteCount > 0 &&
        peer.selectedCandidatePairs.some(
          (pair) =>
            pair.protocol === "tcp" &&
            ["connected", "completed"].includes(peer.iceConnectionState),
        ),
    );
    result.turnTlsRelaySelected = result.rtcPeerConnections.some(
      (peer) =>
        peer.turnProxyCredentialsAvailable &&
        peer.selectedCandidatePairs.some(
          (pair) =>
            pair.localCandidateType === "relay" &&
            (pair.protocol === "tcp" ||
              ["tcp", "tls"].includes(pair.localRelayProtocol)),
        ),
    );
    result.browserProxyMediaSelected = result.rtcPeerConnections.some(
      (peer) =>
        ["connected", "completed"].includes(peer.iceConnectionState) &&
        peer.selectedCandidatePairs.some(
          (pair) =>
            pair.protocol === "tcp" ||
            ["tcp", "tls"].includes(pair.localRelayProtocol),
        ),
    );

    if (args.screenshot) {
      fs.mkdirSync(path.dirname(args.screenshot), {
        recursive: true,
      });
      await page.screenshot({
        path: args.screenshot,
        fullPage: true,
      });
    }

    const endButton = page.getByRole("button", { name: /end call/i });
    if (await endButton.count().catch(() => 0)) {
      await endButton
        .first()
        .click()
        .catch(() => {});
    }

    // Transport/audio success does not score reasoning quality. Evidence-grounded semantic
    // acceptance belongs to the paired truth-seeking bank and its independent rubric.
    result.transportOk =
      result.seeded &&
      result.autoConnected &&
      result.rtcConnected &&
      result.zeroSetupStartActions === 0 &&
      result.activeJobPresent &&
      result.transcriptCount > 0 &&
      result.transcriptCountWithinLimit &&
      result.transcriptMatchedExpected &&
      (!args.interactive ||
        (result.interactiveTurnCompleted &&
          result.assistantResponsePresent &&
          result.deliveredAudioPresent &&
          result.playbackCompleted &&
          result.voiceLlmProviderIsIndependent)) &&
      (!result.externalTurnConfigured || result.externalRelaySelected) &&
      (!result.publicMediaProxyConfigured || result.externalTcpMediaSelected) &&
      (!result.turnProxyConfigured || result.turnTlsRelaySelected) &&
      (!result.browserProxyConfigured || result.browserProxyMediaSelected) &&
      pageErrors.length === 0;
    result.ok = result.transportOk;
  } catch (error) {
    if (error?.connectionReadiness) {
      result.connectionReadiness = error.connectionReadiness;
    } else if (page) {
      result.connectionReadinessAfterFailure = await collectCallReadinessEvidence(page).catch(
        () => null,
      );
    }
    if (page && args.screenshot) {
      fs.mkdirSync(path.dirname(args.screenshot), { recursive: true });
      await page.screenshot({ path: args.screenshot, fullPage: true }).catch(() => {});
    }
    result.errorCodes.push(safeErrorCode(error));
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (seeded && args.cleanup) {
      cleanup = await cleanupSyntheticRecords(db, seeded).catch(() => ({
        errorCode: "cleanup_failed",
      }));
      result.cleanup = cleanup;
    }
    result.consoleErrorCounts = consoleMessages
      .filter((message) => ["error", "warning"].includes(message.type))
      .reduce((counts, message) => {
        counts[message.type] = (counts[message.type] || 0) + 1;
        return counts;
      }, {});
    result.pageErrorCount = pageErrors.length;
    await client.close();
  }

  fs.mkdirSync(path.dirname(args.result), { recursive: true, mode: 0o700 });
  fs.writeFileSync(args.result, JSON.stringify(result, null, 2) + "\n", {
    mode: 0o600,
  });
  process.stdout.write(
    `${JSON.stringify({
      caseId: result.caseId,
      ok: result.ok,
      transportOk: result.transportOk,
      semanticEvaluationStatus: result.semanticEvaluationStatus,
      resultSaved: true,
    })}\n`,
  );
  process.exitCode = result.ok ? 0 : 1;
}

if (require.main === module) {
  run().catch((error) => {
    console.error(safeErrorCode(error));
    process.exit(1);
  });
}

module.exports = {
  assertCallBootstrapStripped,
  browserCapabilityHeaders,
  buildCallBootstrapUrl,
  createBrowserCallCapability,
  normalizeCallReadinessEvidence,
  preflightPlaygroundProxies,
};
