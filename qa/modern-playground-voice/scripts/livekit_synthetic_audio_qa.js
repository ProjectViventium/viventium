#!/usr/bin/env node
/*
 * Real fake-microphone LiveKit QA harness.
 *
 * It seeds one synthetic Listen-Only call session, opens the modern playground with a WAV file as
 * Chromium's microphone input, waits for the real voice worker/STT path to persist transcript
 * evidence, and cleans up only the synthetic records it created.
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
const OUTPUT_ROOT = path.join(ROOT, "output");

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

function shortHash(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""))
    .digest("hex")
    .slice(0, 12);
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
    } else if (item === "--headed") {
      args.headed = true;
    } else if (item === "--no-cleanup") {
      args.cleanup = false;
    } else if (item === "--allow-non-local-mongo") {
      args.allowNonLocalMongo = true;
    }
  }

  if (!args.audio) {
    throw new Error("--audio is required");
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
  if (args.result) {
    args.result = resolveOutputPath(args.result, "--result");
  }
  if (args.screenshot) {
    args.screenshot = resolveOutputPath(args.screenshot, "--screenshot");
  }
  return args;
}

function resolveOutputPath(value, label) {
  const resolved = path.resolve(value);
  const relative = path.relative(OUTPUT_ROOT, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(
      `${label} must stay under ${path.relative(ROOT, OUTPUT_ROOT)}`,
    );
  }
  return resolved;
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

async function seedCallSession(db, { caseId, agentName }) {
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
    agentId: agentName,
    conversationId: "new",
    roomName,
    expiresAt: new Date(now.getTime() + 15 * 60 * 1000),
    wingModeEnabled: false,
    shadowModeEnabled: false,
    listenOnlyModeEnabled: true,
    requestedVoiceRoute: {
      stt: { provider: "pywhispercpp", variant: "large-v3-turbo" },
      tts: {
        provider: "local_chatterbox_turbo_mlx_8bit",
        variant: "mlx-community/chatterbox-turbo-8bit",
      },
    },
    createdAt: now,
    updatedAt: now,
  });

  return { callSessionId, roomName, userId: userId.toString(), email };
}

async function fetchJsonStatus(url) {
  try {
    const response = await fetch(url.toString(), { cache: "no-store" });
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

async function preflightPlaygroundProxies(playgroundUrl, callSessionId) {
  const stateUrl = new URL("/api/call-session-state", playgroundUrl);
  stateUrl.searchParams.set("callSessionId", callSessionId);
  const settingsUrl = new URL(
    "/api/call-session-voice-settings",
    playgroundUrl,
  );
  settingsUrl.searchParams.set("callSessionId", callSessionId);
  const [state, voiceSettings] = await Promise.all([
    fetchJsonStatus(stateUrl),
    fetchJsonStatus(settingsUrl),
  ]);
  return { state, voiceSettings };
}

async function cleanupSyntheticRecords(db, seeded) {
  const messageFilter = {
    user: seeded.userId,
    "metadata.viventium.callSessionId": seeded.callSessionId,
  };
  const messages = await db
    .collection("messages")
    .find(messageFilter, { projection: { _id: 1 } })
    .toArray();
  const messageIds = messages.map((message) => message._id);
  const conversationDeletePromise =
    messageIds.length > 0
      ? db.collection("conversations").deleteMany({
          user: seeded.userId,
          messages: { $in: messageIds },
        })
      : Promise.resolve({ deletedCount: 0 });

  const [
    messageDelete,
    conversationDelete,
    ingressDelete,
    sessionDelete,
    userDelete,
  ] = await Promise.all([
    db.collection("messages").deleteMany(messageFilter),
    conversationDeletePromise,
    db
      .collection("viventiumvoiceingressevents")
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

async function installExternalTurnProbeAndPublicMediaProxy(page, args) {
  if (
    !args.externalTurnUrls.length &&
    !args.publicMediaCandidate &&
    !args.turnProxyUrl &&
    !args.browserProxy
  ) {
    return false;
  }
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
        selectedCandidatePairs,
        states: entry.states,
      });
    }
    return evidence;
  });
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
  let seeded;
  let cleanup = null;
  const consoleMessages = [];
  const pageErrors = [];
  const result = {
    caseId: args.caseId,
    ok: false,
    seeded: false,
    sessionHash: "",
    roomHash: "",
    proxyPreflight: null,
    pageMatchedExpected: false,
    transcriptMatchedExpected: false,
    transcriptUnorderedMatchedExpected: false,
    transcriptCount: 0,
    transcriptMessageHashes: [],
    transcriptText: "",
    transcriptCountWithinLimit: true,
    activeJobPresent: false,
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
    rtcPeerConnections: [],
    cleanup: null,
    errors: [],
  };

  try {
    seeded = await seedCallSession(db, args);
    result.seeded = true;
    result.sessionHash = shortHash(seeded.callSessionId);
    result.roomHash = shortHash(seeded.roomName);
    result.proxyPreflight = await preflightPlaygroundProxies(
      args.playgroundUrl,
      seeded.callSessionId,
    );
    const voiceSettingsPreflightUsable =
      result.proxyPreflight.voiceSettings.ok ||
      result.proxyPreflight.voiceSettings.status === 504;
    if (!result.proxyPreflight.state.ok || !voiceSettingsPreflightUsable) {
      throw new Error(
        `call session proxy preflight failed: state=${result.proxyPreflight.state.status} ` +
          `voiceSettings=${result.proxyPreflight.voiceSettings.status}`,
      );
    }
    const url = new URL(args.browserPlaygroundUrl);
    url.searchParams.set("agentName", args.agentName);
    url.searchParams.set("callSessionId", seeded.callSessionId);
    url.searchParams.set("roomName", seeded.roomName);
    url.searchParams.set("autoConnect", "0");

    const chromiumArgs = [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
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
      ...launchOptions,
    });
    const context = await browser.newContext();
    await context.grantPermissions(["microphone"], {
      origin: args.browserPlaygroundUrl,
    });
    const page = await context.newPage();
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
    await page
      .getByRole("button", { name: /start chat/i })
      .click({ timeout: 45000 });
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

    const transcript = await waitForTranscript(
      db,
      seeded,
      args.expect,
      args.waitMs,
      args.minTokenRatio,
    );
    const bodyText = await page
      .locator("body")
      .innerText({ timeout: 5000 })
      .catch(() => "");
    result.pageMatchedExpected = tokenMatch(
      bodyText,
      args.expect,
      args.minTokenRatio,
    );
    result.transcriptMatchedExpected = transcript.ok;
    result.transcriptUnorderedMatchedExpected = transcript.unorderedOk;
    result.transcriptCount = transcript.messages.length;
    result.transcriptMessageHashes = transcript.messages.map((message) =>
      shortHash(message.messageId || message._id),
    );
    result.transcriptText = transcript.combinedText;
    result.transcriptCountWithinLimit =
      !Number.isFinite(args.maxTranscriptCount) ||
      args.maxTranscriptCount <= 0 ||
      result.transcriptCount <= args.maxTranscriptCount;

    const sessionAfter = await db
      .collection("viventiumcallsessions")
      .findOne({ callSessionId: seeded.callSessionId });
    result.activeJobPresent = Boolean(
      sessionAfter?.activeJobId || sessionAfter?.activeWorkerId,
    );
    result.rtcPeerConnections = await collectRtcEvidence(page);
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

    result.ok =
      result.seeded &&
      result.activeJobPresent &&
      result.transcriptCount > 0 &&
      result.transcriptCountWithinLimit &&
      result.transcriptMatchedExpected &&
      (!result.externalTurnConfigured || result.externalRelaySelected) &&
      (!result.publicMediaProxyConfigured || result.externalTcpMediaSelected) &&
      (!result.turnProxyConfigured || result.turnTlsRelaySelected) &&
      (!result.browserProxyConfigured || result.browserProxyMediaSelected) &&
      pageErrors.length === 0;
  } catch (error) {
    result.errors.push(String(error?.stack || error));
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (seeded && args.cleanup) {
      cleanup = await cleanupSyntheticRecords(db, seeded).catch((error) => ({
        error: String(error?.message || error),
      }));
      result.cleanup = cleanup;
    }
    result.consoleErrors = consoleMessages
      .filter((message) => ["error", "warning"].includes(message.type))
      .map((message) => ({
        type: message.type,
        text: message.text.slice(0, 500),
      }));
    result.pageErrors = pageErrors;
    await client.close();
  }

  if (args.result) {
    fs.mkdirSync(path.dirname(args.result), { recursive: true });
    fs.writeFileSync(args.result, JSON.stringify(result, null, 2) + "\n");
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = result.ok ? 0 : 1;
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
