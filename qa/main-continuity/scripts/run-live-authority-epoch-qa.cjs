#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance for a reviewed Agent Builder authority change.
 *
 * A disposable clone of Main receives one turn, is updated through the real Agent API, and receives
 * a second turn in the same visible conversation. The stable-authority epoch and native worker must
 * rotate exactly once while both visible answers remain correct. All fixture state is then removed.
 */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const APP_SUPPORT = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium');
const GLASSHIVE_DB = path.join(
  APP_SUPPORT,
  'state',
  'runtime',
  'isolated',
  'glasshive',
  'runtime_phase1.db',
);
const helper = require('../../memory-continuity/scripts/run-live-browser-saved-memory-qa.cjs');

function hash(value, length = 12) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function sqlLiteral(value) {
  return `'${String(value || '').replaceAll("'", "''")}'`;
}

function sqliteRows(query) {
  const raw = execFileSync('sqlite3', ['-json', GLASSHIVE_DB, query], {
    encoding: 'utf8',
    timeout: 10000,
  }).trim();
  return raw ? JSON.parse(raw) : [];
}

async function waitFor(fn, message, timeoutMs = 240000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await fn();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(message);
}

function visibleText(message) {
  return [
    String(message?.text || ''),
    ...(Array.isArray(message?.content)
      ? message.content
          .filter((part) => part?.type === 'text')
          .map((part) => (typeof part.text === 'string' ? part.text : part.text?.value || ''))
      : []),
  ]
    .filter(Boolean)
    .join('\n');
}

