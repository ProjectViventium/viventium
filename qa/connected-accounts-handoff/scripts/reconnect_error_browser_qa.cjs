#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'connected-accounts-handoff');
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

function qaMongoUri(env) {
  if (env.MONGO_URI) {
    return env.MONGO_URI;
  }
  if (env.VIVENTIUM_QA_MONGO_URI) {
    return env.VIVENTIUM_QA_MONGO_URI;
  }
  throw new Error('Missing MONGO_URI or VIVENTIUM_QA_MONGO_URI for local QA');
}

function randomId() {
  return crypto.randomUUID();
}

function hash(value) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, 12);
}

async function resolveQaUser(db, ObjectId) {
  const qaEmail = process.env.VIVENTIUM_QA_USER_EMAIL;
  if (qaEmail) {
    const user = await db.collection('users').findOne({ email: qaEmail });
    if (!user?._id) {
      throw new Error('Configured QA user not found');
    }
    return user;
  }

  const mainAgent = await db
    .collection('agents')
    .findOne({ id: process.env.VIVENTIUM_MAIN_AGENT_ID || 'agent_viventium_main_95aeb3' });
  const authorId = mainAgent?.author ? String(mainAgent.author) : '';
  if (!authorId || !ObjectId.isValid(authorId)) {
    throw new Error('Missing VIVENTIUM_QA_USER_EMAIL and main-agent author fallback');
  }
  const user = await db.collection('users').findOne({ _id: new ObjectId(authorId) });
  if (!user?._id) {
    throw new Error('Main-agent author user not found');
  }
  return user;
}

async function main() {
  requireLocalQaAuth();

  const env = { ...loadRuntimeEnv(), ...process.env };
  const mongoUri = qaMongoUri(env);
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
  let browser;
  let sessionId;
  let conversationId;
  try {
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
    const db = client.db(dbName);
    const user = await resolveQaUser(db, ObjectId);
    const userId = user._id.toString();

    sessionId = new ObjectId();
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
    conversationId = randomId();
    const userMessageId = randomId();
    const assistantMessageId = randomId();
    const userObjectId = new ObjectId();
    const assistantObjectId = new ObjectId();
    const conversationObjectId = new ObjectId();
    const actionableText =
      'The primary model provider was rate-limited, and the configured fallback model could not start because OpenAI connected account needs reconnect in Settings > Account > Connected Accounts. Reconnect OpenAI, then try again.';

    await db.collection('messages').insertMany([
      {
        _id: userObjectId,
        user: userId,
        messageId: userMessageId,
        conversationId,
        parentMessageId: '00000000-0000-0000-0000-000000000000',
        isCreatedByUser: true,
        sender: 'User',
        text: 'Synthetic reconnect error rendering QA fixture',
        endpoint: 'agents',
        model: null,
        tokenCount: 8,
        error: false,
        unfinished: false,
        expiredAt: null,
        createdAt: now,
        updatedAt: now,
        metadata: { viventium: { qaSynthetic: true, qaCase: 'CA-HANDOFF-013' } },
      },
      {
        _id: assistantObjectId,
        user: userId,
        messageId: assistantMessageId,
        conversationId,
        parentMessageId: userMessageId,
        isCreatedByUser: false,
        sender: 'Viventium',
        text: '',
        endpoint: 'agents',
        model: 'gpt-5.4',
        tokenCount: 20,
        error: false,
        unfinished: false,
        expiredAt: null,
        createdAt: new Date(now.getTime() + 1),
        updatedAt: new Date(now.getTime() + 1),
        metadata: { viventium: { qaSynthetic: true, qaCase: 'CA-HANDOFF-013' } },
        content: [
          {
            type: 'error',
            error: actionableText,
            error_class: 'provider_connected_account_reconnect_required',
          },
        ],
      },
    ]);

    await db.collection('conversations').insertOne({
      _id: conversationObjectId,
      user: userId,
      conversationId,
      title: 'Reconnect Error Rendering QA',
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

    const launchOptions = { headless: true };
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
    await page.goto(`${clientBase}/c/${conversationId}`, {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
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
    await page.waitForFunction(
      (expectedText) => document.body?.innerText?.includes(expectedText),
      actionableText,
      { timeout: 30_000 },
    );

    const beforeRefreshText = await page.locator('body').innerText({ timeout: 20_000 });
    const screenshotPath = path.join(
      OUTPUT_DIR,
      `reconnect-error-rendering-${hash(conversationId)}.png`,
    );
    await page.getByText(actionableText).screenshot({ path: screenshotPath });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.waitForFunction(
      (expectedText) => document.body?.innerText?.includes(expectedText),
      actionableText,
      { timeout: 30_000 },
    );
    const afterRefreshText = await page.locator('body').innerText({ timeout: 20_000 });

    const hasActionableBefore = beforeRefreshText.includes(actionableText);
    const hasActionableAfter = afterRefreshText.includes(actionableText);
    const genericWrapperBefore = beforeRefreshText.includes('Something went wrong');
    const genericWrapperAfter = afterRefreshText.includes('Something went wrong');
    const staleRateLimitBefore = beforeRefreshText.includes(
      'The model provider rate-limited this request. Please try again shortly.',
    );
    const staleRateLimitAfter = afterRefreshText.includes(
      'The model provider rate-limited this request. Please try again shortly.',
    );

    const result = {
      ok:
        refresh.ok &&
        refresh.hasToken &&
        hasActionableBefore &&
        hasActionableAfter &&
        !genericWrapperBefore &&
        !genericWrapperAfter &&
        !staleRateLimitBefore &&
        !staleRateLimitAfter,
      conversationHash: hash(conversationId),
      refresh,
      hasActionableBefore,
      hasActionableAfter,
      genericWrapperBefore,
      genericWrapperAfter,
      staleRateLimitBefore,
      staleRateLimitAfter,
      screenshotPath,
    };
    console.log(JSON.stringify(result, null, 2));
    if (!result.ok) {
      process.exitCode = 1;
    }
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
    const db = client.db(dbName);
    if (conversationId) {
      await db.collection('conversations').deleteOne({ conversationId }).catch(() => {});
      await db.collection('messages').deleteMany({ conversationId }).catch(() => {});
    }
    await db
      .collection('messages')
      .deleteMany({
        'metadata.viventium.qaCase': 'CA-HANDOFF-013',
        'metadata.viventium.qaSynthetic': true,
      })
      .catch(() => {});
    if (sessionId) {
      await db.collection('sessions').deleteOne({ _id: sessionId }).catch(() => {});
    }
    await client.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
