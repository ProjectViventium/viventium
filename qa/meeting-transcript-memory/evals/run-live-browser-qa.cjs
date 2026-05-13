#!/usr/bin/env node
/* eslint-disable no-console */
/**
 * Live browser QA for meeting transcript recall.
 *
 * Public-safe by design:
 * - Uses a non-owner QA account only.
 * - Seeds synthetic meeting transcript summary artifacts, not raw private transcripts.
 * - Writes hashes, counts, and boolean checks to the public report.
 * - Stores screenshots/raw runtime details only under output/playwright/.
 */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const HARDENER_PATH = path.join(LIBRECHAT_ROOT, 'scripts', 'viventium-memory-hardening.js');
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const OWNER_EMAIL = String(process.env.VIVENTIUM_QA_OWNER_EMAIL || '').trim().toLowerCase();

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function hashValue(value, length = 16) {
  return crypto.createHash('sha256').update(String(value || '')).digest('hex').slice(0, length);
}

function sanitizePublicError(value) {
  return String(value || 'qa_failed')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email>')
    .replace(/https?:\/\/[^\s)]+/gi, '<url>')
    .replace(/\/Users\/[^\s)]+/g, '<path>')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer <redacted>')
    .replace(/(sk|rk|pk|ghp|gho|xox[baprs]?)-[A-Za-z0-9._-]+/g, '<secret>')
    .replace(/\b[a-f0-9]{24}\b/gi, '<mongo-id>')
    .replace(/\s+/g, ' ')
    .slice(0, 260);
}

function parseArgs(argv) {
  const startedAt = new Date();
  const stamp = timestampSlug(startedAt);
  const marker = `MTM-LIVE-QA-${hashValue(stamp, 10)}`;
  const args = {
    startedAt,
    marker,
    clientBase: process.env.VIVENTIUM_QA_CLIENT_BASE || 'http://localhost:3190',
    apiBase: process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180',
    qaEmail: String(process.env.VIVENTIUM_QA_EMAIL || '').trim().toLowerCase(),
    qaUsername: String(process.env.VIVENTIUM_QA_USERNAME || '').trim(),
    agentId: process.env.VIVENTIUM_QA_AGENT_ID || 'agent_viventium_main_95aeb3',
    headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
    timeoutMs: Number(process.env.VIVENTIUM_QA_TIMEOUT_MS || 180000),
    outputDir:
      process.env.VIVENTIUM_QA_OUTPUT_DIR ||
      path.join(REPO_ROOT, 'output', 'playwright', 'meeting-transcript-memory', stamp),
    publicReport:
      process.env.VIVENTIUM_QA_REPORT_PATH ||
      path.join(
        REPO_ROOT,
        'qa',
        'meeting-transcript-memory',
        'reports',
        `2026-05-12-live-browser-qa-${stamp}.md`,
      ),
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
    } else if (arg === '--qa-username') {
      args.qaUsername = next;
      i += 1;
    } else if (arg === '--headed') {
      args.headless = false;
    } else if (arg === '--headless') {
      args.headless = true;
    } else if (arg === '--output-dir') {
      args.outputDir = path.resolve(next);
      i += 1;
    } else if (arg === '--public-report') {
      args.publicReport = path.resolve(next);
      i += 1;
    } else if (arg === '--timeout-ms') {
      args.timeoutMs = Number(next);
      i += 1;
    }
  }
  args.qaEmail = String(args.qaEmail || '').trim().toLowerCase();
  args.qaUsername = String(args.qaUsername || '').trim();
  args.clientBase = args.clientBase.replace(/\/$/, '');
  args.apiBase = args.apiBase.replace(/\/$/, '');
  return args;
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const index = line.indexOf('=');
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      value.length >= 2 &&
      value[0] === value[value.length - 1] &&
      (value[0] === '"' || value[0] === "'")
    ) {
      value = value.slice(1, -1);
    }
    if (value === '' && values[key]) continue;
    values[key] = value;
  }
  return values;
}