async function main() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_authority_epoch_qa_forbidden_in_ci_or_production');
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== '1') {
    throw new Error('local_authority_epoch_qa_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT');
  }
  const mainAgentId = String(process.env.VIVENTIUM_QA_MAIN_AGENT_ID || '').trim();
  if (!mainAgentId) throw new Error('VIVENTIUM_QA_MAIN_AGENT_ID_is_required');

  const env = helper.loadRuntimeEnv();
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const mongo = new MongoClient(env.MONGO_URI);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const fixtureAgentId = `agent_qa_authority_epoch_${hash(stamp)}`;
  const firstExpected = `AUTHORITY_A_OK_${hash(stamp, 8).toUpperCase()}`;
  const secondExpected = `AUTHORITY_B_OK_${hash(`${stamp}-b`, 8).toUpperCase()}`;
  const firstPrompt = `Reply exactly ${firstExpected}`;
  const secondPrompt = `Reply exactly ${secondExpected}`;
  const fixtureObjectId = new ObjectId();
  const privateDir = path.join(
    APP_SUPPORT,
    'private-user-data',
    'qa',
    'main-continuity',
    `authority-epoch-${stamp}`,
  );
  fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });

  const result = {
    pass: false,
    firstAnswered: false,
    agentApiUpdated: false,
    secondAnswered: false,
    sameVisibleConversation: false,
    stableAuthorityChanged: false,
    contextEpochChanged: false,
    workerRotatedOnce: false,
    previousWorkerTerminated: false,
    refreshPreserved: false,
    cleanupVerified: false,
    consoleErrorCount: 0,
    error: '',
  };
  let db;
  let auth;
  let browser;
  let page;
  let fixtureOwner;
  const conversationIds = [];

  try {
    await mongo.connect();
    db = mongo.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    const mainAgent = await db.collection('agents').findOne({ id: mainAgentId });
    if (!mainAgent?._id || !mainAgent.author) throw new Error('configured_main_agent_not_found');
    fixtureOwner = await db.collection('users').findOne({ _id: mainAgent.author });
    if (!fixtureOwner?._id) throw new Error('configured_main_owner_not_found');
    const roles = await db
      .collection('accessroles')
      .find({ accessRoleId: { $in: ['agent_owner', 'remoteAgent_owner'] } })
      .toArray();
    const roleById = new Map(roles.map((role) => [role.accessRoleId, role]));
    if (!roleById.get('agent_owner') || !roleById.get('remoteAgent_owner')) {
      throw new Error('authority_epoch_qa_access_roles_missing');
    }

    const now = new Date();
    await db.collection('agents').insertOne({
      ...mainAgent,
      _id: fixtureObjectId,
      id: fixtureAgentId,
      name: 'Authority epoch QA',
      description: 'Disposable local Main-continuity QA Agent',
      instructions: 'Stable authority A. Follow the user request exactly.',
      background_cortices: [],
      createdAt: now,
      updatedAt: now,
    });
    await db.collection('aclentries').insertMany(
      [
        ['agent', roleById.get('agent_owner')],
        ['remoteAgent', roleById.get('remoteAgent_owner')],
      ].map(([resourceType, role]) => ({
        principalType: 'user',
        principalId: fixtureOwner._id,
        principalModel: 'User',
        resourceType,
        resourceId: fixtureObjectId,
        roleId: role._id,
        permBits: role.permBits,
        grantedBy: fixtureOwner._id,
        grantedAt: now,
        createdAt: now,
        updatedAt: now,
        __v: 0,
      })),
    );

    auth = await helper.createQaAuth({ env, db, user: fixtureOwner });
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await helper.attachAuth({
      context,
      args: { apiBase: 'http://localhost:3180', clientBase: 'http://localhost:3190' },
      auth,
    });
    page = await context.newPage();
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(helper.safeError(message.text()));
    });
    const agentUrl = `http://localhost:3190/c/new?agent_id=${encodeURIComponent(fixtureAgentId)}`;
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message/)).last();
    await input.waitFor({ state: 'visible', timeout: 60000 });

    const firstStartedAt = new Date();
    await input.fill(firstPrompt);
    await page.getByTestId('send-button').last().click();
    const firstUser = await waitFor(
      () =>
        db.collection('messages').findOne({
          user: String(fixtureOwner._id),
          isCreatedByUser: true,
          text: firstPrompt,
          createdAt: { $gte: firstStartedAt },
        }),
      'authority_epoch_first_user_missing',
    );
    conversationIds.push(firstUser.conversationId);
    const firstAssistant = await waitFor(
      async () => {
        const row = await db.collection('messages').findOne({
          user: String(fixtureOwner._id),
          conversationId: firstUser.conversationId,
          parentMessageId: firstUser.messageId,
          isCreatedByUser: false,
          unfinished: false,
        });
        return visibleText(row).includes(firstExpected) ? row : null;
      },
      'authority_epoch_first_answer_missing',
    );
    result.firstAnswered = visibleText(firstAssistant).includes(firstExpected);
    await page.getByText(firstExpected, { exact: true }).waitFor({ state: 'visible' });
    const firstSession = sqliteRows(
      `SELECT worker_id, context_manifest_json FROM provider_sessions WHERE conversation_id=${sqlLiteral(firstUser.conversationId)} AND agent_id=${sqlLiteral(fixtureAgentId)} LIMIT 1`,
    )[0];
    if (!firstSession) throw new Error('authority_epoch_first_session_missing');
    const firstManifest = JSON.parse(firstSession.context_manifest_json || '{}');

    const update = await context.request.patch(
      `http://localhost:3180/api/agents/${encodeURIComponent(fixtureAgentId)}`,
      {
        headers: { Authorization: `Bearer ${auth.accessToken}` },
        data: { instructions: 'Stable authority B. Follow the user request exactly.' },
      },
    );
    if (!update.ok()) throw new Error(`authority_epoch_agent_update_${update.status()}`);
    result.agentApiUpdated = true;

    const secondStartedAt = new Date();
    await input.fill(secondPrompt);
    await page.getByTestId('send-button').last().click();
    const secondUser = await waitFor(
      () =>
        db.collection('messages').findOne({
          user: String(fixtureOwner._id),
          conversationId: firstUser.conversationId,
          isCreatedByUser: true,
          text: secondPrompt,
          createdAt: { $gte: secondStartedAt },
        }),
      'authority_epoch_second_user_missing',
    );
    const secondAssistant = await waitFor(
      async () => {
        const row = await db.collection('messages').findOne({
          user: String(fixtureOwner._id),
          conversationId: firstUser.conversationId,
          parentMessageId: secondUser.messageId,
          isCreatedByUser: false,
          unfinished: false,
        });
        return visibleText(row).includes(secondExpected) ? row : null;
      },
      'authority_epoch_second_answer_missing',
    );
    result.secondAnswered = visibleText(secondAssistant).includes(secondExpected);
    result.sameVisibleConversation = secondUser.conversationId === firstUser.conversationId;
    await page.getByText(secondExpected, { exact: true }).waitFor({ state: 'visible' });
    const secondSession = sqliteRows(
      `SELECT worker_id, context_manifest_json FROM provider_sessions WHERE conversation_id=${sqlLiteral(firstUser.conversationId)} AND agent_id=${sqlLiteral(fixtureAgentId)} LIMIT 1`,
    )[0];
    if (!secondSession) throw new Error('authority_epoch_second_session_missing');
    const secondManifest = JSON.parse(secondSession.context_manifest_json || '{}');
    result.stableAuthorityChanged =
      Boolean(firstManifest.stable_authority_sha256) &&
      firstManifest.stable_authority_sha256 !== secondManifest.stable_authority_sha256;
    result.contextEpochChanged =
      Boolean(firstManifest.provider_context_epoch) &&
      firstManifest.provider_context_epoch !== secondManifest.provider_context_epoch;
    result.workerRotatedOnce = firstSession.worker_id !== secondSession.worker_id;
    result.previousWorkerTerminated =
      sqliteRows(
        `SELECT state FROM workers WHERE worker_id=${sqlLiteral(firstSession.worker_id)} LIMIT 1`,
      )[0]?.state === 'terminated';

    await page.screenshot({ path: path.join(privateDir, 'authority-changed.png'), fullPage: true });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page.getByText(secondExpected, { exact: true }).waitFor({ state: 'visible' });
    result.refreshPreserved = true;
    result.consoleErrorCount = consoleErrors.length;
    result.pass =
      result.firstAnswered &&
      result.agentApiUpdated &&
      result.secondAnswered &&
      result.sameVisibleConversation &&
      result.stableAuthorityChanged &&
      result.contextEpochChanged &&
      result.workerRotatedOnce &&
      result.previousWorkerTerminated &&
      result.refreshPreserved &&
      result.consoleErrorCount === 0;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    await browser?.close().catch(() => {});
    if (db) {
      const ids = [...new Set(conversationIds.filter(Boolean))];
      if (ids.length) {
        await Promise.all([
          db.collection('messages').deleteMany({ conversationId: { $in: ids } }),
          db.collection('conversations').deleteMany({ conversationId: { $in: ids } }),
        ]).catch(() => {});
        helper.cleanupGlassHiveConversations(ids);
      }
      await db.collection('agents').deleteMany({ id: fixtureAgentId }).catch(() => {});
      await db.collection('aclentries').deleteMany({ resourceId: fixtureObjectId }).catch(() => {});
      if (auth?.sessionId) {
        await db.collection('sessions').deleteMany({ _id: auth.sessionId }).catch(() => {});
      }
      const residue = await Promise.all([
        db.collection('agents').countDocuments({ id: fixtureAgentId }),
        ids.length ? db.collection('messages').countDocuments({ conversationId: { $in: ids } }) : 0,
        ids.length ? db.collection('conversations').countDocuments({ conversationId: { $in: ids } }) : 0,
      ]);
      result.cleanupVerified = residue.every((count) => count === 0);
    }
    await mongo.close().catch(() => {});
    result.pass = result.pass && result.cleanupVerified;
  }

  process.stdout.write(
    `${JSON.stringify({ ...result, error: result.error ? helper.safeError(result.error) : '' }, null, 2)}\n`,
  );
  process.exitCode = result.pass ? 0 : 1;
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${helper.safeError(error?.stack || error)}\n`);
    process.exitCode = 1;
  });
}
