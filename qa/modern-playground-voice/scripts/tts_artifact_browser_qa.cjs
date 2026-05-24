#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'modern-playground-voice');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const DEFAULT_AGENT_ID = process.env.VIVENTIUM_QA_AGENT_ID || 'agent_viventium_main_95aeb3';
const LOG_PATH =
  process.env.VIVENTIUM_VOICE_GATEWAY_LOG ||
  path.join(
    process.env.HOME || '',
    'Library',
    'Application Support',
    'Viventium',
    'state',
    'runtime',
    'isolated',
    'logs',
    'voice_gateway.log',
  );

function shortHash(value) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, 12);
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) {
    return values;
  }
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const match = rawLine.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }
    values[match[1]] = match[2].trim().replace(/^['"](.*)['"]$/, '$1');
  }
  return values;
}

function loadEnv() {
  return {
    ...process.env,
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, '.env')),
  };
}

function requireLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('Local QA JWT auth is forbidden in CI or production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1`);
  }
}

function artifactCounts(text) {
  const value = String(text || '');
  return {
    punctuationOnly: /^[\s.,!?;:…]+$/.test(value.trim()) && value.trim().length > 0 ? 1 : 0,
    rawUrl: /\bhttps?:\/\/|\bwww\./i.test(value) ? 1 : 0,
    rawEmail: /\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b/.test(value) ? 1 : 0,
    sourceLabel: /\b(?:sources?|references?|citations?)\s*:/i.test(value) ? 1 : 0,
    markdownLink: /\[[^\]]+\]\([^)]+\)/.test(value) ? 1 : 0,
    codeFence: /```|`[^`]+`/.test(value) ? 1 : 0,
    unknownAngleTag: /<\/?[A-Za-z][A-Za-z0-9_-]*(?:\s+[^<>]*)?>/.test(value) ? 1 : 0,
    internalTurnId: /turn\d+[A-Za-z]+\d+/i.test(value) ? 1 : 0,
    privateUseCitationMarker:
      /(?:\\ue2(?:00|01|02|03|04|06)|ue2(?:00|01|02|03|04|06)|[\uE200-\uE206])/i.test(value)
        ? 1
        : 0,
    knownMissingSpaceJoin:
      /\b(?:clearedis|what'syour|thisthem|tryingto|somethingbefore|threadingthat|keepingViventium|yourswhile|showingup|meetingframed|arethey|walkinginto|notme)\b/i.test(
        value,
      )
        ? 1
        : 0,
  };
}

function addCounts(target, source) {
  for (const [key, value] of Object.entries(source)) {
    target[key] = (target[key] || 0) + Number(value || 0);
  }
}

function parseDebugJsonField(message, name) {
  const marker = `${name}=`;
  const start = message.indexOf(marker);
  if (start < 0) {
    return '';
  }
  const rest = message.slice(start + marker.length);
  const match = rest.match(/^("(?:\\.|[^"\\])*")/);
  if (!match) {
    return '';
  }
  try {
    return JSON.parse(match[1]);
  } catch {
    return '';
  }
}

