#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * Browser QA for ACT-21: activation detection must judge the latest user message.
 *
 * Public-safe by design:
 * - Requires explicit local JWT opt-in.
 * - Uses synthetic prompts only.
 * - Writes only hashes, counts, and pass/fail state. No screenshots, raw replies, conversation IDs,
 *   emails, credentials, or private URLs are written to the public repo.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const REQUIRED_SETUP_CARD_NAMES = ['Red Team', 'Confirmation Bias'];
const TEST_PROMPT = 'say "TEST_OK"';

function hashValue(value, length = 16) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function parseArgs(argv) {
  const startedAt = new Date().toISOString();
  const marker = `latest-user-${hashValue(startedAt)}`;
  const args = {
    startedAt,
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190',
    apiBase: process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180',
    qaEmail: process.env.VIVENTIUM_QA_EMAIL || 'qa@example.com',
    out:
      process.env.VIVENTIUM_QA_REPORT_PATH ||
      path.join(REPO_ROOT, 'qa', 'background_agents', 'latest_user_activation_browser_qa_2026-05-11.md'),
    headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 120000),
    settleMs: Number(process.env.VIVENTIUM_QA_SETTLE_MS || 15000),
    setupPrompt:
      process.env.VIVENTIUM_QA_SETUP_PROMPT ||
      [
        'For this synthetic QA turn only, red-team a product launch and check whether I am confirmation-biasing myself.',
        `Synthetic QA marker: ${marker}.`,
      ].join(' '),
    testPrompt: process.env.VIVENTIUM_QA_TEST_PROMPT || TEST_PROMPT,
    testExpectedText: process.env.VIVENTIUM_QA_TEST_EXPECTED_TEXT || 'TEST_OK',
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
    } else if (arg === '--qa-email') {
      args.qaEmail = next;
      i += 1;
    } else if (arg === '--out') {
      args.out = next;
      i += 1;
    } else if (arg === '--headed') {
      args.headless = false;
    } else if (arg === '--headless') {
      args.headless = true;
    } else if (arg === '--setup-prompt') {
      args.setupPrompt = next;
      i += 1;
    } else if (arg === '--test-prompt') {
      args.testPrompt = next;
      i += 1;
    } else if (arg === '--test-expected-text') {
      args.testExpectedText = next;
      i += 1;
    }
  }

  return args;
}

function sanitizePublicError(value) {
  return String(value || 'qa_failed')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email>')
    .replace(/https?:\/\/[^\s)]+/gi, '<url>')
    .replace(/\/Users\/[^\s)]+/g, '<path>')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer <redacted>')
    .replace(/sk-[A-Za-z0-9._-]+/g, 'sk-<redacted>')
    .replace(/\s+/g, ' ')
    .slice(0, 220);
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const env = {};
  for (const line of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) {
      continue;
    }
    const index = trimmed.indexOf('=');
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

function localEnv() {
  return {
    ...parseEnvFile(path.join(LIBRECHAT_ROOT, '.env')),
    ...parseEnvFile(path.join(REPO_ROOT, '.env')),
    ...process.env,
  };
}

async function createQaAuth({ args, env }) {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('Local QA JWT auth is forbidden in CI or production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1`);
  }
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error('Missing local QA auth prerequisites');
  }

  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const client = new MongoClient(env.MONGO_URI);
  await client.connect();
  const dbName = new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium';
  const db = client.db(dbName);
  const user = await db.collection('users').findOne({ email: args.qaEmail });
  if (!user?._id) {
    await client.close();
    throw new Error('QA user not found');
  }

  const userId = user._id.toString();
  const accessToken = jwt.sign(
    {
      id: userId,
      username: user.username,
      provider: user.provider,
      email: user.email,
    },
    env.JWT_SECRET,
    { expiresIn: '2h' },
  );
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: userId, sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
  await db.collection('sessions').insertOne({
    _id: sessionId,
    user: user._id,
    expiration,
    refreshTokenHash: crypto.createHash('sha256').update(refreshToken).digest('hex'),
  });

  return {
    close: () => client.close(),
    db,
    userId,
    accessToken,
    refreshToken,
  };
}

