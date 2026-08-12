#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance for visible model-fallback disclosure.
 *
 * The script creates a disposable QA-owned Agent whose primary route is the configured QA
 * account's currently disconnected Anthropic lane and whose fallback is the healthy OpenAI lane.
 * It sends one ordinary turn through LibreChat, expands the visible disclosure, reloads the page,
 * checks persisted message content, and removes the Agent/session/conversation fixtures.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const APP_SUPPORT = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium');
const helper = require('./run-live-browser-saved-memory-qa.cjs');

function hashValue(value, length = 16) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function safeError(value) {
  return helper.safeError(value);
}

async function waitForCondition(fn, { timeoutMs = 180000, intervalMs = 750, error }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await fn();
    if (result) return result;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(error);
}

function contentText(content) {
  if (!Array.isArray(content)) return '';
  return content
    .filter((part) => part?.type === 'text')
    .map((part) => (typeof part.text === 'string' ? part.text : part.text?.value || ''))
    .filter(Boolean)
    .join('\n');
}

function fallbackPart(content) {
  return (Array.isArray(content) ? content : []).find(
    (part) =>
      part?.type === 'harness_activity' &&
      part?.harness_activity?.event === 'fallback-recovery',
  );
}

function writePublicReport(reportPath, result) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  const lines = [
    '<!-- qa-evidence-exempt: Generated focused browser artifact; full-view acceptance is owned by the universal continuity report. -->',
    '',
    `# Live browser fallback-disclosure QA — ${new Date().toISOString().slice(0, 10)}`,
    '',
    `- Status: ${result.pass ? 'PASS' : 'FAIL'}`,
    '- Surface: local LibreChat, non-admin QA account, disposable QA-owned Agent',
    `- Primary route failed before response: ${result.primaryUnavailable ? 'yes' : 'not proven'}`,
    `- Configured fallback produced visible assistant text: ${result.fallbackAnswered ? 'yes' : 'no'}`,
    `- Visible “Model fallback used” disclosure: ${result.visibleDisclosure ? 'yes' : 'no'}`,
    `- Expanded reason visible: ${result.expandedReasonVisible ? 'yes' : 'no'}`,
    `- Disclosure and answer persisted after reload: ${result.reloadPreserved ? 'yes' : 'no'}`,
    `- Persisted message contains structural fallback event: ${result.persistenceAgreed ? 'yes' : 'no'}`,
    `- Synthetic Agent/conversation/session cleanup: ${result.cleanupVerified ? 'verified' : 'failed'}`,
    `- Browser console errors: ${result.consoleErrorCount}`,
    `- Account hash: ${result.userHash || 'unavailable'}`,
    `- Conversation hash: ${result.conversationHash || 'unavailable'}`,
    '',
    'The fixture tests a provider failure boundary, not a prompt/entity rule. Raw prompts, responses, provider payloads, account identifiers, screenshots, tokens, local paths, and database identifiers remain outside the repository.',
  ];
  if (result.error) lines.push('', '## Error', '', `- ${safeError(result.error)}`);
  fs.writeFileSync(reportPath, `${lines.join('\n')}\n`, 'utf8');
}