function scanVoiceLog(offset) {
  const result = {
    rawDeltaCount: 0,
    ttsEmitCount: 0,
    ttsProviderMetricCount: 0,
    ttsProviderCancelledCount: 0,
    ttsProviderCharacters: 0,
    rawArtifacts: {},
    rawAggregateArtifacts: {},
    ttsArtifacts: {},
    ttsAggregateArtifacts: {},
    providerLabels: [],
  };
  if (!fs.existsSync(LOG_PATH)) {
    return result;
  }
  const fd = fs.openSync(LOG_PATH, 'r');
  try {
    const stat = fs.fstatSync(fd);
    const start = Math.min(Number(offset || 0), stat.size);
    const buffer = Buffer.alloc(Math.max(0, stat.size - start));
    if (buffer.length > 0) {
      fs.readSync(fd, buffer, 0, buffer.length, start);
    }
    const rawChunks = [];
    const ttsChunks = [];
    for (const line of buffer.toString('utf8').split(/\r?\n/)) {
      if (
        !line.includes('VoiceMarkup') &&
        !line.includes('Using ') &&
        !line.includes('Prepared fallback provider') &&
        !line.includes('tts_provider_metrics')
      ) {
        continue;
      }
      let message = line;
      try {
        message = JSON.parse(line).message || line;
      } catch {
        // Keep raw log line when it is not JSON.
      }
      const providerMatch = message.match(
        /Using (.+?) TTS(?:\s|\(|$)|Prepared fallback provider: Using (.+?) TTS(?:\s|\(|$)/,
      );
      if (providerMatch) {
        result.providerLabels.push((providerMatch[1] || providerMatch[2] || '').trim());
      }
      if (message.includes('tts_provider_metrics')) {
        result.ttsProviderMetricCount += 1;
        if (/\bcancelled=True\b/.test(message)) {
          result.ttsProviderCancelledCount += 1;
        }
        const charactersMatch = message.match(/\bcharacters=(\d+)/);
        if (charactersMatch) {
          result.ttsProviderCharacters += Number(charactersMatch[1] || 0);
        }
      }
      if (message.includes('[VoiceMarkup] llm_delta')) {
        const raw = parseDebugJsonField(message, 'raw_json');
        result.rawDeltaCount += 1;
        rawChunks.push(raw);
        addCounts(result.rawArtifacts, artifactCounts(raw));
      }
      if (message.includes('[VoiceMarkup] tts_emit')) {
        const chunk = parseDebugJsonField(message, 'chunk_json');
        result.ttsEmitCount += 1;
        ttsChunks.push(chunk);
        addCounts(result.ttsArtifacts, artifactCounts(chunk));
      }
    }
    result.rawAggregateArtifacts = artifactCounts(rawChunks.join(''));
    result.ttsAggregateArtifacts = artifactCounts(ttsChunks.join(''));
  } finally {
    fs.closeSync(fd);
  }
  result.providerLabels = [...new Set(result.providerLabels)].sort();
  return result;
}

async function createQaAuth({ env, db }) {
  const { ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const requestedEmail = String(
    process.env.VIVENTIUM_QA_USER_EMAIL || process.env.VIVENTIUM_QA_EMAIL || '',
  ).trim();
  const query = requestedEmail
    ? { email: requestedEmail }
    : { name: 'Viventium QA', viventiumApprovalStatus: 'approved' };
  const user = await db.collection('users').findOne(query);
  if (!user?._id) {
    throw new Error('QA user not found');
  }
  const userId = user._id.toString();
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: userId, sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  const refreshTokenHash = crypto.createHash('sha256').update(refreshToken).digest('hex');
  await db.collection('sessions').insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash,
  });
  const accessToken = jwt.sign(
    {
      id: userId,
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: '2h' },
  );
  return {
    user,
    userId,
    accessToken,
    sessionId,
    cleanup: async () => db.collection('sessions').deleteOne({ _id: sessionId }),
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { message: text.slice(0, 200) };
    }
  }
  return { ok: response.ok, status: response.status, body };
}

async function cleanupCallArtifacts(db, { userId, callSessionId, conversationId }) {
  const messageFilter = {
    user: userId,
    'metadata.viventium.callSessionId': callSessionId,
  };
  const messages = await db.collection('messages').find(messageFilter, { projection: { _id: 1 } }).toArray();
  const messageIds = messages.map((message) => message._id);
  const [messageDelete, conversationDelete, ingressDelete, sessionDelete] = await Promise.all([
    db.collection('messages').deleteMany(messageFilter),
    messageIds.length
      ? db.collection('conversations').deleteMany({ user: userId, messages: { $in: messageIds } })
      : db.collection('conversations').deleteMany({ user: userId, conversationId }),
    db.collection('viventiumvoiceingressevents').deleteMany({ callSessionId }),
    db.collection('viventiumcallsessions').deleteOne({ callSessionId }),
  ]);
  return {
    messages: messageDelete.deletedCount,
    conversations: conversationDelete.deletedCount,
    ingressEvents: ingressDelete.deletedCount,
    callSessions: sessionDelete.deletedCount,
  };
}

