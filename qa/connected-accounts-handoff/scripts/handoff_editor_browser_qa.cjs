#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'connected-accounts-handoff');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const MAIN_AGENT_ID = process.env.VIVENTIUM_MAIN_AGENT_ID || 'agent_viventium_main_95aeb3';
const CONNECTED_ACCOUNTS_AGENT_ID = 'agent_viventium_connected_accounts_95aeb3';

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

  const mainAgent = await db.collection('agents').findOne({ id: MAIN_AGENT_ID });
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
      viewport: { width: 2048, height: 1260 },
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
    await page.goto(`${clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    const refresh = await page.evaluate(async () => {
      const res = await fetch('/api/auth/refresh', { method: 'POST' });
      const body = await res.json().catch(() => ({}));
      const token = body.token || '';
      if (token) {
        localStorage.setItem('token', token);
        window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: token }));
      }
      return { status: res.status, ok: res.ok, hasToken: token.length > 10 };
    });

    await page.goto(`${clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
    await page.getByRole('button', { name: 'Agent Builder' }).click({ timeout: 20_000 });
    await page.waitForTimeout(1000);
    await page.getByRole('button', { name: 'Advanced' }).scrollIntoViewIfNeeded();
    await page.getByRole('button', { name: 'Advanced' }).click({ timeout: 20_000 });
    await page.waitForFunction(() => document.body.innerText.includes('Agent Handoffs'), {
      timeout: 30_000,
    });
    await page.waitForTimeout(2000);

    const panel = await page.evaluate(() => {
      const text = document.body?.innerText || '';
      const start = text.indexOf('Agent Handoffs');
      const end = text.indexOf('Agent Chain', start);
      const slice = start >= 0 ? text.slice(start, end > start ? end : start + 1600) : '';
      const visibleText = (node) => String(node?.innerText || node?.textContent || '').trim();
      const textElement = (exactText) =>
        Array.from(document.querySelectorAll('body *')).find((node) => {
          const rect = node.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0 && visibleText(node) === exactText;
        });
      const heading = textElement('Agent Handoffs');
      const nextHeading = textElement('Agent Chain (Mixture-of-Agents)');
      const headingRect = heading?.getBoundingClientRect();
      const nextHeadingRect = nextHeading?.getBoundingClientRect();
      const handoffComboboxTexts =
        headingRect && nextHeadingRect
          ? Array.from(document.querySelectorAll('button[role="combobox"]'))
              .filter((button) => {
                const rect = button.getBoundingClientRect();
                const centerY = rect.y + rect.height / 2;
                return (
                  rect.width > 0 &&
                  rect.height > 0 &&
                  centerY > headingRect.y &&
                  centerY < nextHeadingRect.y
                );
              })
              .map((button) => visibleText(button))
          : [];
      const selectedHandoffText =
        handoffComboboxTexts.find((value) => value && !/^Add\b/.test(value)) || '';
      return {
        slice,
        hasConnectedAccounts: slice.includes('Connected Accounts'),
        selectAgentCount: (slice.match(/Select agent/g) || []).length,
        handoffComboboxTexts,
        selectedHandoffText,
        selectedHandoffResolved: selectedHandoffText === 'Connected Accounts',
      };
    });

    const agentList = await page.evaluate(async (connectedAccountsAgentId) => {
      const token = localStorage.getItem('token') || '';
      const res = await fetch('/api/agents?requiredPermission=1', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const json = await res.json().catch(() => ({}));
      const data = Array.isArray(json.data) ? json.data : [];
      return {
        status: res.status,
        ok: res.ok,
        count: data.length,
        hasConnectedAccounts: data.some((agent) => agent?.id === connectedAccountsAgentId),
        firstAgentId: data[0]?.id || '',
      };
    }, CONNECTED_ACCOUNTS_AGENT_ID);

    const screenshotPath = path.join(
      OUTPUT_DIR,
      `handoff-editor-selector-${hash(userId)}.png`,
    );
    const headingBox = await page.getByText('Agent Handoffs').first().boundingBox();
    if (headingBox) {
      await page.screenshot({
        path: screenshotPath,
        clip: {
          x: Math.max(0, headingBox.x - 24),
          y: Math.max(0, headingBox.y - 20),
          width: 440,
          height: 190,
        },
      });
    }

    const result = {
      ok:
        refresh.ok &&
        refresh.hasToken &&
        panel.hasConnectedAccounts &&
        panel.selectedHandoffResolved &&
        agentList.hasConnectedAccounts,
      refresh,
      panel,
      agentList,
      screenshotPath: headingBox ? screenshotPath : null,
    };
    console.log(JSON.stringify(result, null, 2));
    if (!result.ok) {
      process.exitCode = 1;
    }
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (sessionId) {
      const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
      await client.db(dbName).collection('sessions').deleteOne({ _id: sessionId }).catch(() => {});
    }
    await client.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