async function attachAuthCookies({ context, args, qaAuth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  const cookies = [args.apiBase, args.clientBase].flatMap((url) => [
    {
      name: 'refreshToken',
      value: qaAuth.refreshToken,
      url,
      httpOnly: true,
      sameSite: 'Strict',
      expires,
    },
    {
      name: 'token_provider',
      value: 'librechat',
      url,
      httpOnly: true,
      sameSite: 'Strict',
      expires,
    },
  ]);
  await context.addCookies(cookies);
}

async function installAccessToken(page, localAccessToken = '') {
  const refresh = await page.evaluate(async () => {
    const response = await fetch('/api/auth/refresh', { method: 'POST' });
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    return {
      ok: response.ok,
      status: response.status,
      hasToken: Boolean(payload && typeof payload.token === 'string' && payload.token.length > 0),
      token: payload && typeof payload.token === 'string' ? payload.token : '',
    };
  });
  if (!refresh.ok || !refresh.hasToken) {
    if (!localAccessToken) {
      throw new Error(`auth_refresh_failed_status_${refresh.status}`);
    }
    await page.evaluate((token) => {
      window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: token }));
    }, localAccessToken);
    await page.waitForTimeout(250);
    return { mode: 'direct_access_token_fallback', refreshStatus: refresh.status };
  }
  await page.evaluate((token) => {
    window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: token }));
  }, refresh.token);
  await page.waitForTimeout(250);
  return { mode: 'refresh_cookie', refreshStatus: refresh.status };
}

async function submitPrompt(page, prompt) {
  const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message Viventium$/)).last();
  await input.waitFor({ state: 'visible', timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId('send-button').last().click({ timeout: 30000 });
}

async function visibleBodyText(page) {
  return page.locator('body').innerText({ timeout: 10000 });
}

async function readVisibleEnvironmentBlock(page) {
  if (!page) {
    return '';
  }
  const text = await visibleBodyText(page).catch(() => '');
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return '';
  }
  if (/connected account needs reconnect/i.test(normalized)) {
    return 'model_connected_account_reconnect_required';
  }
  if (/unable to login with the information provided/i.test(normalized)) {
    return 'login_rejected_by_runtime';
  }
  if (/something went wrong/i.test(normalized) && /processing the request/i.test(normalized)) {
    return `visible_generation_error:${sanitizePublicError(normalized)}`;
  }
  return '';
}

function throwEnvironmentBlock(reason) {
  const error = new Error(`environment_blocked:${reason}`);
  error.qaBlocked = true;
  throw error;
}

function exitCodeForResult(result) {
  if (result?.pass) {
    return 0;
  }
  return result?.environmentBlocked ? 2 : 1;
}

