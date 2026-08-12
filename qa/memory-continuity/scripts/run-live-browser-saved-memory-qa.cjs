#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance test for the immediate saved-memory path.
 *
 * The case is intentionally independent of conversation recall: it disables recall before the
 * write, stores a synthetic preference through the normal chat UI, opens a new conversation, and
 * asks for that preference without repeating it. Raw account/chat evidence stays in App Support;
 * the repository receives only a public-safe aggregate report.
 */

const crypto = require('crypto');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const APP_SUPPORT = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium');
const DEFAULT_AGENT_ID = process.env.VIVENTIUM_QA_AGENT_ID || 'agent_viventium_main_95aeb3';

function hashValue(value, length = 16) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const index = line.indexOf('=');
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      value.length >= 2 &&
      value[0] === value[value.length - 1] &&
      (value[0] === '"' || value[0] === "'")
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadRuntimeEnv() {
  const runtime = path.join(APP_SUPPORT, 'runtime');
  const candidates = [
    path.join(runtime, 'runtime.env'),
    path.join(runtime, 'runtime.local.env'),
    path.join(runtime, 'service-env', 'librechat.env'),
    path.join(LIBRECHAT_ROOT, '.env'),
  ];
  const env = { ...process.env };
  for (const candidate of candidates) {
    Object.assign(env, parseEnvFile(candidate));
  }
  const port = String(env.VIVENTIUM_LOCAL_MONGO_PORT || '').trim();
  const database = String(env.VIVENTIUM_LOCAL_MONGO_DB || 'LibreChatViventium').trim();
  if (port) env.MONGO_URI = `mongodb://127.0.0.1:${port}/${database}`;
  return env;
}

function parseArgs(argv) {
  const startedAt = new Date();
  const stamp = timestampSlug(startedAt);
  const marker = `violet-${hashValue(stamp, 10)}`;
  const args = {
    startedAt,
    marker,
    agentId: DEFAULT_AGENT_ID,
    qaUserHash: '',
    apiBase: process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180',
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190',
    headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 240000),
    privateOutputDir: path.join(
      APP_SUPPORT,
      'private-user-data',
      'qa',
      'memory-continuity',
      stamp,
    ),
    publicReport: path.join(
      REPO_ROOT,
      'qa',
      'memory-continuity',
      'reports',
      '2026-08-08-live-browser-saved-memory-model-route.md',
    ),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === '--headed') args.headless = false;
    else if (arg === '--headless') args.headless = true;
    else if (arg === '--agent-id') {
      args.agentId = next;
      index += 1;
    } else if (arg === '--qa-user-hash') {
      args.qaUserHash = String(next || '').trim().toLowerCase();
      index += 1;
    } else if (arg === '--timeout-ms') {
      args.timeoutMs = Number(next);
      index += 1;
    } else if (arg === '--public-report') {
      args.publicReport = path.resolve(next);
      index += 1;
    }
  }
  args.apiBase = args.apiBase.replace(/\/$/, '');
  args.clientBase = args.clientBase.replace(/\/$/, '');
  return args;
}

function ensureLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_qa_jwt_forbidden_in_ci_or_production');
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== '1') {
    throw new Error('local_qa_jwt_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT');
  }
}

function safeError(value) {
  return String(value || 'qa_failed')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email>')
    .replace(/https?:\/\/[^\s)]+/gi, '<url>')
    .replace(/\/Users\/[^\s)]+/g, '<path>')
    .replace(/\b[a-f0-9]{24}\b/gi, '<id>')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer <redacted>')
    .replace(/\s+/g, ' ')
    .slice(0, 360);
}

async function createQaAuth({ env, db, user }) {
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const { ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  if (!env.JWT_SECRET || !env.JWT_REFRESH_SECRET) throw new Error('missing_jwt_prerequisites');
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: String(user._id), sessionId: String(sessionId) },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  const accessToken = jwt.sign(
    {
      id: String(user._id),
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: '2h' },
  );
  await db.collection('sessions').insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash: crypto.createHash('sha256').update(refreshToken).digest('hex'),
  });
  return { sessionId, refreshToken, accessToken };
}