function loadRuntimeEnv() {
  const appRuntime = path.join(os.homedir(), 'Library', 'Application Support', 'Viventium', 'runtime');
  const isolatedRuntime = path.join(REPO_ROOT, '.viventium', 'runtime', 'isolated');
  const candidates = [
    path.join(appRuntime, 'runtime.env'),
    path.join(appRuntime, 'runtime.local.env'),
    path.join(appRuntime, 'service-env', 'librechat.env'),
    path.join(isolatedRuntime, 'local.env'),
    path.join(isolatedRuntime, 'librechat.env'),
    path.join(isolatedRuntime, 'runtime.env'),
    path.join(isolatedRuntime, 'runtime.local.env'),
    path.join(isolatedRuntime, 'service-env', 'librechat.env'),
    path.join(LIBRECHAT_ROOT, '.env'),
  ];
  const env = { ...process.env };
  for (const candidate of candidates) {
    const parsed = parseEnvFile(candidate);
    for (const [key, value] of Object.entries(parsed)) {
      if (value === '' && env[key]) continue;
      env[key] = value;
    }
  }
  return env;
}

function sourcePathHash(sourceDir) {
  if (!sourceDir) return null;
  const expanded =
    sourceDir === '~'
      ? os.homedir()
      : sourceDir.startsWith('~/')
        ? path.join(os.homedir(), sourceDir.slice(2))
        : sourceDir;
  return hashValue(path.resolve(expanded), 16);
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

async function selectQaUser({ db, args }) {
  if (!OWNER_EMAIL) {
    throw new Error('missing_owner_email_guard');
  }
  if (!args.qaEmail && !args.qaUsername) {
    throw new Error('missing_explicit_qa_account');
  }
  if (args.qaEmail && args.qaEmail === OWNER_EMAIL) {
    throw new Error('qa_email_matches_owner_refused');
  }
  const queries = [];
  if (args.qaEmail) queries.push({ email: args.qaEmail });
  if (args.qaUsername) queries.push({ username: args.qaUsername });

  for (const query of queries) {
    const user = await db.collection('users').findOne(query);
    if (!user?._id) continue;
    if (OWNER_EMAIL && String(user.email || '').toLowerCase() === OWNER_EMAIL) {
      throw new Error('selected_owner_account_refused');
    }
    return user;
  }
  throw new Error('qa_user_not_found');
}

async function countOwnerMeetingTranscriptFiles(db) {
  if (!OWNER_EMAIL) return null;
  const owner = await db.collection('users').findOne({ email: OWNER_EMAIL }, { projection: { _id: 1 } });
  if (!owner?._id) return null;
  return db.collection('files').countDocuments({
    user: owner._id,
    context: 'meeting_transcript',
  });
}

function transcriptFixture({ marker, sourceHash, userId }) {
  const fixtures = [
    {
      filename: `mtm-live-qa-helios-${marker}.csv`,
      meeting_datetime: '2026-05-12T10:15:00-04:00',
      display_title: `Helios launch review ${marker}`,
      one_line_summary:
        'A synthetic launch-readiness review covering onboarding, risk ownership, and transcript-only caveats.',
      participants: ['Ava Chen', 'Ben Ortiz', 'QA User'],
      file_content:
        'speaker,timestamp,text\n' +
        `Ava Chen,2026-05-12T10:15:00-04:00,${marker} asks for the onboarding checklist to be verified before launch.\n` +
        'Ben Ortiz,2026-05-12T10:18:00-04:00,Ben owns the launch risk review and rollback checklist.\n' +
        'QA User,2026-05-12T10:21:00-04:00,The Atlas migration wording is a meeting-scoped transcript caveat, not a stable user belief.\n',
      summary:
        `Detailed meeting transcript summary for ${marker}.\n\n` +
        'Subject/title: Helios launch review.\n' +
        'Date/time: 2026-05-12 10:15 AM Eastern, from transcript timestamps.\n' +
        'Participants: Ava Chen, Ben Ortiz, and QA User.\n' +
        'Context: synthetic QA meeting used to verify meeting transcript recall, inventory, speaker visibility, and stale-belief caution.\n' +
        'Who said what: Ava Chen asked that the onboarding checklist be verified before launch. Ben Ortiz took ownership of the launch risk review and rollback checklist. QA User explicitly said the Atlas migration wording is a meeting-scoped transcript caveat and must not be treated as a stable user belief.\n' +
        'Outcomes/follow-ups: Ben owns the launch risk review and rollback checklist; onboarding checklist verification remains a follow-up.\n' +
        'Risks/concerns: risk ownership and rollback readiness were the main concerns.\n' +
        'Uncertainties/caveats: this is synthetic transcript evidence; transcript content may be incomplete or audience-specific.',
    },
    {
      filename: `mtm-live-qa-orion-${marker}.vtt`,
      meeting_datetime: '2026-05-12T14:30:00-04:00',
      display_title: `Orion customer review ${marker}`,
      one_line_summary:
        'A synthetic customer review covering support escalation, participants, and source-quality caveats.',
      participants: ['Mira Patel', 'Noah Reed', 'QA User'],
      file_content:
        `WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nMira Patel: ${marker} Orion customer review starts.\n\n` +
        '00:00:05.000 --> 00:00:09.000\nNoah Reed: Noah owns the support escalation note, while QA User keeps scope caveats explicit.\n',
      summary:
        `Detailed meeting transcript summary for ${marker}.\n\n` +
        'Subject/title: Orion customer review.\n' +
        'Date/time: 2026-05-12 2:30 PM Eastern, inferred from the file metadata and transcript header.\n' +
        'Participants: Mira Patel, Noah Reed, and QA User.\n' +
        'Context: synthetic QA meeting used to verify that inventory and focused summary retrieval preserve meeting-level context.\n' +
        'Who said what: Mira Patel opened the Orion customer review. Noah Reed took ownership of the support escalation note. QA User kept the transcript-source caveat explicit.\n' +
        'Outcomes/follow-ups: Noah owns the support escalation note.\n' +
        'Risks/concerns: support escalation must not be confused with a durable personal preference.\n' +
        'Uncertainties/caveats: this is synthetic transcript evidence and should be interpreted as meeting-scoped context.',
    },
  ];

  return fixtures.map((fixture) => {
    const contentHash = crypto.createHash('sha256').update(fixture.file_content).digest('hex');
    const artifactId = `meeting_transcript:${contentHash.slice(0, 32)}`;
    return {
      ...fixture,
      artifactId,
      rawFileId: `meeting_transcript:${userId}:${contentHash.slice(0, 32)}`,
      summaryFileId: `meeting_summary:${userId}:${contentHash.slice(0, 32)}`,
      sourcePathHash: sourceHash,
      contentHash,
      file_mtime: fixture.meeting_datetime,
      source_status: 'qa_synthetic_current',
      calendar_match: null,
      input_complete: true,
      raw_char_count: fixture.file_content.length,
      supplied_char_count: fixture.file_content.length,
      summary_char_count: fixture.summary.length,
    };
  });
}

async function seedSyntheticTranscriptArtifacts({ env, db, user, args }) {
  Object.assign(process.env, env);
  const hardener = require(HARDENER_PATH);
  const mongoose = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongoose'));
  const { createModels } = require(path.join(LIBRECHAT_ROOT, 'node_modules', '@librechat', 'data-schemas'));

  if (!env.MONGO_URI) throw new Error('missing_mongo_uri');
  if (!env.RAG_API_URL) throw new Error('missing_rag_api_url');
  const sourceHash = sourcePathHash(env.VIVENTIUM_MEMORY_TRANSCRIPTS_DIR);
  if (!sourceHash) throw new Error('missing_transcript_source_hash');
  if (mongoose.connection.readyState !== 1) {
    await mongoose.connect(env.MONGO_URI);
    createModels(mongoose);
  }

  const userId = String(user._id);
  const transcripts = transcriptFixture({ marker: args.marker, sourceHash, userId });
  const beforeOwnerCount = await countOwnerMeetingTranscriptFiles(db);
  const lifecycle = await hardener.applyTranscriptVectorLifecycle({
    userProposal: {
      userId,
      transcripts,
      staleTranscriptArtifacts: [],
      transcriptRagMode: 'detailed_summary_only',
      transcriptSourcePathHash: sourceHash,
      transcriptInventoryRefresh: true,
      transcriptIndex: { sourcePathHash },
    },
  });
  const afterOwnerCount = await countOwnerMeetingTranscriptFiles(db);
  return {
    lifecycle,
    sourceHash,
    transcripts,
    ownerCountUnchanged:
      beforeOwnerCount === null && afterOwnerCount === null ? null : beforeOwnerCount === afterOwnerCount,
  };
}

async function createQaAuth({ env, user }) {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('local_qa_jwt_forbidden_in_ci_or_production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`local_qa_jwt_requires_${LOCAL_JWT_ALLOW_ENV}`);
  }
  if (!env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error('missing_jwt_prerequisites');
  }
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const { ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const userId = String(user._id);
  const sessionId = new ObjectId();
  const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
  const refreshToken = jwt.sign(
    { id: userId, sessionId: sessionId.toString() },
    env.JWT_REFRESH_SECRET,
    { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
  );
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
  return { sessionId, expiration, refreshToken, accessToken, userId };
}

async function attachAuthCookies({ context, args, auth }) {
  const expires = Math.floor(Date.now() / 1000) + 7200;
  const cookies = [args.apiBase, args.clientBase].flatMap((url) => [
    {
      name: 'refreshToken',
      value: auth.refreshToken,
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

async function installAccessToken(page, accessToken) {
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
      token: typeof payload?.token === 'string' ? payload.token : '',
    };
  });
  const token = refresh.ok && refresh.token ? refresh.token : accessToken;
  await page.evaluate((value) => {
    window.dispatchEvent(new CustomEvent('tokenUpdated', { detail: value }));
  }, token);
  await page.waitForTimeout(300);
  return { refreshStatus: refresh.status, directFallback: !(refresh.ok && refresh.token) };
}

async function submitPrompt(page, prompt) {
  const input = page.getByLabel('Message input').or(page.getByPlaceholder(/^Message Viventium$/)).last();
  await input.waitFor({ state: 'visible', timeout: 60000 });
  await input.fill(prompt);
  await page.getByTestId('send-button').last().click({ timeout: 30000 });
}

function extractText(message) {
  const text = typeof message?.text === 'string' ? message.text : '';
  const partText = Array.isArray(message?.content)
    ? message.content
        .map((part) => {
          if (!part || part.type !== 'text') return '';
          if (typeof part.text === 'string') return part.text;
          if (typeof part.text?.value === 'string') return part.text.value;
          return '';
        })
        .filter(Boolean)
        .join('\n')
    : '';
  return [text, partText].filter(Boolean).join('\n').trim();
}

async function waitForUserMessage({ db, userId, prompt, startedAt, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const message = await db.collection('messages').findOne(
      {
        user: userId,
        isCreatedByUser: true,
        text: prompt,
        createdAt: { $gte: startedAt },
      },
      { sort: { createdAt: -1, _id: -1 } },
    );
    if (message?.messageId) return message;
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
      .limit(8)
      .toArray();
    const direct = messages.find((message) => message.parentMessageId === userMessageId);
    const candidate = direct || messages[0];
    const text = extractText(candidate);
    if (candidate && text.length > 40) {
      return candidate;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('missing_browser_assistant_message');
}

async function hydrateToolAttachments({ db, message, timeoutMs = 20000 }) {
  if (!message?.messageId) return message;
  const hasToolCall = Array.isArray(message.content)
    ? message.content.some((part) => part?.type === 'tool_call')
    : false;
  if (!hasToolCall) return message;
  const deadline = Date.now() + timeoutMs;
  let latest = message;
  while (Date.now() < deadline) {
    latest = await db.collection('messages').findOne({ messageId: message.messageId });
    const attachments = Array.isArray(latest?.attachments) ? latest.attachments : [];
    if (attachments.some((attachment) => Array.isArray(attachment?.file_search?.sources))) {
      return latest;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return latest;
}

function summarizeSources(message, marker) {
  const attachments = Array.isArray(message?.attachments) ? message.attachments : [];
  const sources = attachments.flatMap((attachment) =>
    Array.isArray(attachment?.file_search?.sources) ? attachment.file_search.sources : [],
  );
  const fileNames = sources.map((source) => String(source.fileName || ''));
  const fileIds = sources.map((source) => String(source.fileId || ''));
  const contents = sources.map((source) => String(source.content || ''));
  return {
    toolCallCount: Array.isArray(message?.content)
      ? message.content.filter((part) => part?.tool_call?.name === 'file_search').length
      : 0,
    attachmentCount: attachments.length,
    sourceCount: sources.length,
    inventorySourceCount: sources.filter((source, index) => {
      const fileId = fileIds[index];
      const fileName = fileNames[index];
      const content = contents[index];
      return (
        fileId.startsWith('meeting_inventory:') ||
        fileName.includes('meeting-transcript-inventory') ||
        content.includes('Transcript artifact kind: inventory')
      );
    }).length,
    summarySourceCount: sources.filter((source, index) => {
      const fileId = fileIds[index];
      const fileName = fileNames[index];
      const content = contents[index];
      return (
        fileId.startsWith('meeting_summary:') ||
        fileName.includes('meeting-transcript-summary') ||
        content.includes('Transcript artifact kind: summary')
      );
    }).length,
    markerInSources: contents.some((content) => content.includes(marker)),
    fileNameHashes: fileNames.map((name) => hashValue(name, 10)).slice(0, 12),
  };
}

async function runBrowserPrompt({ page, db, userId, prompt, startedAt, timeoutMs, marker }) {
  await submitPrompt(page, prompt);
  const userMessage = await waitForUserMessage({
    db,
    userId,
    prompt,
    startedAt,
    timeoutMs,
  });
  const assistantMessage = await waitForAssistantMessage({
    db,
    userId,
    conversationId: userMessage.conversationId,
    userMessageId: userMessage.messageId,
    startedAt,
    timeoutMs,
  });
  const hydratedAssistantMessage = await hydrateToolAttachments({ db, message: assistantMessage });
  const answerText = extractText(hydratedAssistantMessage);
  const bodyText = await page.locator('body').innerText({ timeout: 10000 }).catch(() => '');
  return {
    userMessage,
    assistantMessage: hydratedAssistantMessage,
    answerText,
    bodyText,
    sourceSummary: summarizeSources(hydratedAssistantMessage, marker),
  };
}

function writePublicReport({ args, result }) {
  ensureDir(path.dirname(args.publicReport));
  const ownerCountStatus =
    result.ownerCountUnchanged === null ? 'not checked' : result.ownerCountUnchanged ? 'yes' : 'no';
  const lines = [
    `# 2026-05-12 Meeting Transcript Live Browser QA`,
    '',
    '## Scope',
    '',
    'Validated the local LibreChat UI on the running Viventium stack with a non-owner QA account and synthetic transcript-summary artifacts.',
    '',
    '## Result',
    '',
    `- Status: ${result.pass ? 'PASS' : 'FAIL'}`,
    `- Runtime: frontend ${args.clientBase.replace(/localhost:\d+/, 'localhost:<port>')}; API ${args.apiBase.replace(/localhost:\d+/, 'localhost:<port>')}`,
    `- QA user hash: ${result.qaUserHash || '<missing>'}`,
    `- Inventory prompt hash: ${hashValue(result.inventoryPrompt || '')}`,
    `- Detail prompt hash: ${hashValue(result.detailPrompt || '')}`,
    `- Conversation hash: ${result.conversationHash || '<missing>'}`,
    `- Screenshot artifact: ${result.screenshotSaved ? 'saved under output/playwright' : 'not saved'}`,
    '',
    '## Checks',
    '',
    `- Explicit owner refusal guard configured: ${result.ownerGuardConfigured ? 'yes' : 'no'}`,
    `- Non-owner QA account selected: ${result.nonOwnerQa ? 'yes' : 'no'}`,
    `- Owner meeting-transcript count unchanged: ${ownerCountStatus}`,
    `- Synthetic summaries uploaded/refreshed: ${result.syntheticSummaryFilesPresent ? 'yes' : 'no'}`,
    `- Inventory artifact present: ${result.inventoryFilePresent ? 'yes' : 'no'}`,
    `- Raw transcript artifacts uploaded in default mode: ${result.rawArtifactCount}`,
    `- Browser submitted inventory prompt and received visible response: ${result.inventoryVisibleResponse ? 'yes' : 'no'}`,
    `- Inventory response used file_search: ${result.inventorySourceSummary.toolCallCount > 0 ? 'yes' : 'no'}`,
    `- Inventory file_search inventory sources: ${result.inventorySourceSummary.inventorySourceCount}`,
    `- Browser submitted detail prompt and received visible response: ${result.detailVisibleResponse ? 'yes' : 'no'}`,
    `- Detail response used file_search: ${result.detailSourceSummary.toolCallCount > 0 ? 'yes' : 'no'}`,
    `- Detail file_search summary sources: ${result.detailSourceSummary.summarySourceCount}`,
    `- Synthetic marker found in detail retrieved sources: ${result.detailSourceSummary.markerInSources ? 'yes' : 'no'}`,
    `- Answer preserved meeting-scoped caveat shape: ${result.answerChecks.meetingScopedCaveat ? 'yes' : 'no'}`,
    `- Answer included participants/details from synthetic summaries: ${result.answerChecks.participantsAndDetails ? 'yes' : 'no'}`,
    '',
    '## Public-Safety Note',
    '',
    'This report intentionally omits raw prompts, raw assistant text, account emails, local paths, transcript content, and screenshots. Raw browser artifacts, if any, stay under local output/playwright and are not public evidence.',
  ];
  if (result.error) {
    lines.push('', '## Error', '', `- ${sanitizePublicError(result.error)}`);
  }
  fs.writeFileSync(args.publicReport, `${lines.join('\n')}\n`, 'utf8');
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = {
    pass: false,
    qaUserHash: '',
    ownerGuardConfigured: Boolean(OWNER_EMAIL),
    nonOwnerQa: false,
    ownerCountUnchanged: null,
    syntheticSummaryFilesPresent: false,
    inventoryFilePresent: false,
    rawArtifactCount: -1,
    inventoryVisibleResponse: false,
    detailVisibleResponse: false,
    conversationHash: '',
    screenshotSaved: false,
    inventoryPrompt: '',
    detailPrompt: '',
    inventorySourceSummary: {
      toolCallCount: 0,
      attachmentCount: 0,
      sourceCount: 0,
      inventorySourceCount: 0,
      summarySourceCount: 0,
      markerInSources: false,
      fileNameHashes: [],
    },
    detailSourceSummary: {
      toolCallCount: 0,
      attachmentCount: 0,
      sourceCount: 0,
      inventorySourceCount: 0,
      summarySourceCount: 0,
      markerInSources: false,
      fileNameHashes: [],
    },
    answerChecks: {
      meetingScopedCaveat: false,
      participantsAndDetails: false,
    },
    error: null,
  };
  ensureDir(args.outputDir);
  const env = loadRuntimeEnv();
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const client = new MongoClient(env.MONGO_URI);
  let browser;
  try {
    await client.connect();
    const db = client.db(new URL(env.MONGO_URI).pathname.replace(/^\//, '') || 'LibreChatViventium');
    const user = await selectQaUser({ db, args });
    result.qaUserHash = hashValue(user._id, 12);
    result.nonOwnerQa = String(user.email || '').toLowerCase() !== OWNER_EMAIL;
    const seeded = await seedSyntheticTranscriptArtifacts({ env, db, user, args });
    result.ownerCountUnchanged = seeded.ownerCountUnchanged;

    const userId = String(user._id);
    const summaryFileIds = seeded.transcripts.map((transcript) => transcript.summaryFileId);
    result.syntheticSummaryFilesPresent =
      (await db.collection('files').countDocuments({
        user: user._id,
        file_id: { $in: summaryFileIds },
        embedded: true,
        'metadata.meetingTranscriptKind': 'summary',
      })) === summaryFileIds.length;
    result.inventoryFilePresent =
      (await db.collection('files').countDocuments({
        user: user._id,
        context: 'meeting_transcript',
        embedded: true,
        'metadata.meetingTranscriptKind': 'inventory',
        'metadata.meetingTranscriptSourcePathHash': seeded.sourceHash,
      })) > 0;
    result.rawArtifactCount = await db.collection('files').countDocuments({
      user: user._id,
      context: 'meeting_transcript',
      'metadata.meetingTranscriptKind': 'raw',
      'metadata.meetingTranscriptContentHash': {
        $in: seeded.transcripts.map((transcript) => transcript.contentHash),
      },
    });

    const auth = await createQaAuth({ env, user });
    await db.collection('sessions').insertOne({
      _id: auth.sessionId,
      user: user._id,
      expiration: auth.expiration,
      refreshTokenHash: crypto.createHash('sha256').update(auth.refreshToken).digest('hex'),
    });

    const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
    browser = await chromium.launch({ channel: 'chrome', headless: args.headless });
    const context = await browser.newContext({
      baseURL: args.clientBase,
      viewport: { width: 1365, height: 920 },
    });
    await attachAuthCookies({ context, args, auth });
    const page = await context.newPage();
    await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await installAccessToken(page, auth.accessToken);
    await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await installAccessToken(page, auth.accessToken);

    const inventoryPrompt =
      'Use file_search meeting transcript recall to answer a broad inventory question. ' +
      'Retrieve the meeting transcript inventory or table of contents if it is available. ' +
      'What recent meeting transcript entries do you see? Include date/time, participants, and one-line context when visible.';
    result.inventoryPrompt = inventoryPrompt;
    const inventoryRun = await runBrowserPrompt({
      page,
      db,
      userId,
      prompt: inventoryPrompt,
      startedAt: args.startedAt,
      timeoutMs: args.timeoutMs,
      marker: args.marker,
    });
    result.conversationHash = hashValue(inventoryRun.userMessage.conversationId, 12);
    result.inventoryVisibleResponse = Boolean(inventoryRun.answerText || inventoryRun.bodyText);
    result.inventorySourceSummary = inventoryRun.sourceSummary;

    await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await installAccessToken(page, auth.accessToken);
    const detailPrompt =
      `Use file_search meeting transcript recall. Find synthetic marker ${args.marker}. ` +
      'List the Helios and Orion transcript entries with date/time, participants, and one-line context. ' +
      'Then answer who owns the launch risk review, and whether the Atlas migration wording is a stable user belief or only meeting-scoped transcript context.';
    result.detailPrompt = detailPrompt;
    const detailRun = await runBrowserPrompt({
      page,
      db,
      userId,
      prompt: detailPrompt,
      startedAt: args.startedAt,
      timeoutMs: args.timeoutMs,
      marker: args.marker,
    });
    await page.waitForFunction(
      (needle) => (document.body.innerText || '').includes(needle),
      args.marker,
      { timeout: 60000 },
    ).catch(() => {});
    result.detailVisibleResponse = Boolean(detailRun.answerText || detailRun.bodyText.includes(args.marker));
    result.detailSourceSummary = detailRun.sourceSummary;
    const normalizedAnswer = `${detailRun.answerText}\n${detailRun.bodyText}`.replace(/\s+/g, ' ').toLowerCase();
    result.answerChecks.meetingScopedCaveat =
      normalizedAnswer.includes('meeting-scoped') &&
      normalizedAnswer.includes('not') &&
      normalizedAnswer.includes('stable user belief');
    result.answerChecks.participantsAndDetails =
      normalizedAnswer.includes('ben ortiz') &&
      normalizedAnswer.includes('atlas migration') &&
      normalizedAnswer.includes('launch risk') &&
      normalizedAnswer.includes('helios') &&
      normalizedAnswer.includes('orion');
    const screenshotPath = path.join(args.outputDir, 'browser-result.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    fs.writeFileSync(
      path.join(args.outputDir, 'result.private.json'),
      JSON.stringify(
        {
          marker: args.marker,
          qaUserHash: result.qaUserHash,
          conversationHash: result.conversationHash,
          inventoryAssistantMessageHash: hashValue(
            inventoryRun.assistantMessage.messageId || inventoryRun.assistantMessage._id,
            12,
          ),
          detailAssistantMessageHash: hashValue(
            detailRun.assistantMessage.messageId || detailRun.assistantMessage._id,
            12,
          ),
          inventoryAnswerHash: hashValue(inventoryRun.answerText, 16),
          detailAnswerHash: hashValue(detailRun.answerText, 16),
          inventoryAnswerLength: inventoryRun.answerText.length,
          detailAnswerLength: detailRun.answerText.length,
          inventorySourceSummary: result.inventorySourceSummary,
          detailSourceSummary: result.detailSourceSummary,
        },
        null,
        2,
      ),
      'utf8',
    );
    result.screenshotSaved = true;
    result.pass =
      result.ownerGuardConfigured &&
      result.nonOwnerQa &&
      result.ownerCountUnchanged === true &&
      result.syntheticSummaryFilesPresent &&
      result.inventoryFilePresent &&
      result.rawArtifactCount === 0 &&
      result.inventoryVisibleResponse &&
      result.detailVisibleResponse &&
      result.inventorySourceSummary.toolCallCount > 0 &&
      result.inventorySourceSummary.inventorySourceCount > 0 &&
      result.detailSourceSummary.toolCallCount > 0 &&
      result.detailSourceSummary.summarySourceCount > 0 &&
      result.detailSourceSummary.markerInSources &&
      result.answerChecks.meetingScopedCaveat &&
      result.answerChecks.participantsAndDetails;
  } catch (error) {
    result.error = error?.stack || error?.message || String(error);
  } finally {
    if (browser) await browser.close().catch(() => {});
    await client.close().catch(() => {});
    try {
      const mongoose = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongoose'));
      if (mongoose.connection.readyState !== 0) {
        await mongoose.disconnect();
      }
    } catch {
      // Best-effort cleanup for local QA handles.
    }
    writePublicReport({ args, result });
  }
  console.log(
    JSON.stringify(
      {
        pass: result.pass,
        report: args.publicReport,
        outputDir: args.outputDir,
        qaUserHash: result.qaUserHash,
        conversationHash: result.conversationHash,
        inventorySourceSummary: result.inventorySourceSummary,
        detailSourceSummary: result.detailSourceSummary,
        error: result.error ? sanitizePublicError(result.error) : null,
      },
      null,
      2,
    ),
  );
  return result.pass ? 0 : 1;
}

main().then((code) => {
  process.exitCode = code;
});
