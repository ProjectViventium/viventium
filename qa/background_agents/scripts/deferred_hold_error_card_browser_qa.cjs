#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const API_ROOT = path.join(LIBRECHAT_ROOT, 'api');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'background-agents');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const cleanupState = {};

function loadRuntimeEnv() {
  const env = {};
  const envPaths = [
    path.join(
      process.env.HOME || '',
      'Library',
      'Application Support',
      'Viventium',
      'runtime',
      'runtime.env',
    ),
    path.join(LIBRECHAT_ROOT, '.env'),
  ];
  for (const envPath of envPaths) {
    const text = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
    for (const line of text.split(/\r?\n/)) {
      const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (!match) {
        continue;
      }
      env[match[1]] = match[2].replace(/^"(.*)"$/, '$1');
    }
  }
  return env;
}

function requireLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('Local QA JWT auth is forbidden in CI or production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1`);
  }
}

function randomId() {
  return crypto.randomUUID();
}

async function cleanupSyntheticFixture({ closeClient = true } = {}) {
  const { db, sessionId, conversationId, client, browser } = cleanupState;
  if (browser) {
    await browser.close().catch(() => {});
    cleanupState.browser = null;
  }
  if (db) {
    if (conversationId) {
      await db.collection('conversations').deleteOne({ conversationId }).catch(() => {});
      await db.collection('messages').deleteMany({ conversationId }).catch(() => {});
    }
    await db
      .collection('conversations')
      .deleteMany({ title: 'ACT-23 Deferred Hold QA' })
      .catch(() => {});
    await db
      .collection('messages')
      .deleteMany({ 'metadata.viventium.qaCase': 'ACT-23', 'metadata.viventium.qaSynthetic': true })
      .catch(() => {});
    if (sessionId) {
      await db.collection('sessions').deleteOne({ _id: sessionId }).catch(() => {});
    }
  }
  if (client && closeClient) {
    await client.close().catch(() => {});
    cleanupState.client = null;
  }
}