async function attachAuth({ context, args, auth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  await context.addCookies(
    [args.apiBase, args.clientBase].flatMap((url) => [
      {
        name: 'refreshToken',
        value: auth.refreshToken,
        url,
        httpOnly: true,
        sameSite: 'Strict',
        expires,
      },
      {
        name: 'token_provider',
        value: 'librechat',
        url,
        httpOnly: true,
        sameSite: 'Strict',
        expires,
      },
    ]),
  );
}

async function installAccessToken(page, fallbackToken) {
  const refreshed = await page.evaluate(async () => {
    const response = await fetch('/api/auth/refresh', { method: 'POST' });
    const payload = await response.json().catch(() => ({}));
    return { ok: response.ok, token: typeof payload.token === 'string' ? payload.token : '' };
  });
  const token = refreshed.ok && refreshed.token ? refreshed.token : fallbackToken;
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: value }));
  }, token);
  await page.waitForTimeout(400);
  return token;
}

async function apiJson({ args, token, pathname, method = 'GET', body }) {
  const response = await fetch(`${args.apiBase}${pathname}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      'User-Agent': 'ViventiumSavedMemoryBrowserQA/1.0',
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const payload = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, body: payload };
}

async function setPreferences({ args, token, memories, conversationRecall }) {
  const response = await apiJson({
    args,
    token,
    pathname: '/api/memories/preferences',
    method: 'PATCH',
    body: { memories, conversation_recall: conversationRecall },
  });
  const preferences = response.body?.preferences || {};
  if (
    !response.ok ||
    preferences.memories !== memories ||
    preferences.conversation_recall !== conversationRecall
  ) {
    throw new Error(`preference_update_http_${response.status}`);
  }
}

async function getMemories({ args, token }) {
  const response = await apiJson({ args, token, pathname: '/api/memories' });
  if (!response.ok || !Array.isArray(response.body?.memories)) {
    throw new Error(`memory_read_http_${response.status}`);
  }
  return response.body.memories;
}

async function waitForCondition(fn, { timeoutMs, intervalMs = 750, error }) {
  const deadline = Date.now() + timeoutMs;
  let latest;
  while (Date.now() < deadline) {
    latest = await fn();
    if (latest) return latest;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(error);
}

async function submitPrompt(page, prompt) {
  const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message Viventium$/)).last();
  await input.waitFor({ state: 'visible', timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId('send-button').last().click({ timeout: 30000 });
}

function messageText(message) {
  const text = typeof message?.text === 'string' ? message.text : '';
  const content = Array.isArray(message?.content)
    ? message.content
        .map((part) => {
          if (part?.type !== 'text') return '';
          if (typeof part.text === 'string') return part.text;
          return typeof part.text?.value === 'string' ? part.text.value : '';
        })
        .filter(Boolean)
        .join('\n')
    : '';
  return `${text}\n${content}`.trim();
}

async function waitForTurn({ db, userId, prompt, startedAt, timeoutMs }) {
  const userMessage = await waitForCondition(
    () =>
      db.collection('messages').findOne(
        { user: userId, isCreatedByUser: true, text: prompt, createdAt: { $gte: startedAt } },
        { sort: { createdAt: -1, _id: -1 } },
      ),
    { timeoutMs, error: 'browser_user_message_not_persisted' },
  );
  const assistantMessage = await waitForCondition(
    async () => {
      const rows = await db
        .collection('messages')
        .find({
          user: userId,
          conversationId: userMessage.conversationId,
          isCreatedByUser: false,
          createdAt: { $gte: startedAt },
        })
        .sort({ createdAt: -1, _id: -1 })
        .limit(8)
        .toArray();
      const row =
        rows.find(
          (candidate) =>
            candidate.parentMessageId === userMessage.messageId && candidate.unfinished !== true,
        ) || rows.find((candidate) => candidate.unfinished !== true);
      return row && messageText(row).trim() ? row : null;
    },
    { timeoutMs, intervalMs: 1000, error: 'browser_assistant_message_not_persisted' },
  );
  return { userMessage, assistantMessage, assistantText: messageText(assistantMessage) };
}

async function waitForWriterReceipt({ userId, startedAt, timeoutMs }) {
  const userHash = hashValue(userId, 24);
  const receiptPath = path.join(
    APP_SUPPORT,
    'state',
    'memory-continuity-health',
    `${userHash}.writer.json`,
  );
  return waitForCondition(
    async () => {
      try {
        const stat = fs.statSync(receiptPath);
        const payload = JSON.parse(fs.readFileSync(receiptPath, 'utf8'));
        if (stat.mtimeMs < startedAt.getTime() || Date.parse(payload.updatedAt || '') < startedAt.getTime()) {
          return null;
        }
        return payload;
      } catch {
        return null;
      }
    },
    { timeoutMs, intervalMs: 1000, error: 'fresh_memory_writer_receipt_not_observed' },
  );
}

async function restoreMemory({ args, token, key, original, current }) {
  if (!current) throw new Error('cleanup_memory_missing_after_write');
  if (original) {
    const response = await apiJson({
      args,
      token,
      pathname: `/api/memories/entries/${encodeURIComponent(key)}`,
      method: 'PATCH',
      body: {
        key,
        value: original.value,
        expectedRevision: current.revision,
      },
    });
    if (!response.ok) throw new Error(`cleanup_memory_restore_http_${response.status}`);
  } else {
    const response = await apiJson({
      args,
      token,
      pathname: `/api/memories/entries/${encodeURIComponent(key)}?revision=${current.revision}`,
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`cleanup_memory_delete_http_${response.status}`);
  }
}

function sqliteJson(databasePath, sql) {
  const output = execFileSync('sqlite3', ['-json', databasePath, sql], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
  return output ? JSON.parse(output) : [];
}

function cleanupGlassHiveConversations(conversationIds) {
  const exactIds = [...new Set(conversationIds.filter(Boolean))];
  if (exactIds.length === 0) return true;
  if (!exactIds.every((value) => /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(value))) {
    throw new Error('glasshive_cleanup_refused_invalid_conversation_id');
  }
  const databasePath = path.join(
    APP_SUPPORT,
    'state',
    'runtime',
    'isolated',
    'glasshive',
    'runtime_phase1.db',
  );
  if (!fs.existsSync(databasePath)) return true;
  const quotedIds = exactIds.map((value) => `'${value}'`).join(',');
  const scope = `conversation_id IN (${quotedIds})`;
  const checks = sqliteJson(
    databasePath,
    `WITH target AS (SELECT * FROM provider_sessions WHERE ${scope})
     SELECT
       (SELECT count(*) FROM target) AS session_count,
       (SELECT count(*) FROM provider_sessions WHERE worker_id IN (SELECT worker_id FROM target)) AS worker_session_count,
       (SELECT count(*) FROM workers WHERE project_id IN (SELECT project_id FROM target)) AS project_worker_count,
       (SELECT count(*) FROM callback_outbox WHERE worker_id IN (SELECT worker_id FROM target)) AS callback_count,
       (SELECT count(*) FROM scheduled_runs WHERE worker_id IN (SELECT worker_id FROM target)) AS scheduled_count,
       (SELECT count(*) FROM recurring_schedule_definitions WHERE worker_id IN (SELECT worker_id FROM target)) AS recurring_count;`,
  )[0] || {};
  if (!checks.session_count) return true;
  if (
    checks.session_count !== checks.worker_session_count ||
    checks.session_count !== checks.project_worker_count ||
    checks.callback_count !== 0 ||
    checks.scheduled_count !== 0 ||
    checks.recurring_count !== 0
  ) {
    throw new Error('glasshive_cleanup_refused_shared_or_active_state');
  }
  execFileSync(
    'sqlite3',
    [
      databasePath,
      `PRAGMA foreign_keys=ON;
       BEGIN IMMEDIATE;
       CREATE TEMP TABLE qa_target_sessions AS
         SELECT session_id, worker_id, project_id FROM provider_sessions WHERE ${scope};
       DELETE FROM provider_activity WHERE request_id IN (
         SELECT request_id FROM provider_requests
         WHERE session_id IN (SELECT session_id FROM qa_target_sessions)
       );
       DELETE FROM provider_requests
         WHERE session_id IN (SELECT session_id FROM qa_target_sessions);
       DELETE FROM events WHERE worker_id IN (SELECT worker_id FROM qa_target_sessions);
       DELETE FROM runs WHERE worker_id IN (SELECT worker_id FROM qa_target_sessions);
       DELETE FROM provider_sessions
         WHERE session_id IN (SELECT session_id FROM qa_target_sessions);
       DELETE FROM workers WHERE worker_id IN (SELECT worker_id FROM qa_target_sessions);
       DELETE FROM projects WHERE project_id IN (SELECT project_id FROM qa_target_sessions);
       DROP TABLE qa_target_sessions;
       COMMIT;`,
    ],
    { stdio: ['ignore', 'pipe', 'pipe'] },
  );
  const remaining = sqliteJson(
    databasePath,
    `SELECT count(*) AS count FROM provider_sessions WHERE ${scope};`,
  )[0]?.count;
  return remaining === 0;
}

function writePublicReport({ args, result }) {
  fs.mkdirSync(path.dirname(args.publicReport), { recursive: true });
  const lines = [
    '<!-- qa-evidence-exempt: Generated focused browser artifact; full-view user-grade acceptance is owned by the universal cognitive-continuity report. -->',
    '',
    `# Live browser saved-memory model-route QA — ${new Date().toISOString().slice(0, 10)}`,
    '',
    `- Status: ${result.pass ? 'PASS' : 'FAIL'}`,
    `- Signed-in surface: local LibreChat, non-admin QA account`,
    `- Writer route: ${result.writerProvider || 'not observed'} / ${result.writerModel || 'not observed'}`,
    `- Writer effort: ${result.writerEffort || 'not observed'}`,
    `- Conversation recall during both turns: ${result.recallDisabled ? 'disabled' : 'not proven'}`,
    `- Synthetic fact written through browser chat: ${result.memoryStored ? 'yes' : 'no'}`,
    `- Stored fact visible in Memories panel: ${result.memoryPanelVisible ? 'yes' : 'no'}`,
    `- Fresh conversation recovered both requested fields: ${result.freshConversationRecovered ? 'yes' : 'no'}`,
    `- Reload preserved the visible answer: ${result.reloadPreserved ? 'yes' : 'no'}`,
    `- DB/message/receipt evidence agreed: ${result.backendEvidenceAgreed ? 'yes' : 'no'}`,
    `- Revision-safe memory cleanup verified: ${result.memoryCleanupVerified ? 'yes' : 'no'}`,
    `- LibreChat and GlassHive synthetic conversation/session cleanup verified: ${result.runtimeCleanupVerified ? 'yes' : 'no'}`,
    `- Original account preferences restored: ${result.preferencesRestored ? 'yes' : 'no'}`,
    `- Account hash: ${result.userHash || 'not available'}`,
    `- Write conversation hash: ${result.writeConversationHash || 'not available'}`,
    `- Read conversation hash: ${result.readConversationHash || 'not available'}`,
    `- Private screenshot/result artifacts: ${result.privateArtifactsSaved ? 'saved outside repository' : 'not saved'}`,
    '',
    'The test used an ordinary-language durable preference without a memory command or named-person/pet fixture, never repeated that preference in the recovery prompt, and disabled conversation recall before both turns. This proves the general saved-memory write/read path rather than transcript recall or a phrase/entity-specific rule.',
    '',
    'Raw prompts, responses, memory values, account identifiers, screenshots, tokens, local paths, and database identifiers are intentionally excluded from this public report.',
  ];
  if (result.error) lines.push('', '## Error', '', `- ${safeError(result.error)}`);
  fs.writeFileSync(args.publicReport, `${lines.join('\n')}\n`, 'utf8');
}

