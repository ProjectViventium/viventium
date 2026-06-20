#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * Browser QA for CA-HANDOFF-015.
 *
 * Public-safe by design:
 * - Requires explicit local JWT opt-in.
 * - Uses synthetic non-mutating prompts only.
 * - Writes screenshots under output/, not under qa/.
 * - Prints counts, hashes, and pass/fail state. No private emails, raw chats, tokens, or provider
 *   responses are written to the public QA report.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'playwright', 'connected-accounts-handoff');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const MAIN_AGENT_ID = process.env.VIVENTIUM_MAIN_AGENT_ID || 'agent_viventium_main_95aeb3';
const CONNECTED_ACCOUNTS_AGENT_ID =
  process.env.VIVENTIUM_CONNECTED_ACCOUNTS_AGENT_ID || 'agent_viventium_connected_accounts_95aeb3';
const INCIDENT_CONVERSATION_ID = process.env.VIVENTIUM_QA_INCIDENT_CONVERSATION_ID || '';

const REQUIRED_WRITE_TOOLS = [
  'send-mail_mcp_ms-365',
  'create-draft-email_mcp_ms-365',
  'create-calendar-event_mcp_ms-365',
  'send_gmail_message_mcp_google_workspace',
  'draft_gmail_message_mcp_google_workspace',
  'create_event_mcp_google_workspace',
];

const FORBIDDEN_CONNECTED_ACCOUNTS_TOOLS = [
  'upload-file-content_mcp_ms-365',
  'delete-onedrive-file_mcp_ms-365',
  'create_drive_file_mcp_google_workspace',
  'move-mail-message_mcp_ms-365',
  'delete-mail-message_mcp_ms-365',
  'delete-calendar-event_mcp_ms-365',
  'delete-specific-calendar-event_mcp_ms-365',
  'delete_event_mcp_google_workspace',
];

const FORBIDDEN_MUTATION_TOOL_CALLS = [
  'send-mail_mcp_ms-365',
  'create-draft-email_mcp_ms-365',
  'create-calendar-event_mcp_ms-365',
  'update-calendar-event_mcp_ms-365',
  'delete-calendar-event_mcp_ms-365',
  'send_gmail_message_mcp_google_workspace',
  'draft_gmail_message_mcp_google_workspace',
  'create_event_mcp_google_workspace',
  'modify_event_mcp_google_workspace',
  'delete_event_mcp_google_workspace',
];

const STALE_READ_ONLY_PATTERNS = [
  /only has read-only/i,
  /this path is read-only/i,
  /read-only connected-account access/i,
  /read-only access to (?:my|your) calendar/i,
  /calendar\/email\/file write requests are out of scope/i,
  /can't send (?:it|them) from here/i,
  /cannot send (?:it|them) from here/i,
];

const ACTIONABLE_PATTERNS = [
  /confirm/i,
  /recipient/i,
  /content/i,
  /body/i,
  /subject/i,
  /send/i,
  /draft/i,
  /outlook|ms365|microsoft/i,
];

function parseArgs(argv) {
  const startedAt = new Date();
  const marker = `ca-confirmed-write-${hash(startedAt.toISOString(), 10)}`;
  const args = {
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190',
    apiBase: process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180',
    headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 180000),
    startedAt,
    marker,
    prompt:
      process.env.VIVENTIUM_QA_PROMPT ||
      [
        'Synthetic QA only.',
        'Do not send, draft, create, update, delete, move, archive, mark, invite, or modify anything.',
        'I may need to send an Outlook/MS365 email after I explicitly approve it.',
        'Before doing anything, what details and confirmation would you need from me?',
        `QA marker: ${marker}.`,
      ].join(' '),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === '--client-base') {
      args.clientBase = next;
      i += 1;
    } else if (arg === '--api-base') {
      args.apiBase = next;
      i += 1;
    } else if (arg === '--headed') {
      args.headless = false;
    } else if (arg === '--headless') {
      args.headless = true;
    } else if (arg === '--timeout-ms') {
      args.timeoutMs = Number(next);
      i += 1;
    } else if (arg === '--prompt') {
      args.prompt = next;
      i += 1;
    }
  }

  return args;
}

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

function hash(value, length = 12) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function randomId() {
  return crypto.randomUUID();
}

function sanitizeSnippet(value) {
  return String(value || '')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email>')
    .replace(/https?:\/\/[^\s)]+/gi, '<url>')
    .replace(/\/Users\/[^\s)]+/g, '<path>')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer <redacted>')
    .replace(/sk-[A-Za-z0-9._-]+/g, 'sk-<redacted>')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 260);
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

