#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance for Viventium's GlassHive primary -> Agent Builder fallback boundary.
 *
 * The fixture clones the configured Main route for its owning local account, starts one synthetic
 * turn, and terminates only the clone's newly created primary worker. The normal LibreChat fallback
 * must then produce the exact answer, keep the frozen MainContext digest, disclose the recovery,
 * survive refresh, and leave no LibreChat Agent/chat/session fixture behind.
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

async function waitFor(fn, message, timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await fn();
    if (result) return result;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(message);
}

function fallbackPart(content) {
  return (Array.isArray(content) ? content : []).find(
    (part) =>
      part?.type === 'harness_activity' &&
      part?.harness_activity?.event === 'fallback-recovery',
  );
}

function visibleText(message) {
  const parts = (Array.isArray(message?.content) ? message.content : [])
    .filter((part) => part?.type === 'text')
    .map((part) => (typeof part.text === 'string' ? part.text : part.text?.value || ''));
  return [String(message?.text || ''), ...parts].filter(Boolean).join('\n');
}

async function main() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_main_fallback_qa_forbidden_in_ci_or_production');
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== '1') {
    throw new Error('local_main_fallback_qa_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT');
  }
  const mainAgentId = String(process.env.VIVENTIUM_QA_MAIN_AGENT_ID || '').trim();
  if (!mainAgentId) {
    throw new Error('VIVENTIUM_QA_MAIN_AGENT_ID is required');
  }

  const env = helper.loadRuntimeEnv();
  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const mongo = new MongoClient(env.MONGO_URI);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const fixtureAgentId = `agent_qa_main_fallback_${hash(stamp)}`;
  const expected = `MAIN_FALLBACK_OK_${hash(stamp, 8).toUpperCase()}`;
  const prompt = `Reply with exactly ${expected}`;
  const result = {
    pass: false,
    primaryWorkerTerminated: false,
    fallbackAnswered: false,
    disclosureVisible: false,
    refreshPreserved: false,
    snapshotParity: false,
    capabilityParity: false,
    cleanupVerified: false,
    consoleErrorCount: 0,
    accountHash: '',
    conversationHash: '',
    error: '',
  };
  const privateDir = path.join(
    APP_SUPPORT,
    'private-user-data',
    'qa',
    'main-continuity',
    `main-fallback-${stamp}`,
  );
  fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });

  let db;
  let auth;
  let browser;
  let page;
  let owner;
  let mainAgent;
  const fixtureObjectId = new ObjectId();
  const conversationIds = [];

  try {
    await mongo.connect();
    db = mongo.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    mainAgent = await db.collection('agents').findOne({ id: mainAgentId });
    if (!mainAgent?._id || !mainAgent?.author) throw new Error('configured_main_agent_not_found');
    if (
      mainAgent.provider !== 'glasshive-harness' ||
      mainAgent.fallback_llm_provider !== 'glasshive-harness' ||
      !String(mainAgent.fallback_llm_model || '').startsWith('claude-code:')
    ) {
      throw new Error('configured_main_route_is_not_glasshive_to_claude');
    }
    owner = await db.collection('users').findOne({ _id: mainAgent.author });
    if (!owner?._id) throw new Error('configured_main_owner_not_found');
    result.accountHash = hash(owner._id);

    const accessRoles = await db
      .collection('accessroles')
      .find({ accessRoleId: { $in: ['agent_owner', 'remoteAgent_owner'] } })
      .toArray();
    const roleById = new Map(accessRoles.map((role) => [role.accessRoleId, role]));
    if (!roleById.get('agent_owner') || !roleById.get('remoteAgent_owner')) {
      throw new Error('main_fallback_qa_access_roles_missing');
    }

    const now = new Date();
    const glasshiveOptions = { ...(mainAgent.glasshive_options || {}) };
    delete glasshiveOptions.fallback_model;
    delete glasshiveOptions.fallback_reasoning_effort;
    await db.collection('agents').insertOne({
      ...mainAgent,
      _id: fixtureObjectId,
      id: fixtureAgentId,
      name: 'Main fallback QA',
      description: 'Disposable local Main-continuity QA Agent',
      instructions: 'Follow the user request exactly. Do not add commentary.',
      glasshive_options: glasshiveOptions,
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
        principalId: owner._id,
        principalModel: 'User',
        resourceType,
        resourceId: fixtureObjectId,
        roleId: role._id,
        permBits: role.permBits,
        grantedBy: owner._id,
        grantedAt: now,
        createdAt: now,
        updatedAt: now,
        __v: 0,
      })),
    );

    auth = await helper.createQaAuth({ env, db, user: owner });
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    const consoleErrors = [];
    await helper.attachAuth({
      context,
      args: { apiBase: 'http://localhost:3180', clientBase: 'http://localhost:3190' },
      auth,
    });
    page = await context.newPage();
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
    const startedAt = new Date();
    await input.fill(prompt);
    await page.getByTestId('send-button').last().click({ timeout: 30000 });
    const userMessage = await waitFor(
      () =>
        db.collection('messages').findOne(
          {
            user: String(owner._id),
            isCreatedByUser: true,
            text: prompt,
            createdAt: { $gte: startedAt },
          },
          { sort: { createdAt: -1 } },
        ),
      'main_fallback_qa_user_message_not_persisted',
    );
    conversationIds.push(userMessage.conversationId);
    result.conversationHash = hash(userMessage.conversationId);

    const primarySession = await waitFor(() => {
      const rows = sqliteRows(
        `SELECT session_id, worker_id FROM provider_sessions WHERE conversation_id=${sqlLiteral(userMessage.conversationId)} AND agent_id=${sqlLiteral(fixtureAgentId)} ORDER BY created_at DESC LIMIT 1`,
      );
      return rows[0] || null;
    }, 'main_fallback_qa_primary_session_not_created');
    const terminated = await fetch(
      `http://127.0.0.1:8766/v1/workers/${encodeURIComponent(primarySession.worker_id)}/terminate`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${env.WPR_API_TOKEN}`,
          'X-Viventium-User-Id': String(owner._id),
          'X-Viventium-Tenant-Id': 'local',
        },
      },
    );
    if (!terminated.ok) throw new Error(`main_fallback_qa_worker_terminate_${terminated.status}`);
    result.primaryWorkerTerminated = true;

    const assistantMessage = await waitFor(async () => {
      const rows = await db
        .collection('messages')
        .find({
          user: String(owner._id),
          conversationId: userMessage.conversationId,
          isCreatedByUser: false,
          unfinished: { $ne: true },
          createdAt: { $gte: startedAt },
        })
        .sort({ createdAt: -1 })
        .limit(4)
        .toArray();
      return rows.find((row) => visibleText(row).includes(expected));
    }, 'main_fallback_qa_fallback_answer_not_persisted');
    result.fallbackAnswered = visibleText(assistantMessage).includes(expected);
    result.disclosureVisible = Boolean(fallbackPart(assistantMessage.content));

    await page.getByText(expected, { exact: true }).waitFor({ state: 'visible', timeout: 60000 });
    await page.getByText('Model fallback used', { exact: true }).waitFor({
      state: 'visible',
      timeout: 60000,
    });
    await page.screenshot({ path: path.join(privateDir, 'fallback-visible.png'), fullPage: true });
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page.getByText(expected, { exact: true }).waitFor({ state: 'visible', timeout: 30000 });
    await page.getByText('Model fallback used', { exact: true }).waitFor({
      state: 'visible',
      timeout: 30000,
    });
    result.refreshPreserved = true;

    const attempts = sqliteRows(
      `SELECT r.state, r.replay_decision_json, s.model_id FROM provider_requests r JOIN provider_sessions s ON s.session_id=r.session_id WHERE s.conversation_id=${sqlLiteral(userMessage.conversationId)} AND s.agent_id=${sqlLiteral(fixtureAgentId)} ORDER BY r.created_at`,
    ).map((row) => ({
      state: row.state,
      model: row.model_id,
      replay: JSON.parse(row.replay_decision_json || '{}'),
    }));
    const digests = new Set(
      attempts.map((attempt) => attempt.replay.main_context_snapshot_sha256).filter(Boolean),
    );
    result.snapshotParity = attempts.length >= 2 && digests.size === 1;
    const ceilings = new Set(
      attempts
        .map((attempt) => JSON.stringify(attempt.replay.main_context_delta_v1 || {}))
        .filter((value) => value !== '{}'),
    );
    result.capabilityParity = attempts.length >= 2 && ceilings.size === 1;
    result.consoleErrorCount = consoleErrors.length;
    result.pass =
      result.primaryWorkerTerminated &&
      result.fallbackAnswered &&
      result.disclosureVisible &&
      result.refreshPreserved &&
      result.snapshotParity &&
      result.capabilityParity &&
      result.consoleErrorCount === 0;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    if (page) {
      await page
        .screenshot({ path: path.join(privateDir, 'final-state.png'), fullPage: true })
        .catch(() => {});
    }
    if (browser) await browser.close().catch(() => {});
    if (db) {
      const ids = [...new Set(conversationIds.filter(Boolean))];
      if (ids.length > 0) {
        await Promise.all([
          db.collection('messages').deleteMany({ conversationId: { $in: ids } }),
          db.collection('conversations').deleteMany({ conversationId: { $in: ids } }),
        ]).catch(() => {});
      }
      await db.collection('agents').deleteMany({ id: fixtureAgentId }).catch(() => {});
      await db.collection('aclentries').deleteMany({ resourceId: fixtureObjectId }).catch(() => {});
      if (auth?.sessionId) {
        await db.collection('sessions').deleteMany({ _id: auth.sessionId }).catch(() => {});
      }
      const residue = await Promise.all([
        db.collection('agents').countDocuments({ id: fixtureAgentId }),
        ids.length ? db.collection('messages').countDocuments({ conversationId: { $in: ids } }) : 0,
        ids.length
          ? db.collection('conversations').countDocuments({ conversationId: { $in: ids } })
          : 0,
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