async function main() {
  ensureLocalQaAuth();
  const args = parseArgs(process.argv.slice(2));
  const env = loadRuntimeEnv();
  if (!env.MONGO_URI) throw new Error('missing_mongo_uri');
  const qaEmail = String(env.VIVENTIUM_QA_EMAIL || '').trim().toLowerCase();
  if (!qaEmail && !args.qaUserHash) throw new Error('missing_viventium_qa_email');
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const client = new MongoClient(env.MONGO_URI);
  const result = {
    pass: false,
    recallDisabled: false,
    memoryStored: false,
    memoryPanelVisible: false,
    freshConversationRecovered: false,
    reloadPreserved: false,
    backendEvidenceAgreed: false,
    memoryCleanupVerified: false,
    runtimeCleanupVerified: false,
    preferencesRestored: false,
    privateArtifactsSaved: false,
    error: '',
  };
  let browser;
  let db;
  let user;
  let auth;
  let token;
  let originalMemories = new Map();
  let originalPreferences;
  const conversationIds = [];
  const promptMarker = args.marker;
  const writePrompt =
    `For future workshop packets, I use a graphite cover and the footer code is ${promptMarker}.`;
  const readPrompt = 'Tell me my workshop-packet cover color and footer code. Answer with both only.';
  let page;
  try {
    await client.connect();
    db = client.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    if (args.qaUserHash) {
      const candidates = await db
        .collection('users')
        .find({ role: { $ne: 'ADMIN' } })
        .project({ _id: 1, email: 1, username: 1, provider: 1, role: 1, personalization: 1 })
        .toArray();
      user = candidates.find((candidate) => hashValue(candidate._id, 12) === args.qaUserHash);
    } else {
      user = await db.collection('users').findOne({ email: qaEmail });
    }
    if (!user?._id) throw new Error('configured_qa_user_not_found');
    if (String(user.role || '').toUpperCase() === 'ADMIN') throw new Error('configured_qa_user_must_be_non_admin');
    result.userHash = hashValue(user._id, 12);
    originalPreferences = {
      memories: user.personalization?.memories !== false,
      conversationRecall: user.personalization?.conversation_recall === true,
    };
    const userQuery = {
      $or: [
        { user: user._id },
        { user: String(user._id) },
        { userId: user._id },
        { userId: String(user._id) },
      ],
    };
    const [keyRows, tokenRows] = await Promise.all([
      db.collection('keys').countDocuments(userQuery),
      db.collection('tokens').countDocuments(userQuery),
    ]);
    if (keyRows + tokenRows === 0) throw new Error('qa_connected_account_credentials_not_found');

    auth = await createQaAuth({ env, db, user });
    token = auth.accessToken;
    const initialMemories = await getMemories({ args, token });
    originalMemories = new Map(initialMemories.map((memory) => [memory.key, memory]));
    await setPreferences({
      args,
      token,
      memories: true,
      conversationRecall: false,
    });
    result.recallDisabled = true;

    fs.mkdirSync(args.privateOutputDir, { recursive: true, mode: 0o700 });
    browser = await chromium.launch({ channel: 'chrome', headless: args.headless });
    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1440, height: 960 },
    });
    await context.addInitScript(() => {
      localStorage.setItem('fullPanelCollapse', 'false');
      localStorage.setItem('react-resizable-panels:collapsed', 'false');
    });
    await attachAuth({ context, args, auth });
    page = await context.newPage();
    const agentUrl = `${args.clientBase}/c/new?agent_id=${encodeURIComponent(args.agentId)}`;
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    token = await installAccessToken(page, token);
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    token = await installAccessToken(page, token);

    const writeStartedAt = new Date();
    await submitPrompt(page, writePrompt);
    const writeTurn = await waitForTurn({
      db,
      userId: String(user._id),
      prompt: writePrompt,
      startedAt: writeStartedAt,
      timeoutMs: args.timeoutMs,
    });
    conversationIds.push(writeTurn.userMessage.conversationId);
    result.writeConversationHash = hashValue(writeTurn.userMessage.conversationId, 12);
    const receipt = await waitForWriterReceipt({
      userId: String(user._id),
      startedAt: writeStartedAt,
      timeoutMs: args.timeoutMs,
    });
    result.writerProvider = receipt.provider || '';
    result.writerModel = receipt.model || '';
    result.writerEffort = receipt.effort || '';
    if (receipt.status !== 'ok') throw new Error(`memory_writer_${receipt.reason || 'degraded'}`);

    const writtenMemory = await waitForCondition(
      async () => {
        const rows = await getMemories({ args, token });
        const row = rows.find((memory) => memory.key === 'preferences');
        const normalized = String(row?.value || '').toLowerCase();
        return normalized.includes('graphite') && normalized.includes(promptMarker.toLowerCase()) ? row : null;
      },
      { timeoutMs: args.timeoutMs, intervalMs: 1000, error: 'synthetic_saved_memory_not_persisted' },
    );
    result.memoryStored = true;

    const memoryButtons = page.getByRole('button', { name: 'Memories', exact: true });
    await memoryButtons.first().waitFor({ state: 'attached', timeout: 15000 });
    let memoriesButton;
    for (let index = 0; index < (await memoryButtons.count()); index += 1) {
      const candidate = memoryButtons.nth(index);
      if (await candidate.isVisible()) {
        memoriesButton = candidate;
        break;
      }
    }
    if (memoriesButton) {
      await memoriesButton.click();
      const memoryRegions = page.getByRole('region', { name: 'Memories', exact: true });
      await memoryRegions.first().waitFor({ state: 'visible', timeout: 15000 });
      const memoryFilter = memoryRegions.first().getByLabel('Filter memories');
      if (await memoryFilter.isVisible().catch(() => false)) {
        await memoryFilter.fill(promptMarker);
      }
      await page.waitForTimeout(500);
      const visiblePanelText = (await memoryRegions.allInnerTexts()).join('\n').toLowerCase();
      result.memoryPanelVisible =
        visiblePanelText.includes('graphite') && visiblePanelText.includes(promptMarker.toLowerCase());
      await page.screenshot({
        path: path.join(args.privateOutputDir, 'saved-memory-filtered-panel.png'),
        fullPage: true,
      });
      await memoriesButton.click().catch(() => {});
    }

    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    token = await installAccessToken(page, token);
    const readStartedAt = new Date();
    await submitPrompt(page, readPrompt);
    const readTurn = await waitForTurn({
      db,
      userId: String(user._id),
      prompt: readPrompt,
      startedAt: readStartedAt,
      timeoutMs: args.timeoutMs,
    });
    conversationIds.push(readTurn.userMessage.conversationId);
    result.readConversationHash = hashValue(readTurn.userMessage.conversationId, 12);
    const normalizedAnswer = readTurn.assistantText.toLowerCase();
    result.freshConversationRecovered =
      normalizedAnswer.includes('graphite') && normalizedAnswer.includes(promptMarker.toLowerCase());
    const readReceipt = await waitForWriterReceipt({
      userId: String(user._id),
      startedAt: readStartedAt,
      timeoutMs: args.timeoutMs,
    });
    if (readReceipt.status !== 'ok') {
      throw new Error(`memory_writer_read_turn_${readReceipt.reason || 'degraded'}`);
    }
    await page.waitForFunction(
      ({ color, marker }) => {
        const text = (document.body.innerText || '').toLowerCase();
        return text.includes(color) && text.includes(marker);
      },
      { color: 'graphite', marker: promptMarker.toLowerCase() },
      { timeout: 30000 },
    );
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    token = await installAccessToken(page, token);
    await page.waitForFunction(
      ({ color, marker }) => {
        const text = (document.body.innerText || '').toLowerCase();
        return text.includes(color) && text.includes(marker);
      },
      { color: 'graphite', marker: promptMarker.toLowerCase() },
      { timeout: 30000 },
    );
    result.reloadPreserved = true;
    result.backendEvidenceAgreed =
      result.writerProvider === 'openai' &&
      result.writerModel === 'gpt-5.6-luna' &&
      result.writerEffort === 'medium' &&
      String(writtenMemory.value).toLowerCase().includes(promptMarker.toLowerCase()) &&
      result.freshConversationRecovered;

    await page.screenshot({
      path: path.join(args.privateOutputDir, 'fresh-conversation-after-reload.png'),
      fullPage: true,
    });
    fs.writeFileSync(
      path.join(args.privateOutputDir, 'result.private.json'),
      JSON.stringify(
        {
          marker: promptMarker,
          userHash: result.userHash,
          writerReceipt: receipt,
          readWriterReceipt: readReceipt,
          writeConversationHash: result.writeConversationHash,
          readConversationHash: result.readConversationHash,
          writeAnswerHash: hashValue(writeTurn.assistantText),
          readAnswerHash: hashValue(readTurn.assistantText),
          readAnswerLength: readTurn.assistantText.length,
        },
        null,
        2,
      ),
      { encoding: 'utf8', mode: 0o600 },
    );
    result.privateArtifactsSaved = true;
    result.pass =
      result.recallDisabled &&
      result.memoryStored &&
      result.memoryPanelVisible &&
      result.freshConversationRecovered &&
      result.reloadPreserved &&
      result.backendEvidenceAgreed;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    if (page && args.privateOutputDir) {
      try {
        fs.mkdirSync(args.privateOutputDir, { recursive: true, mode: 0o700 });
        await page.screenshot({
          path: path.join(args.privateOutputDir, 'final-visible-state.png'),
          fullPage: true,
        });
        result.privateArtifactsSaved = true;
      } catch {
        // Best-effort evidence capture must not mask the primary QA result.
      }
    }
    if (db && user && token) {
      try {
        const rows = await getMemories({ args, token });
        const contaminated = rows.filter((memory) =>
          String(memory.value || '').includes(promptMarker),
        );
        for (const current of contaminated) {
          await restoreMemory({
            args,
            token,
            key: current.key,
            original: originalMemories.get(current.key) || null,
            current,
          });
        }
        const after = await getMemories({ args, token });
        result.memoryCleanupVerified = !after.some((memory) =>
          String(memory.value || '').includes(promptMarker),
        );
      } catch (error) {
        result.error = `${result.error || ''}\ncleanup: ${error?.message || error}`.trim();
        result.pass = false;
      }
      try {
        if (originalPreferences) {
          await setPreferences({
            args,
            token,
            memories: originalPreferences.memories,
            conversationRecall: originalPreferences.conversationRecall,
          });
          const restored = await db.collection('users').findOne(
            { _id: user._id },
            { projection: { personalization: 1 } },
          );
          result.preferencesRestored =
            (restored?.personalization?.memories !== false) === originalPreferences.memories &&
            (restored?.personalization?.conversation_recall === true) ===
              originalPreferences.conversationRecall;
        }
      } catch (error) {
        result.error = `${result.error || ''}\npreference cleanup: ${error?.message || error}`.trim();
        result.pass = false;
      }
      try {
        const uniqueConversationIds = [...new Set(conversationIds.filter(Boolean))];
        await db.collection('messages').deleteMany({
          user: String(user._id),
          conversationId: { $in: uniqueConversationIds },
        });
        await db.collection('conversations').deleteMany({
          user: String(user._id),
          conversationId: { $in: uniqueConversationIds },
        });
        if (auth?.sessionId) await db.collection('sessions').deleteOne({ _id: auth.sessionId });
        const remaining = await db.collection('messages').countDocuments({
          user: String(user._id),
          conversationId: { $in: uniqueConversationIds },
        });
        const glassHiveClean = cleanupGlassHiveConversations(uniqueConversationIds);
        result.runtimeCleanupVerified = remaining === 0 && glassHiveClean;
      } catch (error) {
        result.error = `${result.error || ''}\nruntime cleanup: ${error?.message || error}`.trim();
        result.pass = false;
      }
    }
    if (browser) await browser.close().catch(() => {});
    await client.close().catch(() => {});
    result.pass =
      result.pass &&
      result.memoryCleanupVerified &&
      result.runtimeCleanupVerified &&
      result.preferencesRestored;
    writePublicReport({ args, result });
  }
  process.stdout.write(
    `${JSON.stringify({ ...result, error: result.error ? safeError(result.error) : '' }, null, 2)}\n`,
  );
  process.exitCode = result.pass ? 0 : 1;
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${safeError(error?.stack || error)}\n`);
    process.exitCode = 1;
  });
}

module.exports = {
  apiJson,
  attachAuth,
  cleanupGlassHiveConversations,
  createQaAuth,
  getMemories,
  hashValue,
  installAccessToken,
  loadRuntimeEnv,
  parseEnvFile,
  safeError,
};
