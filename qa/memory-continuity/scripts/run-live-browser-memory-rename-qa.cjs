#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance for rename into a deleted destination key.
 * Uses a disposable synthetic local user so tombstone generations cannot affect real user state.
 */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  apiJson,
  attachAuth,
  createQaAuth,
  getMemories,
  installAccessToken,
  loadRuntimeEnv,
  safeError,
} = require('./run-live-browser-saved-memory-qa.cjs');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const APP_SUPPORT = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium');

function requireLocalQaAuth() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_qa_jwt_forbidden_in_ci_or_production');
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== '1') {
    throw new Error('local_qa_jwt_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT');
  }
}

async function firstVisible(locator) {
  for (let index = 0; index < (await locator.count()); index += 1) {
    if (await locator.nth(index).isVisible()) return locator.nth(index);
  }
  return null;
}

async function openMemories(page) {
  const button = await firstVisible(page.getByRole('button', { name: 'Memories', exact: true }));
  if (!button) throw new Error('memories_button_not_visible');
  await button.click();
  const region = page.getByRole('region', { name: 'Memories', exact: true }).first();
  await region.waitFor({ state: 'visible', timeout: 30_000 });
  return region;
}

async function main() {
  requireLocalQaAuth();
  const env = loadRuntimeEnv();
  if (!env.MONGO_URI) throw new Error('missing_mongo_uri');
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const client = new MongoClient(env.MONGO_URI);
  const marker = crypto.randomBytes(6).toString('hex');
  const userId = new ObjectId();
  const email = `synthetic-memory-${marker}@example.invalid`;
  const args = {
    apiBase: process.env.VIVENTIUM_QA_API_BASE || 'http://127.0.0.1:3180',
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://127.0.0.1:3190',
  };
  const privateDir = path.join(
    APP_SUPPORT,
    'private-user-data',
    'qa',
    'memory-continuity',
    `rename-${new Date().toISOString().replace(/[:.]/g, '-')}`,
  );
  const reportPath = path.join(
    REPO_ROOT,
    'qa',
    'memory-continuity',
    'reports',
    '2026-08-09-live-browser-tombstone-rename.md',
  );
  let db;
  let browser;
  let auth;
  const result = {
    pass: false,
    tombstoneCreated: false,
    uiRenameSucceeded: false,
    monotonicRevision: false,
    reloadPreserved: false,
    cleanupVerified: false,
    consoleErrorCount: 0,
    error: '',
  };

  try {
    await client.connect();
    db = client.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    const now = new Date();
    const user = {
      _id: userId,
      email,
      username: `synthetic_memory_${marker}`,
      name: 'Synthetic Memory QA',
      provider: 'local',
      role: 'USER',
      emailVerified: true,
      personalization: { memories: true, conversation_recall: false },
      createdAt: now,
      updatedAt: now,
    };
    await db.collection('users').insertOne(user);
    auth = await createQaAuth({ env, db, user });
    const token = auth.accessToken;

    const sourceCreate = await apiJson({
      args,
      token,
      pathname: '/api/memories',
      method: 'POST',
      body: { key: 'working', value: `Synthetic source ${marker}` },
    });
    const destinationCreate = await apiJson({
      args,
      token,
      pathname: '/api/memories',
      method: 'POST',
      body: { key: 'drafts', value: `Synthetic destination ${marker}` },
    });
    if (!sourceCreate.ok || !destinationCreate.ok) throw new Error('memory_fixture_create_failed');
    const sourceRevision = Number(sourceCreate.body?.memory?.revision);
    const destinationRevision = Number(destinationCreate.body?.memory?.revision);
    const destinationDelete = await apiJson({
      args,
      token,
      pathname: `/api/memories/entries/drafts?revision=${destinationRevision}`,
      method: 'DELETE',
    });
    if (!destinationDelete.ok) throw new Error('destination_tombstone_create_failed');
    const deletedRevision = destinationRevision + 1;
    result.tombstoneCreated = true;

    fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await attachAuth({ context, args, auth });
    const page = await context.newPage();
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });
    await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await installAccessToken(page, token);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await installAccessToken(page, token);

    let region = await openMemories(page);
    const filter = region.getByLabel('Filter memories');
    await filter.fill('working');
    const sourceKey = region.getByText('working', { exact: true }).first();
    await sourceKey.waitFor({ state: 'visible', timeout: 30_000 });
    const sourceRow = sourceKey.locator('xpath=ancestor::*[@role="listitem"][1]');
    await sourceRow.waitFor({ state: 'visible', timeout: 30_000 });
    await sourceRow.getByRole('button', { name: 'Edit', exact: true }).click();
    const dialog = page.getByRole('dialog').last();
    await dialog.locator('#memory-key').fill('drafts');
    await dialog.locator('#memory-value').fill(`Synthetic renamed ${marker}`);
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();

    let renamed;
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      const rows = await getMemories({ args, token });
      renamed = rows.find((row) => row.key === 'drafts');
      if (renamed && !rows.some((row) => row.key === 'working')) break;
      await page.waitForTimeout(500);
    }
    result.uiRenameSucceeded =
      Boolean(renamed) && String(renamed.value || '').includes(marker);
    result.monotonicRevision =
      Number(renamed?.revision) > Math.max(sourceRevision, deletedRevision);

    await page.screenshot({ path: path.join(privateDir, 'renamed-visible.png'), fullPage: true });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await installAccessToken(page, token);
    region = await openMemories(page);
    await region.getByLabel('Filter memories').fill(marker);
    await region.getByText('drafts', { exact: true }).waitFor({ state: 'visible', timeout: 30_000 });
    result.reloadPreserved = (await region.innerText()).includes(marker);
    result.consoleErrorCount = consoleErrors.length;
    result.pass =
      result.tombstoneCreated &&
      result.uiRenameSucceeded &&
      result.monotonicRevision &&
      result.reloadPreserved &&
      result.consoleErrorCount === 0;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (db) {
      await Promise.all([
        db.collection('memoryentries').deleteMany({ userId }),
        db.collection('sessions').deleteMany({ user: userId }),
        db.collection('messages').deleteMany({ user: String(userId) }),
        db.collection('conversations').deleteMany({ user: String(userId) }),
        db.collection('users').deleteOne({ _id: userId }),
      ]).catch((error) => {
        result.error = `${result.error}\ncleanup:${error?.message || error}`.trim();
      });
      const [users, memories, sessions] = await Promise.all([
        db.collection('users').countDocuments({ _id: userId }),
        db.collection('memoryentries').countDocuments({ userId }),
        db.collection('sessions').countDocuments({ user: userId }),
      ]);
      result.cleanupVerified = users + memories + sessions === 0;
    }
    await client.close().catch(() => {});
    result.pass = result.pass && result.cleanupVerified;
    fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });
    fs.writeFileSync(
      path.join(privateDir, 'result.private.json'),
      `${JSON.stringify(result, null, 2)}\n`,
      { encoding: 'utf8', mode: 0o600 },
    );
    const failureClass = result.error
      ? String(result.error).split('\n')[0].replace(/[^A-Za-z0-9_:. -]/g, '').slice(0, 120)
      : '';
    const report = [
      '<!-- qa-evidence-exempt: Focused synthetic browser artifact; full-view acceptance is owned by the universal continuity report. -->',
      '',
      '# Live browser tombstone-rename QA — 2026-08-09',
      '',
      `- Status: ${result.pass ? 'PASS' : 'FAIL'}`,
      '- Surface: local LibreChat Memories panel in real Chrome, disposable synthetic user',
      `- Deleted destination tombstone created: ${result.tombstoneCreated ? 'yes' : 'no'}`,
      `- Rename through Edit dialog succeeded: ${result.uiRenameSucceeded ? 'yes' : 'no'}`,
      `- Revision remained monotonic across destination tombstone: ${result.monotonicRevision ? 'yes' : 'no'}`,
      `- Reload preserved renamed key/value: ${result.reloadPreserved ? 'yes' : 'no'}`,
      `- Browser console errors: ${result.consoleErrorCount}`,
      `- Disposable user/memory/session cleanup verified: ${result.cleanupVerified ? 'yes' : 'no'}`,
      ...(failureClass ? [`- Failure class: ${failureClass}`] : []),
      '',
      'Raw synthetic values, screenshots, ids, JWTs, local paths, and database rows remain outside the repository.',
      '',
    ].join('\n');
    fs.writeFileSync(reportPath, report, 'utf8');
  }

  process.stdout.write(`${JSON.stringify({ ...result, error: result.error ? safeError(result.error) : '' }, null, 2)}\n`);
  process.exitCode = result.pass ? 0 : 1;
}

main().catch((error) => {
  process.stderr.write(`${safeError(error?.stack || error)}\n`);
  process.exitCode = 1;
});