function extractText(message) {
  const text = typeof message?.text === 'string' ? message.text : '';
  const partText = Array.isArray(message?.content)
    ? message.content
        .map((part) => {
          if (!part || part.type !== 'text') {
            return '';
          }
          if (typeof part.text === 'string') {
            return part.text;
          }
          if (typeof part.text?.value === 'string') {
            return part.text.value;
          }
          return '';
        })
        .filter(Boolean)
        .join('\n')
    : '';
  return [text, partText].filter(Boolean).join('\n').trim();
}

function contentContainsToolCall(message, toolName) {
  const parts = Array.isArray(message?.content) ? message.content : [];
  return parts.some((part) => {
    const candidate =
      part?.toolCall?.name ||
      part?.tool_call?.function?.name ||
      part?.function?.name ||
      part?.name ||
      '';
    if (candidate === toolName) {
      return true;
    }
    if (part?.type === 'tool_call' || part?.type === 'function') {
      return JSON.stringify(part).includes(toolName);
    }
    return false;
  });
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

async function installAccessToken(page) {
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
  await page.waitForTimeout(250);
  return refresh;
}

async function submitPrompt(page, prompt) {
  const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message Viventium$/)).last();
  await input.waitFor({ state: 'visible', timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId('send-button').last().click({ timeout: 30000 });
}

async function waitForUserMessage({ db, userId, conversationId, prompt, startedAt, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const message = await db.collection('messages').findOne(
      {
        user: userId,
        conversationId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: startedAt },
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    if (message?.messageId) {
      return message;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('missing_browser_user_message');
}

async function waitForAssistantMessage({ db, userId, conversationId, userMessageId, startedAt, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const messages = await db
      .collection('messages')
      .find({
        user: userId,
        conversationId,
        isCreatedByUser: false,
        createdAt: { $gte: startedAt },
      })
      .sort({ createdAt: -1, _id: -1 })
      .limit(12)
      .toArray();
    const direct = messages.find((message) => message.parentMessageId === userMessageId);
    const candidate = direct || messages[0];
    const text = extractText(candidate);
    const isPlaceholder = /^Generation in progress\.?$/i.test(text.trim());
    if (candidate && candidate.error) {
      return candidate;
    }
    if (candidate && !isPlaceholder && candidate.unfinished !== true && text.length > 35) {
      return candidate;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('missing_browser_assistant_message');
}

async function createSyntheticConnectedAccountsConversation({ db, ObjectId, user, connectedAgent, args }) {
  const now = new Date();
  const conversationId = randomId();
  const userMessageId = randomId();
  const assistantMessageId = randomId();
  const userObjectId = new ObjectId();
  const assistantObjectId = new ObjectId();
  const conversationObjectId = new ObjectId();
  const userId = user._id.toString();
  const model = connectedAgent?.model || 'gpt-5.4';

  await db.collection('messages').insertMany([
    {
      _id: userObjectId,
      user: userId,
      messageId: userMessageId,
      conversationId,
      parentMessageId: '00000000-0000-0000-0000-000000000000',
      isCreatedByUser: true,
      sender: 'User',
      text: `Synthetic Connected Accounts confirmed-write QA seed. Marker: ${args.marker}.`,
      endpoint: 'agents',
      model: null,
      tokenCount: 12,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: now,
      updatedAt: now,
      metadata: { viventium: { qaSynthetic: true, qaCase: 'CA-HANDOFF-015' } },
    },
    {
      _id: assistantObjectId,
      user: userId,
      messageId: assistantMessageId,
      conversationId,
      parentMessageId: userMessageId,
      isCreatedByUser: false,
      sender: 'Connected Accounts',
      text: 'Synthetic QA seed ready.',
      endpoint: 'agents',
      model,
      tokenCount: 6,
      error: false,
      unfinished: false,
      expiredAt: null,
      createdAt: new Date(now.getTime() + 1),
      updatedAt: new Date(now.getTime() + 1),
      metadata: { viventium: { qaSynthetic: true, qaCase: 'CA-HANDOFF-015' } },
    },
  ]);

  await db.collection('conversations').insertOne({
    _id: conversationObjectId,
    user: userId,
    conversationId,
    title: 'Connected Accounts Confirmed Write QA',
    endpoint: 'agents',
    endpointType: 'agents',
    agent_id: CONNECTED_ACCOUNTS_AGENT_ID,
    model,
    messages: [userObjectId, assistantObjectId],
    files: [],
    tags: [],
    resendFiles: true,
    isArchived: false,
    expiredAt: null,
    createdAt: now,
    updatedAt: new Date(now.getTime() + 1),
    _meiliIndex: true,
    metadata: { viventium: { qaSynthetic: true, qaCase: 'CA-HANDOFF-015' } },
  });

  return { conversationId, seedMessageIds: [userMessageId, assistantMessageId] };
}

async function main() {
  requireLocalQaAuth();

  const args = parseArgs(process.argv.slice(2));
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

    const connectedAgent = await db.collection('agents').findOne({ id: CONNECTED_ACCOUNTS_AGENT_ID });
    const mainAgent = await db.collection('agents').findOne({ id: MAIN_AGENT_ID });
    const connectedTools = connectedAgent?.tools || [];
    const requiredWritePresent = REQUIRED_WRITE_TOOLS.filter((tool) => connectedTools.includes(tool));
    const forbiddenBroadPresent = FORBIDDEN_CONNECTED_ACCOUNTS_TOOLS.filter((tool) =>
      connectedTools.includes(tool),
    );
    const handoffEdge = (mainAgent?.edges || []).find((edge) => {
      const target = edge?.target || edge?.to || edge?.agent_id || edge?.targetAgent || '';
      return target === CONNECTED_ACCOUNTS_AGENT_ID;
    });

    const incidentConversation = INCIDENT_CONVERSATION_ID
      ? await db.collection('conversations').findOne({
          conversationId: INCIDENT_CONVERSATION_ID,
          user: userId,
        })
      : null;
    const incidentMessages =
      INCIDENT_CONVERSATION_ID && incidentConversation
        ? await db
            .collection('messages')
            .find({ conversationId: INCIDENT_CONVERSATION_ID, user: userId })
            .sort({ createdAt: 1, _id: 1 })
            .toArray()
        : [];
    const incidentTexts = incidentMessages.map(extractText).filter(Boolean);
    const incidentReadOnlyRefusalCount = incidentTexts.filter((text) =>
      STALE_READ_ONLY_PATTERNS.some((pattern) => pattern.test(text)),
    ).length;

    const synthetic = await createSyntheticConnectedAccountsConversation({
      db,
      ObjectId,
      user,
      connectedAgent,
      args,
    });

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

    const launchOptions = { headless: args.headless };
    try {
      browser = await chromium.launch({ ...launchOptions, channel: 'chrome' });
    } catch {
      browser = await chromium.launch(launchOptions);
    }

    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1600, height: 1100 },
    });
    const cookieExpires = Math.floor(Date.now() / 1000) + 7200;
    await context.addCookies([
      {
        name: 'refreshToken',
        value: refreshToken,
        url: args.clientBase,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
      {
        name: 'token_provider',
        value: 'librechat',
        url: args.clientBase,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
      {
        name: 'refreshToken',
        value: refreshToken,
        url: args.apiBase,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
      {
        name: 'token_provider',
        value: 'librechat',
        url: args.apiBase,
        httpOnly: true,
        sameSite: 'Strict',
        expires: cookieExpires,
      },
    ]);

    const page = await context.newPage();

    const incidentRefresh = INCIDENT_CONVERSATION_ID
      ? await installAccessToken(page)
      : { ok: true, skipped: true, reason: 'VIVENTIUM_QA_INCIDENT_CONVERSATION_ID not set' };
    if (INCIDENT_CONVERSATION_ID) {
      await page.goto(`${args.clientBase}/c/${INCIDENT_CONVERSATION_ID}`, {
        waitUntil: 'domcontentloaded',
        timeout: 60_000,
      });
      await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
    }
    const incidentVisibleText = INCIDENT_CONVERSATION_ID
      ? await page.locator('body').innerText({ timeout: 20_000 })
      : '';
    const incidentVisibleRefusal = STALE_READ_ONLY_PATTERNS.some((pattern) =>
      pattern.test(incidentVisibleText),
    );

    await page.goto(`${args.clientBase}/c/${synthetic.conversationId}`, {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    const syntheticRefresh = await installAccessToken(page);
    await page.goto(`${args.clientBase}/c/${synthetic.conversationId}`, {
      waitUntil: 'domcontentloaded',
      timeout: 60_000,
    });
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});

    const beforePrompt = new Date();
    await submitPrompt(page, args.prompt);
    const userMessage = await waitForUserMessage({
      db,
      userId,
      conversationId: synthetic.conversationId,
      prompt: args.prompt,
      startedAt: beforePrompt,
      timeoutMs: args.timeoutMs,
    });
    const assistantMessage = await waitForAssistantMessage({
      db,
      userId,
      conversationId: synthetic.conversationId,
      userMessageId: userMessage.messageId,
      startedAt: beforePrompt,
      timeoutMs: args.timeoutMs,
    });

    await page.waitForTimeout(1500);
    const syntheticVisibleText = await page.locator('body').innerText({ timeout: 20_000 });
    const screenshotPath = path.join(
      OUTPUT_DIR,
      `confirmed-write-capability-${hash(userId)}-${hash(synthetic.conversationId, 8)}.png`,
    );
    await page.screenshot({ path: screenshotPath, fullPage: false });

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
    const reloadedVisibleText = await page.locator('body').innerText({ timeout: 20_000 });

    const postMessages = await db
      .collection('messages')
      .find({
        user: userId,
        conversationId: synthetic.conversationId,
        createdAt: { $gte: beforePrompt },
      })
      .sort({ createdAt: 1, _id: 1 })
      .toArray();
    const assistantText = extractText(assistantMessage);
    const staleReadOnlyInAssistant = STALE_READ_ONLY_PATTERNS.some((pattern) =>
      pattern.test(assistantText),
    );
    const staleReadOnlyVisible = STALE_READ_ONLY_PATTERNS.some((pattern) =>
      pattern.test(syntheticVisibleText),
    );
    const actionable = ACTIONABLE_PATTERNS.filter((pattern) => pattern.test(assistantText)).length >= 4;
    const forbiddenMutationCalls = FORBIDDEN_MUTATION_TOOL_CALLS.filter((toolName) =>
      postMessages.some((message) => contentContainsToolCall(message, toolName)),
    );
    const visibleAfterReload = reloadedVisibleText.includes(args.marker);
    const selectedConnectedAccounts =
      /Connected Accounts/.test(syntheticVisibleText) || /Connected Accounts/.test(reloadedVisibleText);
    const generationErrorVisible = /Something went wrong|Connection error|rate-limited/i.test(
      syntheticVisibleText,
    );

    const result = {
      ok:
        incidentRefresh.ok &&
        syntheticRefresh.ok &&
        (!INCIDENT_CONVERSATION_ID ||
          (incidentConversation?.agent_id === CONNECTED_ACCOUNTS_AGENT_ID &&
            incidentReadOnlyRefusalCount > 0 &&
            incidentVisibleRefusal)) &&
        requiredWritePresent.length === REQUIRED_WRITE_TOOLS.length &&
        forbiddenBroadPresent.length === 0 &&
        Boolean(handoffEdge) &&
        selectedConnectedAccounts &&
        !staleReadOnlyInAssistant &&
        !staleReadOnlyVisible &&
        actionable &&
        forbiddenMutationCalls.length === 0 &&
        visibleAfterReload &&
        !generationErrorVisible,
      auth: {
        incidentRefresh,
        syntheticRefresh,
      },
      liveConfig: {
        connectedAgentFound: Boolean(connectedAgent),
        connectedToolCount: connectedTools.length,
        requiredWritePresentCount: requiredWritePresent.length,
        requiredWriteMissing: REQUIRED_WRITE_TOOLS.filter((tool) => !connectedTools.includes(tool)),
        forbiddenBroadPresent,
        handoffEdgeFound: Boolean(handoffEdge),
        handoffEdgeHasConfirmedWritePrompt: /confirmed|write tool|read-only/i.test(
          String(handoffEdge?.prompt || ''),
        ),
      },
      incident: {
        skipped: !INCIDENT_CONVERSATION_ID,
        conversationFound: Boolean(incidentConversation),
        activeAgentIsConnectedAccounts:
          incidentConversation?.agent_id === CONNECTED_ACCOUNTS_AGENT_ID,
        messageCount: incidentMessages.length,
        readOnlyRefusalCount: incidentReadOnlyRefusalCount,
        visibleHistoricalRefusal: incidentVisibleRefusal,
      },
      browser: {
        syntheticConversationHash: hash(synthetic.conversationId),
        selectedConnectedAccounts,
        staleReadOnlyInAssistant,
        staleReadOnlyVisible,
        actionable,
        forbiddenMutationCalls,
        generationErrorVisible,
        visibleAfterReload,
        assistantTextHash: hash(assistantText, 16),
        assistantTextSnippet: sanitizeSnippet(assistantText),
        screenshotPath,
      },
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
