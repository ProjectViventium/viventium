#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'modern-playground-voice');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';

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
  const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
  const db = client.db(dbName);
  const user = await db.collection('users').findOne({ email: qaEmail });
  if (!user?._id) {
    throw new Error('QA user not found');
  }

  const userId = user._id.toString();
  const sessionId = new ObjectId();
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
  const userMessageId = randomId();
  const assistantMessageId = randomId();
  const userObjectId = new ObjectId();
  const assistantObjectId = new ObjectId();
  const conversationObjectId = new ObjectId();
  const visibleText =
    'Recovered QA answer: the useful assistant text stays visible without a stale overload banner.';

  await db.collection('messages').insertMany([
    {
      _id: userObjectId,
      user: userId,
      messageId: userMessageId,
      conversationId,
      parentMessageId: '00000000-0000-0000-0000-000000000000',
      isCreatedByUser: true,
      sender: 'User',
      text: 'Synthetic recovered provider-error QA fixture',
      endpoint: 'agents',
      model: null,
      tokenCount: 8,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: now,
      updatedAt: now,
      metadata: { viventium: { qaSynthetic: true, qaCase: 'MPV-011' } },
    },
    {
      _id: assistantObjectId,
      user: userId,
      messageId: assistantMessageId,
      conversationId,
      parentMessageId: userMessageId,
      isCreatedByUser: false,
      sender: 'Viventium',
      text: visibleText,
      endpoint: 'agents',
      model: 'gpt-5.4',
      tokenCount: 20,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: new Date(now.getTime() + 1),
      updatedAt: new Date(now.getTime() + 1),
      metadata: {
        viventium: {
          qaSynthetic: true,
          qaCase: 'MPV-011',
          type: 'cortex_followup',
          promotedToEmptyParent: true,
          forceVisibleFollowUp: true,
        },
      },
      content: [
        {
          type: 'cortex_insight',
          agent_name: 'QA Recovery',
          content: 'Synthetic supporting cortex insight.',
        },
        { type: 'text', text: visibleText },
        {
          type: 'error',
          error: 'The model provider is temporarily overloaded. Please try again shortly.',
          error_class: 'provider_temporarily_unavailable',
        },
      ],
    },
  ]);

  await db.collection('conversations').insertOne({
    _id: conversationObjectId,
    user: userId,
    conversationId,
    title: 'Recovered Provider Error QA',
    endpoint: 'agents',
    endpointType: 'agents',
    agent_id: 'agent_viventium_main_95aeb3',
    model: 'gpt-5.4',
    messages: [userObjectId, assistantObjectId],
    files: [],
    tags: [],
    resendFiles: true,
    isArchived: false,
    expiredAt: null,
    createdAt: now,
    updatedAt: new Date(now.getTime() + 1),
    _meiliIndex: true,
  });

  const dbFixtureErrorPartsBeforeBrowser = await db.collection('messages').countDocuments({
    messageId: assistantMessageId,
    content: { $elemMatch: { type: 'error' } },
  });

  const launchOptions = { headless: true };
  let browser;
  try {
    browser = await chromium.launch({ ...launchOptions, channel: 'chrome' });
  } catch {
    browser = await chromium.launch(launchOptions);
  }
  const clientBase = process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190';
  const apiBase = process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180';
  const context = await browser.newContext({
    baseURL: clientBase,
    viewport: { width: 1440, height: 1100 },
  });
  const cookieExpires = Math.floor(Date.now() / 1000) + 7200;
  await context.addCookies([
    {
      name: 'refreshToken',
      value: refreshToken,
      url: clientBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: cookieExpires,
    },
    {
      name: 'token_provider',
      value: 'librechat',
      url: clientBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: cookieExpires,
    },
    {
      name: 'refreshToken',
      value: refreshToken,
      url: apiBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: cookieExpires,
    },
    {
      name: 'token_provider',
      value: 'librechat',
      url: apiBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: cookieExpires,
    },
  ]);

  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text().slice(0, 300));
    }
  });

  await page.goto(`${clientBase}/c/${conversationId}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
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
  await page.goto(`${clientBase}/c/${conversationId}`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  await page.waitForTimeout(1500);

  const beforeRefreshText = await page.locator('body').innerText({ timeout: 20_000 });
  const screenshotPath = path.join(
    OUTPUT_DIR,
    'provider-overload-cleanup-post-correction-2026-05-21.png',
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  await page.waitForTimeout(1000);
  const afterRefreshText = await page.locator('body').innerText({ timeout: 20_000 });
  await browser.close();

  const hasRecoveredTextBefore = beforeRefreshText.includes(visibleText);
  const hasRecoveredTextAfter = afterRefreshText.includes(visibleText);
  const errorVisibleBefore =
    beforeRefreshText.includes('Something went wrong') ||
    beforeRefreshText.includes('temporarily overloaded');
  const errorVisibleAfter =
    afterRefreshText.includes('Something went wrong') ||
    afterRefreshText.includes('temporarily overloaded');

  await db.collection('conversations').deleteOne({ conversationId });
  await db.collection('messages').deleteMany({ conversationId });
  await db.collection('sessions').deleteOne({ _id: sessionId });

  await client.close();

  const result = {
    ok:
      refresh.ok &&
      refresh.hasToken &&
      dbFixtureErrorPartsBeforeBrowser === 1 &&
      hasRecoveredTextBefore &&
      hasRecoveredTextAfter &&
      !errorVisibleBefore &&
      !errorVisibleAfter,
    refresh,
    dbFixtureErrorPartsBeforeBrowser,
    hasRecoveredTextBefore,
    hasRecoveredTextAfter,
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
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