async function main() {
  requireLocalQaAuth();
  const qaEmail = process.env.VIVENTIUM_QA_USER_EMAIL;
  if (!qaEmail) {
    throw new Error('Missing VIVENTIUM_QA_USER_EMAIL');
  }

  const env = { ...loadRuntimeEnv(), ...process.env };
  const mongoUri = env.MONGO_URI || 'mongodb://127.0.0.1:27117/LibreChatViventium';
  const jwtSecret = env.JWT_SECRET;
  const jwtRefreshSecret = env.JWT_REFRESH_SECRET;
  if (!jwtSecret || !jwtRefreshSecret) {
    throw new Error('Missing JWT secrets in runtime env');
  }

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));

  const client = new MongoClient(mongoUri);
  await client.connect();
  cleanupState.client = client;
  const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
  const db = client.db(dbName);
  cleanupState.db = db;
  await cleanupSyntheticFixture({ closeClient: false });
  cleanupState.client = client;
  cleanupState.db = db;
  const user = await db.collection('users').findOne({ email: qaEmail });
  if (!user?._id) {
    throw new Error('QA user not found');
  }

  const userId = user._id.toString();
  const sessionId = new ObjectId();
  cleanupState.sessionId = sessionId;
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: userId, sessionId: sessionId.toString() },
    jwtRefreshSecret,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  const refreshTokenHash = crypto.createHash('sha256').update(refreshToken).digest('hex');
  await db.collection('sessions').insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash,
  });

  const now = new Date();
  const conversationId = randomId();
  cleanupState.conversationId = conversationId;
  const userMessageId = randomId();
  const parentMessageId = randomId();
  const followUpMessageId = randomId();
  const userObjectId = new ObjectId();
  const parentObjectId = new ObjectId();
  const followUpObjectId = new ObjectId();
  const conversationObjectId = new ObjectId();
  const followUpText =
    'Synthetic ACT-23 follow-up: background workspace checks finished without a connection-error banner.';

  await db.collection('messages').insertMany([
    {
      _id: userObjectId,
      user: userId,
      messageId: userMessageId,
      conversationId,
      parentMessageId: '00000000-0000-0000-0000-000000000000',
      isCreatedByUser: true,
      sender: 'User',
      text: 'Synthetic ACT-23 deferred tool-cortex QA prompt',
      endpoint: 'agents',
      model: null,
      tokenCount: 8,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: now,
      updatedAt: now,
      metadata: { viventium: { qaSynthetic: true, qaCase: 'ACT-23' } },
    },
    {
      _id: parentObjectId,
      user: userId,
      messageId: parentMessageId,
      conversationId,
      parentMessageId: userMessageId,
      isCreatedByUser: false,
      sender: 'Viventium',
      text: 'Checking now.',
      endpoint: 'agents',
      model: 'synthetic-act-23',
      tokenCount: 12,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: new Date(now.getTime() + 1),
      updatedAt: new Date(now.getTime() + 1),
      metadata: { viventium: { qaSynthetic: true, qaCase: 'ACT-23' } },
      content: [
        {
          type: 'cortex_insight',
          cortex_id: 'agent_synthetic_ms365',
          cortex_name: 'MS365',
          status: 'complete',
          insight: 'Synthetic MS365 result.',
        },
        {
          type: 'text',
          text: 'Checking now.',
          viventium_runtime_hold: true,
        },
        {
          type: 'error',
          error: 'The model provider could not complete this request.',
          error_class: 'completion_error',
        },
      ],
    },
    {
      _id: followUpObjectId,
      user: userId,
      messageId: followUpMessageId,
      conversationId,
      parentMessageId,
      isCreatedByUser: false,
      sender: 'Viventium',
      text: followUpText,
      endpoint: 'agents',
      model: 'synthetic-act-23',
      tokenCount: 18,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: new Date(now.getTime() + 2),
      updatedAt: new Date(now.getTime() + 2),
      metadata: {
        viventium: {
          qaSynthetic: true,
          qaCase: 'ACT-23',
          type: 'cortex_followup',
          parentMessageId,
          forceVisibleFollowUp: true,
        },
      },
      content: [{ type: 'text', text: followUpText }],
    },
  ]);

  await db.collection('conversations').insertOne({
    _id: conversationObjectId,
    user: userId,
    conversationId,
    title: 'ACT-23 Deferred Hold QA',
    endpoint: 'agents',
    endpointType: 'agents',
    agent_id: 'agent_viventium_main_95aeb3',
    model: 'synthetic-act-23',
    messages: [userObjectId, parentObjectId, followUpObjectId],
    files: [],
    tags: [],
    resendFiles: true,
    isArchived: false,
    expiredAt: null,
    createdAt: now,
    updatedAt: new Date(now.getTime() + 2),
    _meiliIndex: true,
  });

  const parentErrorPartsBeforeRecovery = await db.collection('messages').countDocuments({
    messageId: parentMessageId,
    content: { $elemMatch: { type: 'error', error_class: 'completion_error' } },
  });

  process.env.MONGO_URI = mongoUri;
  process.chdir(API_ROOT);
  const moduleAlias = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'module-alias'));
  moduleAlias.addAlias('~', API_ROOT);
  const mongoose = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongoose'));
  const { connectDb } = require(path.join(API_ROOT, 'db', 'connect'));
  const {
    recoverDeferredHoldParentErrorCards,
  } = require(path.join(API_ROOT, 'server', 'services', 'viventium', 'staleCortexMessageRecovery'));
  await connectDb();
  const recovery = await recoverDeferredHoldParentErrorCards({ limit: 10 });
  await mongoose.disconnect();

  const parentErrorPartsAfterRecovery = await db.collection('messages').countDocuments({
    messageId: parentMessageId,
    content: { $elemMatch: { type: 'error' } },
  });

  const launchOptions = { headless: true };
  let browser;
  try {
    browser = await chromium.launch({ ...launchOptions, channel: 'chrome' });
  } catch {
    browser = await chromium.launch(launchOptions);
  }
  cleanupState.browser = browser;

  const clientBase = process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190';
  const apiBase = process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180';
  const context = await browser.newContext({
    baseURL: clientBase,
    viewport: { width: 1440, height: 1100 },
  });
  const cookieExpires = Math.floor(Date.now() / 1000) + 7200;
  for (const url of [clientBase, apiBase]) {
    await context.addCookies([
      {
        name: 'refreshToken',
        value: refreshToken,
        url,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
      {
        name: 'token_provider',
        value: 'librechat',
        url,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
    ]);
  }

  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text().slice(0, 300));
    }
  });

  await page.goto(`${clientBase}/c/${conversationId}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  const refresh = await page.evaluate(async () => {
    const res = await fetch('/api/auth/refresh', { method: 'POST' });
    const body = await res.json().catch(() => ({}));
    const token = body.token || '';
    if (token) {
      window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: token }));
    }
    return { status: res.status, ok: res.ok, hasToken: token.length > 10 };
  });
  await page.goto(`${clientBase}/c/${conversationId}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  await page.waitForTimeout(1500);

  const beforeRefreshText = await page.locator('body').innerText({ timeout: 20_000 });
  const screenshotPath = path.join(
    OUTPUT_DIR,
    'act-23-deferred-hold-error-cleanup-2026-05-21.png',
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  await page.waitForTimeout(1000);
  const afterRefreshText = await page.locator('body').innerText({ timeout: 20_000 });
  await browser.close();
  cleanupState.browser = null;

  const hasFollowUpBefore = beforeRefreshText.includes(followUpText);
  const hasFollowUpAfter = afterRefreshText.includes(followUpText);
  const errorVisibleBefore =
    beforeRefreshText.includes('Connection error') ||
    beforeRefreshText.includes('Something went wrong') ||
    beforeRefreshText.includes('model provider could not complete');
  const errorVisibleAfter =
    afterRefreshText.includes('Connection error') ||
    afterRefreshText.includes('Something went wrong') ||
    afterRefreshText.includes('model provider could not complete');

  await cleanupSyntheticFixture();

  const result = {
    ok:
      refresh.ok &&
      refresh.hasToken &&
      parentErrorPartsBeforeRecovery === 1 &&
      recovery.repaired >= 1 &&
      parentErrorPartsAfterRecovery === 0 &&
      hasFollowUpBefore &&
      hasFollowUpAfter &&
      !errorVisibleBefore &&
      !errorVisibleAfter,
    refresh,
    parentErrorPartsBeforeRecovery,
    recovery,
    parentErrorPartsAfterRecovery,
    hasFollowUpBefore,
    hasFollowUpAfter,
    errorVisibleBefore,
    errorVisibleAfter,
    screenshotPath,
    consoleErrorCount: consoleErrors.length,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main().catch(async (error) => {
  await cleanupSyntheticFixture();
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
