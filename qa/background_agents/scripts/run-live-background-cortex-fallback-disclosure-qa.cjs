#!/usr/bin/env node
'use strict';

/**
 * Real-browser acceptance for background-cortex model-fallback disclosure.
 *
 * The harness creates a disposable non-admin-owned main Agent and one disposable cortex. The main
 * route and cortex fallback use the healthy OpenAI lane; the cortex primary uses a deliberately
 * unavailable synthetic provider lane. A normal browser turn must activate the cortex, receive a
 * visible fallback-produced result, expose the disclosure, survive reload, and leave no fixture.
 */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const APP_SUPPORT = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium');
const helper = require('../../memory-continuity/scripts/run-live-browser-saved-memory-qa.cjs');

function hashValue(value, length = 12) {
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

function cortexFallbackPart(content, cortexId) {
  return (Array.isArray(content) ? content : []).find(
    (part) =>
      part?.cortex_id === cortexId &&
      part?.status === 'complete' &&
      part?.fallback_used === true &&
      typeof part?.insight === 'string' &&
      part.insight.trim(),
  );
}

function writePublicReport(reportPath, result) {
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  const lines = [
    '<!-- qa-evidence-exempt: Generated focused browser artifact; full-view acceptance is owned by the universal continuity report. -->',
    '',
    `# Live background-cortex fallback disclosure QA — ${new Date().toISOString().slice(0, 10)}`,
    '',
    `- Status: ${result.pass ? 'PASS' : 'FAIL'}`,
    '- Surface: local LibreChat, non-admin QA account, disposable main Agent and cortex',
    `- Cortex activated from a normal browser turn: ${result.activationObserved ? 'yes' : 'no'}`,
    `- Disconnected primary recovered through configured fallback: ${result.fallbackRecovered ? 'yes' : 'no'}`,
    `- Fallback-produced insight persisted: ${result.insightPersisted ? 'yes' : 'no'}`,
    `- Visible cortex fallback row: ${result.visibleDisclosure ? 'yes' : 'no'}`,
    `- Expanded explanation and public failure class visible: ${result.expandedReasonVisible ? 'yes' : 'no'}`,
    `- Disclosure and cortex result survived reload: ${result.reloadPreserved ? 'yes' : 'no'}`,
    `- Persisted structural fields agreed with the UI: ${result.persistenceAgreed ? 'yes' : 'no'}`,
    `- Synthetic Agents/conversation/session cleanup: ${result.cleanupVerified ? 'verified' : 'failed'}`,
    `- Browser console errors: ${result.consoleErrorCount}`,
    `- Account hash: ${result.userHash || 'unavailable'}`,
    `- Conversation hash: ${result.conversationHash || 'unavailable'}`,
    '',
    'This fixture exercises a generic provider-failure boundary through the real background-cortex runtime. It does not branch on a user entity or production prompt phrase. Raw prompts, responses, provider payloads, identifiers, screenshots, tokens, local paths, and database records remain outside the repository.',
    '',
    'The deterministic synthetic lane proves the downstream generic `primary unavailable` recovery and disclosure contract; it is not a claim that this run reproduced a specific OAuth error variant. Separate connected-account QA covers terminal `invalid_grant` classification.',
  ];
  if (result.error) lines.push('', '## Error', '', `- ${safeError(result.error)}`);
  fs.writeFileSync(reportPath, `${lines.join('\n')}\n`, 'utf8');
}

function agentDocument({
  _id,
  id,
  user,
  name,
  description,
  instructions,
  provider,
  model,
  modelParameters,
  fallbackProvider = null,
  fallbackModel = null,
  fallbackModelParameters = null,
  backgroundCortices = [],
  now,
}) {
  return {
    _id,
    id,
    author: user._id,
    authorName: 'QA',
    name,
    description,
    instructions,
    provider,
    model,
    model_parameters: { ...(modelParameters || {}), model },
    fallback_llm_provider: fallbackProvider,
    fallback_llm_model: fallbackModel,
    fallback_llm_model_parameters: fallbackModel
      ? { ...(fallbackModelParameters || {}), model: fallbackModel }
      : {},
    tools: [],
    tool_options: {},
    tool_kwargs: {},
    mcpServerNames: [],
    agent_ids: [],
    edges: [],
    background_cortices: backgroundCortices,
    conversation_starters: [],
    hide_sequential_outputs: true,
    end_after_tools: false,
    is_promoted: false,
    createdAt: now,
    updatedAt: now,
  };
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

  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const client = new MongoClient(env.MONGO_URI);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const mainAgentId = `agent_qa_cortex_main_${hashValue(stamp)}`;
  const cortexAgentId = `agent_qa_cortex_fallback_${hashValue(`${stamp}:cortex`)}`;
  const cortexName = `Continuity QA ${hashValue(stamp, 6)}`;
  const expectedInsight = `background fallback QA complete ${hashValue(`${stamp}:insight`, 8)}`;
  const prompt =
    'Analyze the tradeoffs between two synthetic indexing plans. Use the background analysis available to you and give a concise recommendation.';
  const reportPath = path.join(
    REPO_ROOT,
    'qa',
    'background_agents',
    'reports',
    `${new Date().toISOString().slice(0, 10)}-background-cortex-fallback-disclosure.md`,
  );
  const privateDir = path.join(
    APP_SUPPORT,
    'private-user-data',
    'qa',
    'background-agents',
    `cortex-fallback-disclosure-${stamp}`,
  );
  fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });

  const result = {
    pass: false,
    activationObserved: false,
    fallbackRecovered: false,
    insightPersisted: false,
    visibleDisclosure: false,
    expandedReasonVisible: false,
    reloadPreserved: false,
    persistenceAgreed: false,
    cleanupVerified: false,
    consoleErrorCount: 0,
    error: '',
  };
  const mainObjectId = new ObjectId();
  const cortexObjectId = new ObjectId();
  const conversationIds = [];
  let db;
  let user;
  let auth;
  let browser;
  let page;

  try {
    await client.connect();
    db = client.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    user = await db.collection('users').findOne({ email: qaEmail });
    if (!user?._id || String(user.role || '').toUpperCase() === 'ADMIN') {
      throw new Error('configured_non_admin_qa_user_not_found');
    }
    result.userHash = hashValue(user._id);

    const openAiTemplate = await db.collection('agents').findOne(
      { provider: 'openAI', model: /gpt-5\.6/ },
      { projection: { model: 1, model_parameters: 1 } },
    );
    if (!openAiTemplate?.model) {
      throw new Error('background_fallback_qa_model_templates_missing');
    }

    const accessRoles = await db
      .collection('accessroles')
      .find({ accessRoleId: { $in: ['agent_owner', 'remoteAgent_owner'] } })
      .toArray();
    const roleById = new Map(accessRoles.map((role) => [role.accessRoleId, role]));
    if (!roleById.get('agent_owner') || !roleById.get('remoteAgent_owner')) {
      throw new Error('background_fallback_qa_access_roles_missing');
    }

    const now = new Date();
    const cortex = agentDocument({
      _id: cortexObjectId,
      id: cortexAgentId,
      user,
      name: cortexName,
      description: 'Analyze tradeoffs and return a concise independent result.',
      instructions: `Return exactly this sentence as the complete result: ${expectedInsight}`,
      provider: 'qa-unavailable-provider',
      model: 'qa-unavailable-model',
      modelParameters: {},
      fallbackProvider: 'openAI',
      fallbackModel: openAiTemplate.model,
      fallbackModelParameters: openAiTemplate.model_parameters,
      now,
    });
    const mainAgent = agentDocument({
      _id: mainObjectId,
      id: mainAgentId,
      user,
      name: 'Background fallback disclosure QA',
      description: 'Disposable local QA main Agent',
      instructions: 'Answer the user directly and briefly. Allow configured background analysis to run.',
      provider: 'openAI',
      model: openAiTemplate.model,
      modelParameters: openAiTemplate.model_parameters,
      backgroundCortices: [
        {
          agent_id: cortexAgentId,
          activation: {
            enabled: true,
            provider: 'groq',
            model: 'qwen/qwen3.6-27b',
            prompt: { promptRef: 'cortex.background_analysis.activation' },
            confidence_threshold: 0.1,
            cooldown_ms: 0,
            max_history: 4,
          },
        },
      ],
      now,
    });
    await db.collection('agents').insertMany([cortex, mainAgent]);
    await db.collection('aclentries').insertMany(
      [mainObjectId, cortexObjectId].flatMap((resourceId) =>
        [
          ['agent', roleById.get('agent_owner')],
          ['remoteAgent', roleById.get('remoteAgent_owner')],
        ].map(([resourceType, role]) => ({
          principalType: 'user',
          principalId: user._id,
          principalModel: 'User',
          resourceType,
          resourceId,
          roleId: role._id,
          permBits: role.permBits,
          grantedBy: user._id,
          grantedAt: now,
          createdAt: now,
          updatedAt: now,
          __v: 0,
        })),
      ),
    );

    auth = await helper.createQaAuth({ env, db, user });
    browser = await chromium.launch({
      channel: 'chrome',
      headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
    });
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
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

    const agentUrl = `http://localhost:3190/c/new?agent_id=${encodeURIComponent(mainAgentId)}`;
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
      { error: 'background_fallback_qa_user_message_not_persisted' },
    );
    conversationIds.push(userMessage.conversationId);
    result.conversationHash = hashValue(userMessage.conversationId);

    const observed = await waitForCondition(
      async () => {
        const rows = await db
          .collection('messages')
          .find({
            user: String(user._id),
            conversationId: userMessage.conversationId,
            isCreatedByUser: false,
            createdAt: { $gte: startedAt },
          })
          .sort({ createdAt: -1 })
          .limit(6)
          .toArray();
        for (const row of rows) {
          const part = cortexFallbackPart(row.content, cortexAgentId);
          if (part) return { row, part };
        }
        return null;
      },
      { error: 'background_fallback_qa_completion_not_persisted' },
    );
    result.activationObserved = true;
    result.fallbackRecovered = observed.part.fallback_used === true;
    result.insightPersisted = observed.part.insight.trim().includes(expectedInsight);
    result.persistenceAgreed =
      result.fallbackRecovered &&
      typeof observed.part.fallback_reason_class === 'string' &&
      observed.part.fallback_reason_class.length > 0;

    const disclosureRow = page.getByText(`${cortexName} · model fallback used`, { exact: true });
    await disclosureRow.waitFor({ state: 'visible', timeout: 90000 });
    result.visibleDisclosure = true;
    await disclosureRow.click();
    await page.getByText('Model fallback used', { exact: true }).waitFor({
      state: 'visible',
      timeout: 15000,
    });
    await page.getByText(/configured primary model route was unavailable/i).waitFor({
      state: 'visible',
      timeout: 15000,
    });
    await page.getByText(/Reason:/).waitFor({ state: 'visible', timeout: 15000 });
    result.expandedReasonVisible = true;
    await page.screenshot({
      path: path.join(privateDir, 'expanded-background-fallback.png'),
      fullPage: true,
    });

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    await helper.installAccessToken(page, auth.accessToken);
    const reloadedDisclosureRow = page.getByText(`${cortexName} · model fallback used`, {
      exact: true,
    });
    await reloadedDisclosureRow.waitFor({
      state: 'visible',
      timeout: 30000,
    });
    await reloadedDisclosureRow.click();
    await page.getByText(expectedInsight, { exact: true }).waitFor({
      state: 'visible',
      timeout: 30000,
    });
    result.reloadPreserved = true;
    result.consoleErrorCount = consoleErrors.length;
    result.pass =
      result.activationObserved &&
      result.fallbackRecovered &&
      result.insightPersisted &&
      result.visibleDisclosure &&
      result.expandedReasonVisible &&
      result.reloadPreserved &&
      result.persistenceAgreed &&
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
      await db
        .collection('agents')
        .deleteMany({ id: { $in: [mainAgentId, cortexAgentId] } })
        .catch(() => {});
      await db
        .collection('aclentries')
        .deleteMany({ resourceId: { $in: [mainObjectId, cortexObjectId] } })
        .catch(() => {});
      if (auth?.sessionId) {
        await db.collection('sessions').deleteMany({ _id: auth.sessionId }).catch(() => {});
      }
      const [agentResidue, messageResidue, conversationResidue] = await Promise.all([
        db.collection('agents').countDocuments({ id: { $in: [mainAgentId, cortexAgentId] } }),
        ids.length ? db.collection('messages').countDocuments({ conversationId: { $in: ids } }) : 0,
        ids.length
          ? db.collection('conversations').countDocuments({ conversationId: { $in: ids } })
          : 0,
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