async function main() {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_qa_jwt_forbidden_in_ci_or_production');
  }
  if (process.env.VIVENTIUM_QA_ALLOW_LOCAL_JWT !== '1') {
    throw new Error('local_qa_jwt_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT');
  }

  const env = helper.loadRuntimeEnv();
  const qaEmail = String(env.VIVENTIUM_QA_EMAIL || '').trim().toLowerCase();
  if (!env.MONGO_URI || !qaEmail) throw new Error('qa_runtime_prerequisites_missing');
  const { MongoClient, ObjectId } = require(path.join(
    LIBRECHAT_ROOT,
    'node_modules',
    'mongodb',
  ));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const client = new MongoClient(env.MONGO_URI);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const agentId = `agent_qa_fallback_${hashValue(stamp, 12)}`;
  const expectedAnswer = `fallback disclosure QA complete ${hashValue(stamp, 8)}`;
  const prompt = `Reply with exactly: ${expectedAnswer}`;
  const reportPath = path.join(
    REPO_ROOT,
    'qa',
    'memory-continuity',
    'reports',
    `${new Date().toISOString().slice(0, 10)}-live-browser-fallback-disclosure.md`,
  );
  const privateDir = path.join(
    APP_SUPPORT,
    'private-user-data',
    'qa',
    'memory-continuity',
    `fallback-disclosure-${stamp}`,
  );
  fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });

  const result = {
    pass: false,
    primaryUnavailable: false,
    fallbackAnswered: false,
    visibleDisclosure: false,
    expandedReasonVisible: false,
    reloadPreserved: false,
    persistenceAgreed: false,
    cleanupVerified: false,
    consoleErrorCount: 0,
    error: '',
  };
  let db;
  let user;
  let auth;
  const agentObjectId = new ObjectId();
  let browser;
  let context;
  let page;
  const conversationIds = [];

  try {
    await client.connect();
    db = client.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    user = await db.collection('users').findOne({ email: qaEmail });
    if (!user?._id || String(user.role || '').toUpperCase() === 'ADMIN') {
      throw new Error('configured_non_admin_qa_user_not_found');
    }
    result.userHash = hashValue(user._id, 12);

    const [anthropicTemplate, openAiTemplate] = await Promise.all([
      db.collection('agents').findOne(
        { provider: 'anthropic' },
        { projection: { model: 1, model_parameters: 1 } },
      ),
      db.collection('agents').findOne(
        { provider: 'openAI', model: /gpt-5\.6/ },
        { projection: { model: 1, model_parameters: 1 } },
      ),
    ]);
    if (!anthropicTemplate?.model || !openAiTemplate?.model) {
      throw new Error('fallback_qa_model_templates_missing');
    }

    const accessRoles = await db
      .collection('accessroles')
      .find({ accessRoleId: { $in: ['agent_owner', 'remoteAgent_owner'] } })
      .toArray();
    const roleById = new Map(accessRoles.map((role) => [role.accessRoleId, role]));
    if (!roleById.get('agent_owner') || !roleById.get('remoteAgent_owner')) {
      throw new Error('fallback_qa_access_roles_missing');
    }

    const now = new Date();
    await db.collection('agents').insertOne({
      _id: agentObjectId,
      id: agentId,
      author: user._id,
      authorName: 'QA',
      name: 'Fallback disclosure QA',
      description: 'Disposable local QA Agent',
      instructions: 'Answer the user directly and briefly.',
      provider: 'anthropic',
      model: anthropicTemplate.model,
      model_parameters: anthropicTemplate.model_parameters || { model: anthropicTemplate.model },
      fallback_llm_provider: 'openAI',
      fallback_llm_model: openAiTemplate.model,
      fallback_llm_model_parameters: {
        ...(openAiTemplate.model_parameters || {}),
        model: openAiTemplate.model,
      },
      tools: [],
      tool_options: {},
      tool_kwargs: {},
      mcpServerNames: [],
      agent_ids: [],
      edges: [],
      background_cortices: [],
      conversation_starters: [],
      hide_sequential_outputs: true,
      end_after_tools: true,
      is_promoted: false,
      createdAt: now,
      updatedAt: now,
    });
    await db.collection('aclentries').insertMany(
      [
        ['agent', roleById.get('agent_owner')],
        ['remoteAgent', roleById.get('remoteAgent_owner')],
      ].map(([resourceType, role]) => ({
        principalType: 'user',
        principalId: user._id,
        principalModel: 'User',
        resourceType,
        resourceId: agentObjectId,
        roleId: role._id,
        permBits: role.permBits,
        grantedBy: user._id,
        grantedAt: now,
        createdAt: now,
        updatedAt: now,
        __v: 0,
      })),
    );

    auth = await helper.createQaAuth({ env, db, user });
    browser = await chromium.launch({ channel: 'chrome', headless: process.env.VIVENTIUM_QA_HEADLESS !== '0' });
    context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await helper.attachAuth({
      context,
      args: { apiBase: 'http://localhost:3180', clientBase: 'http://localhost:3190' },
      auth,
    });
    page = await context.newPage();
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(safeError(message.text()));
    });
    const agentUrl = `http://localhost:3190/c/new?agent_id=${encodeURIComponent(agentId)}`;
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page.goto(agentUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);

    const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message/)).last();
    await input.waitFor({ state: 'visible', timeout: 60000 });
    const startedAt = new Date();
    await input.fill(prompt);
    await page.getByTestId('send-button').last().click({ timeout: 30000 });

    const userMessage = await waitForCondition(
      () =>
        db.collection('messages').findOne(
          {
            user: String(user._id),
            isCreatedByUser: true,
            text: prompt,
            createdAt: { $gte: startedAt },
          },
          { sort: { createdAt: -1 } },
        ),
      { error: 'fallback_qa_user_message_not_persisted' },
    );
    conversationIds.push(userMessage.conversationId);
    result.conversationHash = hashValue(userMessage.conversationId, 12);
    const assistantMessage = await waitForCondition(
      async () => {
        const rows = await db
          .collection('messages')
          .find({
            user: String(user._id),
            conversationId: userMessage.conversationId,
            isCreatedByUser: false,
            unfinished: { $ne: true },
            createdAt: { $gte: startedAt },
          })
          .sort({ createdAt: -1 })
          .limit(4)
          .toArray();
        return rows.find((row) => contentText(row.content).trim() || String(row.text || '').trim());
      },
      { error: 'fallback_qa_assistant_message_not_persisted' },
    );

    const persistedFallback = fallbackPart(assistantMessage.content);
    const answer = `${String(assistantMessage.text || '')}\n${contentText(assistantMessage.content)}`;
    result.primaryUnavailable = Boolean(persistedFallback);
    result.fallbackAnswered = answer.toLowerCase().includes(expectedAnswer.toLowerCase());
    result.persistenceAgreed = Boolean(
      persistedFallback?.harness_activity?.summary?.includes('primary model route was unavailable'),
    );

    await page.getByText('Model fallback used', { exact: true }).waitFor({
      state: 'visible',
      timeout: 60000,
    });
    result.visibleDisclosure = true;
    await page.getByText('Model fallback used', { exact: true }).click();
    await page.getByText(/primary model route was unavailable/i).waitFor({
      state: 'visible',
      timeout: 15000,
    });
    result.expandedReasonVisible = true;
    await page.screenshot({
      path: path.join(privateDir, 'expanded-fallback-disclosure.png'),
      fullPage: true,
    });

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    await page.getByText('Model fallback used', { exact: true }).waitFor({
      state: 'visible',
      timeout: 30000,
    });
    await page.getByText(expectedAnswer, { exact: true }).waitFor({
      state: 'visible',
      timeout: 30000,
    });
    result.reloadPreserved = true;
    result.consoleErrorCount = consoleErrors.length;
    result.pass =
      result.primaryUnavailable &&
      result.fallbackAnswered &&
      result.visibleDisclosure &&
      result.expandedReasonVisible &&
      result.reloadPreserved &&
      result.persistenceAgreed &&
      result.consoleErrorCount === 0;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    if (page) {
      await page.screenshot({ path: path.join(privateDir, 'final-state.png'), fullPage: true }).catch(() => {});
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
      await db.collection('agents').deleteMany({ id: agentId }).catch(() => {});
      await db.collection('aclentries').deleteMany({ resourceId: agentObjectId }).catch(() => {});
      if (auth?.sessionId) await db.collection('sessions').deleteMany({ _id: auth.sessionId }).catch(() => {});
      const [agentResidue, messageResidue, conversationResidue] = await Promise.all([
        db.collection('agents').countDocuments({ id: agentId }),
        ids.length ? db.collection('messages').countDocuments({ conversationId: { $in: ids } }) : 0,
        ids.length ? db.collection('conversations').countDocuments({ conversationId: { $in: ids } }) : 0,
      ]);
      result.cleanupVerified = agentResidue + messageResidue + conversationResidue === 0;
    }
    await client.close().catch(() => {});
    result.pass = result.pass && result.cleanupVerified;
    writePublicReport(reportPath, result);
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