async function main() {
  requireLocalQaAuth();
  const env = loadEnv();
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error('Missing MONGO_URI/JWT secrets');
  }
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const apiBase = process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180';
  const clientBase = process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190';
  const prompt =
    process.env.VIVENTIUM_TTS_ARTIFACT_QA_PROMPT ||
    'Reply exactly with this one line, no extra words: Sources: https://example.com/report Read [brief](https://example.com/brief). Email qa@example.com. References: I have a few good ones. Done.';

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const beforeOffset = fs.existsSync(LOG_PATH) ? fs.statSync(LOG_PATH).size : 0;
  const client = new MongoClient(env.MONGO_URI);
  await client.connect();
  const dbName = new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium';
  const db = client.db(dbName);
  const auth = await createQaAuth({ env, db });
  let browser;
  let call = null;
  let cleanup = null;
  const consoleErrors = [];
  const result = {
    ok: false,
    qaUserHash: shortHash(auth.user.email),
    callSessionHash: '',
    conversationHash: '',
    callCreated: false,
    pageOpened: false,
    startClicked: false,
    transcriptToggled: false,
    promptSent: false,
    inputEnabled: false,
    transcriptVisible: false,
    logScan: null,
    cleanup: null,
    consoleErrorCount: 0,
    consoleErrorHashes: [],
    errors: [],
  };

  try {
    const callResponse = await fetchJson(`${apiBase}/api/viventium/calls`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${auth.accessToken}`,
        'Content-Type': 'application/json',
        'User-Agent': 'ViventiumTtsArtifactQA/1.0',
      },
      body: JSON.stringify({
        conversationId: 'new',
        agentId: DEFAULT_AGENT_ID,
      }),
    });
    if (!callResponse.ok || !callResponse.body.callSessionId || !callResponse.body.playgroundUrl) {
      throw new Error(`call_session_http_${callResponse.status}`);
    }
    call = callResponse.body;
    result.callCreated = true;
    result.callSessionHash = shortHash(call.callSessionId);
    result.conversationHash = shortHash(call.conversationId);

    browser = await chromium.launch({
      headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
      args: [
        '--autoplay-policy=no-user-gesture-required',
        '--use-fake-device-for-media-stream',
        '--use-fake-ui-for-media-stream',
      ],
    });
    const context = await browser.newContext({ baseURL: clientBase, viewport: { width: 1440, height: 1100 } });
    const playgroundOrigin = new URL(call.playgroundUrl).origin;
    await context.grantPermissions(['microphone'], { origin: playgroundOrigin });
    const page = await context.newPage();
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text().slice(0, 300));
      }
    });
    await page.goto(call.playgroundUrl.replace('autoConnect=1', 'autoConnect=0'), {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    result.pageOpened = true;
    await page.getByRole('button', { name: /start chat/i }).click({ timeout: 60_000 });
    result.startClicked = true;
    await page.getByRole('button', { name: /toggle transcript/i }).click({ timeout: 60_000 });
    result.transcriptToggled = true;
    const input = page.getByPlaceholder(/type something/i);
    await input.waitFor({ state: 'visible', timeout: 60_000 });
    await page.waitForFunction(
      () => {
        const field = Array.from(document.querySelectorAll('input, textarea')).find((node) =>
          /type something/i.test(node.getAttribute('placeholder') || ''),
        );
        return Boolean(field && !field.disabled && !field.readOnly);
      },
      null,
      { timeout: 90_000 },
    );
    result.inputEnabled = true;
    await input.fill(prompt, { timeout: 60_000 });
    await page.keyboard.press('Enter');
    result.promptSent = true;

    const started = Date.now();
    while (Date.now() - started < 120_000) {
      const scan = scanVoiceLog(beforeOffset);
      const text = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');
      result.transcriptVisible = /\b(done|brief|email|link available|references)\b/i.test(text);
      const providerCompleted =
        scan.ttsProviderMetricCount > 0 && scan.ttsProviderCancelledCount === 0;
      if (scan.ttsEmitCount > 0 && result.transcriptVisible && providerCompleted) {
        result.logScan = scan;
        break;
      }
      await page.waitForTimeout(1500);
    }
    result.logScan = result.logScan || scanVoiceLog(beforeOffset);
    const tts = result.logScan.ttsArtifacts || {};
    const ttsAggregate = result.logScan.ttsAggregateArtifacts || {};
    const forbiddenTtsArtifacts = [
      'punctuationOnly',
      'rawUrl',
      'rawEmail',
      'sourceLabel',
      'markdownLink',
      'codeFence',
      'unknownAngleTag',
      'internalTurnId',
      'privateUseCitationMarker',
      'knownMissingSpaceJoin',
    ].reduce((sum, key) => sum + Number(tts[key] || 0) + Number(ttsAggregate[key] || 0), 0);
    result.ok =
      result.callCreated &&
      result.pageOpened &&
      result.startClicked &&
      result.promptSent &&
      result.transcriptVisible &&
      result.logScan.ttsEmitCount > 0 &&
      result.logScan.ttsProviderMetricCount > 0 &&
      result.logScan.ttsProviderCancelledCount === 0 &&
      forbiddenTtsArtifacts === 0;

    const endButton = page.getByRole('button', { name: /end call/i });
    if (await endButton.count().catch(() => 0)) {
      await endButton.first().click().catch(() => {});
    }
  } catch (error) {
    result.errors.push(String(error?.stack || error));
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (call?.callSessionId) {
      cleanup = await cleanupCallArtifacts(db, {
        userId: auth.userId,
        callSessionId: call.callSessionId,
        conversationId: call.conversationId,
      }).catch((error) => ({ error: String(error?.message || error) }));
    }
    await auth.cleanup().catch(() => {});
    result.cleanup = cleanup;
    result.consoleErrorCount = consoleErrors.length;
    result.consoleErrorHashes = consoleErrors.slice(0, 5).map((error) => shortHash(error));
    await client.close();
  }

  const outputPath = path.join(OUTPUT_DIR, `tts-artifact-browser-qa-${Date.now()}.json`);
  fs.writeFileSync(outputPath, JSON.stringify(result, null, 2) + '\n');
  result.outputPath = outputPath.replace(REPO_ROOT, '<repo>');
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = result.ok ? 0 : 1;
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
