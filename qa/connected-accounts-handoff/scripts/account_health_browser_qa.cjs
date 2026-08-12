#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
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
    const source = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
    for (const line of source.split(/\r?\n/)) {
      const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (match) {
        env[match[1]] = match[2].replace(/^"(.*)"$/, '$1');
      }
    }
  }
  return env;
}

function requireLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_qa_jwt_forbidden_in_ci_or_production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`local_qa_jwt_requires_${LOCAL_JWT_ALLOW_ENV}`);
  }
}

function parseExpectedStatus(name) {
  const value = process.env[name]?.trim().toLowerCase();
  if (value !== 'connected' && value !== 'disconnected') {
    throw new Error(`${name}_must_be_connected_or_disconnected`);
  }
  return value[0].toUpperCase() + value.slice(1);
}

async function getVisibleStatus(page, provider) {
  const card = page.getByRole('region', { name: `${provider} account`, exact: true });
  await card.waitFor({ state: 'visible', timeout: 30_000 });
  const text = (await card.innerText()).replace(/\s+/g, ' ').trim();
  const status = /\bDisconnected\b/.test(text)
    ? 'Disconnected'
    : /\bConnected\b/.test(text)
      ? 'Connected'
      : 'Unknown';
  return { status, hasConnectAction: /\bConnect\b|\bReconnect\b/.test(text) };
}

async function openConnectedAccounts(page, clientBase) {
  await page.goto(`${clientBase}/c/new?setup=accounts`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
  const openAiCard = page.getByRole('region', { name: 'OpenAI account', exact: true });
  if ((await openAiCard.count()) === 0) {
    await page.getByTestId('nav-user').click({ timeout: 30_000 });
    await page.getByText(/Connected Accounts/i, { exact: true }).last().click({ timeout: 30_000 });
  }
  await openAiCard.waitFor({ state: 'visible', timeout: 30_000 });
}

async function main() {
  requireLocalQaAuth();
  const expected = {
    OpenAI: parseExpectedStatus('VIVENTIUM_EXPECT_OPENAI_STATUS'),
    Anthropic: parseExpectedStatus('VIVENTIUM_EXPECT_ANTHROPIC_STATUS'),
  };
  const env = { ...loadRuntimeEnv(), ...process.env };
  const mongoUri = env.MONGO_URI || env.VIVENTIUM_QA_MONGO_URI;
  const qaEmail = String(env.VIVENTIUM_QA_EMAIL || env.VIVENTIUM_QA_USER_EMAIL || '')
    .trim()
    .toLowerCase();
  if (!mongoUri || !qaEmail || !env.JWT_REFRESH_SECRET) {
    throw new Error('missing_local_qa_auth_prerequisites');
  }

  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const client = new MongoClient(mongoUri);
  let browser;
  let sessionId;
  try {
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
    const db = client.db(dbName);
    const user = await db.collection('users').findOne({ email: qaEmail });
    if (!user?._id) {
      throw new Error('configured_qa_user_not_found');
    }

    sessionId = new ObjectId();
    const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const refreshToken = jwt.sign(
      { id: user._id.toString(), sessionId: sessionId.toString() },
      env.JWT_REFRESH_SECRET,
      { expiresIn: 7200 },
    );
    await db.collection('sessions').insertOne({
      _id: sessionId,
      user: user._id,
      expiration,
      refreshTokenHash: crypto.createHash('sha256').update(refreshToken).digest('hex'),
    });

    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const clientBase = env.VIVENTIUM_QA_CLIENT_BASE || 'http://127.0.0.1:3190';
    const apiBase = env.VIVENTIUM_QA_API_BASE || 'http://127.0.0.1:3180';
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const expires = Math.floor(expiration.getTime() / 1000);
    const authCookies = [clientBase, apiBase].flatMap((url) => [
      { name: 'refreshToken', value: refreshToken, url, httpOnly: true, sameSite: 'Strict', expires },
      { name: 'token_provider', value: 'librechat', url, httpOnly: true, sameSite: 'Strict', expires },
    ]);
    await context.addCookies(authCookies);
    const page = await context.newPage();
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });

    await page.goto(`${clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    const refresh = await page.evaluate(async () => {
      const response = await fetch('/api/auth/refresh', { method: 'POST' });
      const body = await response.json().catch(() => ({}));
      if (body.token) localStorage.setItem('token', body.token);
      return { status: response.status, hasToken: Boolean(body.token) };
    });
    if (refresh.status !== 200 || !refresh.hasToken) {
      throw new Error(`auth_refresh_failed:${refresh.status}`);
    }

    const readState = async () => {
      await openConnectedAccounts(page, clientBase);
      const ui = {
        OpenAI: await getVisibleStatus(page, 'OpenAI'),
        Anthropic: await getVisibleStatus(page, 'Anthropic'),
      };
      const api = await page.evaluate(async () => {
        const token = localStorage.getItem('token') || '';
        const read = async (endpoint) => {
          const response = await fetch(`/api/keys?name=${encodeURIComponent(endpoint)}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const body = await response.json().catch(() => ({}));
          return { status: response.status, connected: Boolean(body.expiresAt) };
        };
        return { OpenAI: await read('openAI'), Anthropic: await read('anthropic') };
      });
      return { ui, api };
    };

    const initial = await readState();
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await openConnectedAccounts(page, clientBase);
    const reloaded = {
      ui: {
        OpenAI: await getVisibleStatus(page, 'OpenAI'),
        Anthropic: await getVisibleStatus(page, 'Anthropic'),
      },
    };

    const assertions = Object.entries(expected).flatMap(([provider, status]) => [
      initial.ui[provider].status === status,
      initial.api[provider].status === 200,
      initial.api[provider].connected === (status === 'Connected'),
      reloaded.ui[provider].status === status,
    ]);
    const result = {
      pass: assertions.every(Boolean),
      expected,
      initial,
      reloaded,
      authRefreshStatus: refresh.status,
      consoleErrorCount: consoleErrors.length,
      qaUserHash: crypto.createHash('sha256').update(user._id.toString()).digest('hex').slice(0, 12),
    };
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (!result.pass) process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    if (sessionId) {
      const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
      await client.db(dbName).collection('sessions').deleteOne({ _id: sessionId });
    }
    await client.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