function extractConversationIdFromUrl(url) {
  try {
    const match = new URL(url).pathname.match(/^\/c\/([^/?#]+)$/);
    return match ? match[1] : '';
  } catch {
    return '';
  }
}

async function waitForConversationForPrompt({ qaAuth, prompt, startedAt, timeoutMs, page }) {
  const deadline = Date.now() + timeoutMs;
  const startedDate = new Date(startedAt);
  while (Date.now() < deadline) {
    const userMessage = await qaAuth.db.collection('messages').findOne(
      {
        user: qaAuth.userId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: startedDate },
      },
      { sort: { createdAt: -1, _id: -1 }, projection: { conversationId: 1 } },
    );
    if (userMessage?.conversationId) {
      return String(userMessage.conversationId);
    }
    const visibleBlock = await readVisibleEnvironmentBlock(page);
    if (visibleBlock) {
      throwEnvironmentBlock(visibleBlock);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('missing_current_qa_conversation_for_prompt');
}

async function waitForSetupCards(page, timeoutMs) {
  await page.waitForFunction(
    (requiredNames) => {
      const rowTexts = Array.from(document.querySelectorAll('.progress-text-wrapper button')).map(
        (button) => button.textContent || '',
      );
      return requiredNames.every((name) => rowTexts.some((rowText) => rowText.includes(name)));
    },
    REQUIRED_SETUP_CARD_NAMES,
    { timeout: timeoutMs },
  );
}

function extractTextFromContentPart(part) {
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
}

function extractVisibleAnswerTextFromMessage(message) {
  if (!message || typeof message !== 'object') {
    return '';
  }
  const text = typeof message.text === 'string' ? message.text : '';
  const partText = Array.isArray(message.content)
    ? message.content.map(extractTextFromContentPart).filter(Boolean).join('\n')
    : '';
  return [text, partText]
    .filter((part) => typeof part === 'string' && part.trim().length > 0)
    .join('\n')
    .trim();
}

function normalizeAnswerText(text) {
  return String(text || '').replace(/\s+/g, ' ').trim();
}

function isExactExpectedAnswer(text, expectedText) {
  const actual = normalizeAnswerText(text);
  const expected = normalizeAnswerText(expectedText);
  return actual === expected || actual === `"${expected}"`;
}

function isPlaceholderAnswerText(text) {
  const lines = String(text || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return false;
  }
  return lines.every((line) =>
    /^(generation in progress|generation interrupted before completion)\.?$/i.test(line),
  );
}

function cortexPartsFromMessage(message) {
  return Array.isArray(message?.content)
    ? message.content.filter((part) => part && String(part.type || '').startsWith('cortex_'))
    : [];
}

async function waitForUserMessage({ qaAuth, conversationId, prompt, startedAt, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  const startedDate = new Date(startedAt);
  while (Date.now() < deadline) {
    const message = await qaAuth.db.collection('messages').findOne(
      {
        user: qaAuth.userId,
        conversationId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: startedDate },
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    if (message?.messageId) {
      return message;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('missing_latest_user_message');
}

async function waitForAssistantParent({
  qaAuth,
  conversationId,
  userMessageId,
  timeoutMs,
  expectedText = '',
  requireExactText = false,
  rejectPhaseBPromotion = false,
}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const message = await qaAuth.db.collection('messages').findOne(
      {
        user: qaAuth.userId,
        conversationId,
        isCreatedByUser: false,
        parentMessageId: userMessageId,
      },
      { sort: { createdAt: 1, _id: 1 } },
    );
    const visibleText = extractVisibleAnswerTextFromMessage(message).trim();
    const promotedByPhaseB =
      message?.metadata?.viventium?.promotedToEmptyParent === true ||
      message?.metadata?.viventium?.type === 'cortex_followup';
    const expectedSatisfied =
      !expectedText ||
      (requireExactText
        ? isExactExpectedAnswer(visibleText, expectedText)
        : visibleText.toLowerCase().includes(String(expectedText).toLowerCase()));
    if (
      message &&
      visibleText.length > 0 &&
      !isPlaceholderAnswerText(visibleText) &&
      !(rejectPhaseBPromotion && promotedByPhaseB) &&
      expectedSatisfied
    ) {
      return message;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('missing_latest_assistant_parent');
}

async function readLatestTurnState({ qaAuth, conversationId, userMessageId, assistantMessageId }) {
  const parent = await qaAuth.db.collection('messages').findOne({
    user: qaAuth.userId,
    conversationId,
    isCreatedByUser: false,
    messageId: assistantMessageId,
  });
  const phaseBChildren = await qaAuth.db
    .collection('messages')
    .find({
      user: qaAuth.userId,
      conversationId,
      isCreatedByUser: false,
      parentMessageId: assistantMessageId,
    })
    .sort({ createdAt: 1, _id: 1 })
    .toArray();
  const directChildren = await qaAuth.db
    .collection('messages')
    .find({
      user: qaAuth.userId,
      conversationId,
      isCreatedByUser: false,
      parentMessageId: userMessageId,
    })
    .sort({ createdAt: 1, _id: 1 })
    .toArray();

  const scopedMessages = [parent, ...phaseBChildren].filter(Boolean);
  const allCortexParts = scopedMessages.flatMap(cortexPartsFromMessage);
  const parentText = extractVisibleAnswerTextFromMessage(parent);
  const childVisibleTextCount = phaseBChildren.filter(
    (message) => extractVisibleAnswerTextFromMessage(message).trim().length > 0,
  ).length;

  return {
    parentHash: hashValue(parent?.messageId || ''),
    parentTextLength: parentText.length,
    parentIncludesTestOk: /\bTEST_OK\b/.test(parentText),
    parentExactExpected: isExactExpectedAnswer(parentText, 'TEST_OK'),
    directAssistantCount: directChildren.length,
    phaseBChildCount: phaseBChildren.length,
    phaseBChildVisibleTextCount: childVisibleTextCount,
    scopedCortexPartCount: allCortexParts.length,
    scopedCortexNames: Array.from(
      new Set(
        allCortexParts
          .map((part) => String(part.cortex_name || part.cortexName || part.name || '').trim())
          .filter(Boolean),
      ),
    ).sort(),
  };
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const env = localEnv();
  let qaAuth;
  let browser;
  const result = {
    startedAt: args.startedAt,
    clientBaseHash: hashValue(args.clientBase),
    apiBaseHash: hashValue(args.apiBase),
    qaEmailHash: hashValue(args.qaEmail),
    setupPromptHash: hashValue(args.setupPrompt),
    testPromptHash: hashValue(args.testPrompt),
    conversationIdHash: '',
    setupCardsVisible: false,
    setupFollowUpReady: false,
    latestParentHash: '',
    latestParentTextLength: 0,
    latestParentIncludesTestOk: false,
    latestParentExactExpectedText: false,
    latestDirectAssistantCount: 0,
    latestPhaseBChildCount: 0,
    latestPhaseBChildVisibleTextCount: 0,
    latestScopedCortexPartCount: 0,
    latestScopedCortexNames: [],
    directAccessTokenFallbackUsed: false,
    environmentBlocked: false,
    environmentBlockReason: '',
    testOkVisibleBeforeReload: false,
    testOkVisibleAfterReload: false,
    pass: false,
    error: null,
  };

  try {
    qaAuth = await createQaAuth({ args, env });
    const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
    browser = await chromium.launch({ channel: 'chrome', headless: args.headless });
    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1280, height: 960 },
    });
    await attachAuthCookies({ context, args, qaAuth });
    const page = await context.newPage();
    await page.goto(args.clientBase, { waitUntil: 'domcontentloaded', timeout: 60000 });
    let authState = await installAccessToken(page, qaAuth.accessToken);
    result.directAccessTokenFallbackUsed ||= authState.mode === 'direct_access_token_fallback';
    await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    authState = await installAccessToken(page, qaAuth.accessToken);
    result.directAccessTokenFallbackUsed ||= authState.mode === 'direct_access_token_fallback';
    await page.waitForFunction(() => window.location.pathname === '/c/new', undefined, {
      timeout: 10000,
    });

    await submitPrompt(page, args.setupPrompt);
    const conversationId = await waitForConversationForPrompt({
      qaAuth,
      prompt: args.setupPrompt,
      startedAt: args.startedAt,
      timeoutMs: args.timeoutMs,
      page,
    });
    result.conversationIdHash = hashValue(conversationId);
    if (extractConversationIdFromUrl(page.url()) !== conversationId) {
      await page.waitForFunction(
        (expectedConversationId) => window.location.pathname === `/c/${expectedConversationId}`,
        conversationId,
        { timeout: 30000 },
      ).catch(() => {});
    }
    if (extractConversationIdFromUrl(page.url()) !== conversationId) {
      await page.goto(`${args.clientBase}/c/${conversationId}`, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      authState = await installAccessToken(page, qaAuth.accessToken);
      result.directAccessTokenFallbackUsed ||= authState.mode === 'direct_access_token_fallback';
    }
    await waitForSetupCards(page, args.timeoutMs);
    result.setupCardsVisible = true;
    const setupUserMessage = await waitForUserMessage({
      qaAuth,
      conversationId,
      prompt: args.setupPrompt,
      startedAt: args.startedAt,
      timeoutMs: args.timeoutMs,
    });
    result.setupFollowUpReady = Boolean(setupUserMessage?.messageId);

    await submitPrompt(page, args.testPrompt);
    const latestUserMessage = await waitForUserMessage({
      qaAuth,
      conversationId,
      prompt: args.testPrompt,
      startedAt: args.startedAt,
      timeoutMs: args.timeoutMs,
    });
    const latestAssistantParent = await waitForAssistantParent({
      qaAuth,
      conversationId,
      userMessageId: latestUserMessage.messageId,
      timeoutMs: args.timeoutMs,
      expectedText: args.testExpectedText,
      requireExactText: true,
    });
    await page.waitForFunction(
      () => /\bTEST_OK\b/.test(document.body.innerText || ''),
      undefined,
      { timeout: 60000 },
    );
    result.testOkVisibleBeforeReload = /\bTEST_OK\b/.test(await visibleBodyText(page));

    // Wait past the normal activation/status window so a stale-history activation has time to attach.
    await page.waitForTimeout(Math.max(0, args.settleMs));
    const latestState = await readLatestTurnState({
      qaAuth,
      conversationId,
      userMessageId: latestUserMessage.messageId,
      assistantMessageId: latestAssistantParent.messageId,
    });
    const latestParentText = extractVisibleAnswerTextFromMessage(latestAssistantParent);
    Object.assign(result, {
      latestParentHash: latestState.parentHash,
      latestParentTextLength: latestState.parentTextLength,
      latestParentIncludesTestOk: latestState.parentIncludesTestOk,
      latestParentExactExpectedText: isExactExpectedAnswer(
        latestParentText,
        args.testExpectedText,
      ),
      latestDirectAssistantCount: latestState.directAssistantCount,
      latestPhaseBChildCount: latestState.phaseBChildCount,
      latestPhaseBChildVisibleTextCount: latestState.phaseBChildVisibleTextCount,
      latestScopedCortexPartCount: latestState.scopedCortexPartCount,
      latestScopedCortexNames: latestState.scopedCortexNames,
    });

    await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
    authState = await installAccessToken(page, qaAuth.accessToken);
    result.directAccessTokenFallbackUsed ||= authState.mode === 'direct_access_token_fallback';
    if (extractConversationIdFromUrl(page.url()) !== conversationId) {
      await page.goto(`${args.clientBase}/c/${conversationId}`, {
        waitUntil: 'domcontentloaded',
        timeout: 60000,
      });
      authState = await installAccessToken(page, qaAuth.accessToken);
      result.directAccessTokenFallbackUsed ||= authState.mode === 'direct_access_token_fallback';
    }
    result.testOkVisibleAfterReload = /\bTEST_OK\b/.test(await visibleBodyText(page));
    result.pass =
      result.setupCardsVisible &&
      result.setupFollowUpReady &&
      result.latestParentIncludesTestOk &&
      result.latestParentExactExpectedText &&
      result.testOkVisibleBeforeReload &&
      result.testOkVisibleAfterReload &&
      result.latestScopedCortexPartCount === 0 &&
      result.latestPhaseBChildVisibleTextCount === 0;
  } catch (error) {
    if (error?.qaBlocked || String(error?.message || '').startsWith('environment_blocked:')) {
      result.environmentBlocked = true;
      result.environmentBlockReason = sanitizePublicError(
        String(error?.message || '').replace(/^environment_blocked:/, ''),
      );
    }
    result.error = sanitizePublicError(error?.message || error || 'qa_failed');
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (qaAuth) {
      await qaAuth.close().catch(() => {});
    }
  }

  const report = [
    '# Latest-User Activation Browser QA',
    '',
    `- Started: ${result.startedAt}`,
    '- Scope: local synthetic browser run with public-safe hashes only; release approval still requires committed diffs, nested pin agreement, scans, and review-only gates.',
    '- Contract: setup cards must appear, then the latest simple output-only user message must answer without stale-history cortex cards.',
    `- Client hash: \`${result.clientBaseHash}\``,
    `- API hash: \`${result.apiBaseHash}\``,
    `- QA user hash: \`${result.qaEmailHash}\``,
    `- Setup prompt hash: \`${result.setupPromptHash}\``,
    `- Test prompt hash: \`${result.testPromptHash}\``,
    `- Conversation hash: \`${result.conversationIdHash || 'unverified'}\``,
    `- Setup cards visible: ${Boolean(result.setupCardsVisible)}`,
    `- Setup follow-up ready: ${Boolean(result.setupFollowUpReady)}`,
    `- Latest assistant hash: \`${result.latestParentHash || 'unverified'}\``,
    `- Latest parent text length: ${result.latestParentTextLength}`,
    `- Latest parent includes TEST_OK: ${Boolean(result.latestParentIncludesTestOk)}`,
    `- Latest parent exactly expected text: ${Boolean(result.latestParentExactExpectedText)}`,
    `- TEST_OK visible before reload: ${Boolean(result.testOkVisibleBeforeReload)}`,
    `- TEST_OK visible after reload: ${Boolean(result.testOkVisibleAfterReload)}`,
    `- Latest direct assistant count: ${result.latestDirectAssistantCount}`,
    `- Latest Phase B child count: ${result.latestPhaseBChildCount}`,
    `- Latest Phase B visible child count: ${result.latestPhaseBChildVisibleTextCount}`,
    `- Latest scoped cortex part count: ${result.latestScopedCortexPartCount}`,
    `- Latest scoped cortex names: ${result.latestScopedCortexNames.join(', ') || 'none'}`,
    `- Direct access-token fallback used: ${Boolean(result.directAccessTokenFallbackUsed)}`,
    `- Environment blocked: ${Boolean(result.environmentBlocked)}`,
    result.environmentBlockReason
      ? `- Environment block reason: ${result.environmentBlockReason}`
      : '',
    `- Result: ${result.pass ? 'PASS' : result.environmentBlocked ? 'BLOCKED' : 'FAIL'}`,
    result.error ? `- Error: ${result.error}` : '',
    '',
  ]
    .filter(Boolean)
    .join('\n');
  fs.mkdirSync(path.dirname(args.out), { recursive: true });
  fs.writeFileSync(args.out, `${report}\n`, 'utf8');
  console.log(JSON.stringify(result, null, 2));
  return result;
}

if (require.main === module) {
  run()
    .then((result) => {
      process.exit(exitCodeForResult(result));
    })
    .catch((error) => {
      console.error(sanitizePublicError(error?.message || error || 'qa_failed'));
      process.exit(1);
    });
}

module.exports = {
  exitCodeForResult,
  readVisibleEnvironmentBlock,
  sanitizePublicError,
  throwEnvironmentBlock,
};
