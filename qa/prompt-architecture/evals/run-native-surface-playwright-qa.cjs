#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const PROMPT_BANK_PATH = path.join(__dirname, 'prompt-bank.json');
const DEFAULT_CLIENT_BASE = process.env.VIVENTIUM_EVAL_CLIENT_BASE || 'http://localhost:3190';
const DEFAULT_API_BASE = process.env.VIVENTIUM_EVAL_API_BASE || 'http://localhost:3180';
const DEFAULT_QA_EMAIL = process.env.VIVENTIUM_QA_EMAIL || 'qa@example.com';
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const MAIN_AGENT_ID = process.env.VIVENTIUM_EVAL_AGENT_ID || 'agent_viventium_main_95aeb3';
const DEFAULT_JUDGE_ENDPOINT = process.env.VIVENTIUM_EVAL_JUDGE_ENDPOINT || 'openAI';
const DEFAULT_JUDGE_MODEL = process.env.VIVENTIUM_EVAL_JUDGE_MODEL || 'gpt-5.4';
const STARTER_MORNING_BRIEFING_TEMPLATE_ID = 'morning_briefing_default_v1';
const STARTER_MORNING_BRIEFING_BASELINE_PROMPT =
  'Morning orientation: review my memories, calendar, pending tasks, ' +
  'and any overnight signals. Prepare a concise morning briefing for the user.';
const NO_PARENT = '00000000-0000-0000-0000-000000000000';
const PRIVATE_ROOT =
  process.env.VIVENTIUM_PROMPT_ARCH_PRIVATE_DIR ||
  path.join(os.homedir(), 'Library', 'Application Support', 'Viventium', 'private-user-data');
const FRAME_ROOT = path.join(PRIVATE_ROOT, 'prompt-observability', 'frame-logs');
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ViventiumNativeSurfaceQA/1.0';
const QA_MAPPING_RUN_FIELD = 'viventiumNativeSurfaceQaRunId';
const COMPLETION_PROMPT_FAMILIES = new Set([
  'main_assembly',
  'main_runtime',
  'main_run_create',
]);
const MAX_QA_CLEANUP_ROWS = 4096;
let lastTelegramSourceSequence = 0;

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function parseArgs(argv) {
  const stamp = timestampSlug();
  const args = {
    apiBase: DEFAULT_API_BASE.replace(/\/$/, ''),
    clientBase: DEFAULT_CLIENT_BASE.replace(/\/$/, ''),
    qaEmail: DEFAULT_QA_EMAIL,
    agentId: MAIN_AGENT_ID,
    promptBank: PROMPT_BANK_PATH,
    outputDir: path.join(PRIVATE_ROOT, 'prompt-architecture-evals', `native-surface-${stamp}`),
    publicReport: path.join(
      REPO_ROOT,
      'qa',
      'prompt-architecture',
      'reports',
      `native-surface-qa-${stamp}.md`,
    ),
    timeoutMs: 180_000,
    postCaseObserveMs: 25_000,
    followUpGraceMs: Number.parseInt(process.env.VIVENTIUM_EVAL_FOLLOWUP_GRACE_MS || '30000', 10),
    maxCases: Number.MAX_SAFE_INTEGER,
    maxCasesSpecified: false,
    maxCasesInvalid: false,
    family: '',
    familySpecified: false,
    caseId: '',
    caseIdSpecified: false,
    caseIds: [],
    caseIdsSpecified: false,
    caseIdsMalformed: false,
    surface: '',
    surfaceSpecified: false,
    promptId: '',
    promptIdSpecified: false,
    duplicateSelectors: [],
    runLive: false,
    qaRunId: `native-surface-${crypto.randomUUID()}`,
    runJudge: true,
    judgeEndpoint: DEFAULT_JUDGE_ENDPOINT,
    judgeModel: DEFAULT_JUDGE_MODEL,
    headless: process.env.VIVENTIUM_QA_HEADLESS !== '0',
  };

  for (const arg of argv) {
    if (arg.startsWith('--api-base=')) {
      args.apiBase = arg.slice('--api-base='.length).replace(/\/$/, '');
    } else if (arg.startsWith('--client-base=')) {
      args.clientBase = arg.slice('--client-base='.length).replace(/\/$/, '');
    } else if (arg.startsWith('--qa-email=')) {
      args.qaEmail = arg.slice('--qa-email='.length).trim();
    } else if (arg.startsWith('--agent-id=')) {
      args.agentId = arg.slice('--agent-id='.length).trim() || MAIN_AGENT_ID;
    } else if (arg.startsWith('--prompt-bank=')) {
      args.promptBank = path.resolve(arg.slice('--prompt-bank='.length));
    } else if (arg.startsWith('--output-dir=')) {
      args.outputDir = path.resolve(arg.slice('--output-dir='.length));
    } else if (arg.startsWith('--public-report=')) {
      args.publicReport = path.resolve(arg.slice('--public-report='.length));
    } else if (arg.startsWith('--timeout-ms=')) {
      const parsed = Number.parseInt(arg.slice('--timeout-ms='.length), 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        args.timeoutMs = parsed;
      }
    } else if (arg.startsWith('--post-case-observe-ms=')) {
      const parsed = Number.parseInt(arg.slice('--post-case-observe-ms='.length), 10);
      if (Number.isFinite(parsed) && parsed >= 0) {
        args.postCaseObserveMs = parsed;
      }
    } else if (arg.startsWith('--follow-up-grace-ms=')) {
      const parsed = Number.parseInt(arg.slice('--follow-up-grace-ms='.length), 10);
      if (Number.isFinite(parsed) && parsed >= 0) {
        args.followUpGraceMs = parsed;
      }
    } else if (arg.startsWith('--max-cases=')) {
      args.maxCasesSpecified = true;
      const parsed = Number.parseInt(arg.slice('--max-cases='.length), 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        args.maxCases = parsed;
      } else {
        args.maxCasesInvalid = true;
      }
    } else if (arg.startsWith('--family=')) {
      if (args.familySpecified) {
        args.duplicateSelectors.push('family');
      }
      args.familySpecified = true;
      args.family = arg.slice('--family='.length).trim();
    } else if (arg.startsWith('--case-id=')) {
      if (args.caseIdSpecified) {
        args.duplicateSelectors.push('case-id');
      }
      args.caseIdSpecified = true;
      args.caseId = arg.slice('--case-id='.length).trim();
    } else if (arg.startsWith('--case-ids=')) {
      if (args.caseIdsSpecified) {
        args.duplicateSelectors.push('case-ids');
      }
      args.caseIdsSpecified = true;
      const requestedCaseIds = arg.slice('--case-ids='.length).split(',');
      args.caseIdsMalformed =
        args.caseIdsMalformed || requestedCaseIds.some((value) => !value.trim());
      args.caseIds = requestedCaseIds.map((value) => value.trim()).filter(Boolean);
    } else if (arg.startsWith('--surface=')) {
      if (args.surfaceSpecified) {
        args.duplicateSelectors.push('surface');
      }
      args.surfaceSpecified = true;
      args.surface = arg.slice('--surface='.length).trim();
    } else if (arg.startsWith('--prompt-id=')) {
      if (args.promptIdSpecified) {
        args.duplicateSelectors.push('prompt-id');
      }
      args.promptIdSpecified = true;
      args.promptId = arg.slice('--prompt-id='.length).trim();
    } else if (arg === '--run-live') {
      args.runLive = true;
    } else if (arg === '--no-live') {
      args.runLive = false;
    } else if (arg === '--semantic-judge') {
      args.runJudge = true;
    } else if (arg === '--no-semantic-judge') {
      args.runJudge = false;
    } else if (arg === '--no-judge') {
      args.runJudge = false;
    } else if (arg.startsWith('--judge-endpoint=')) {
      args.judgeEndpoint = arg.slice('--judge-endpoint='.length).trim() || args.judgeEndpoint;
    } else if (arg.startsWith('--judge-model=')) {
      args.judgeModel = arg.slice('--judge-model='.length).trim() || args.judgeModel;
    } else if (arg === '--headed') {
      args.headless = false;
    }
  }
  return args;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) {
    return values;
  }
  const text = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of text.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) {
      continue;
    }
    const [rawKey, ...rest] = trimmed.split('=');
    const key = rawKey.trim();
    let value = rest.join('=').trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

function loadLocalEnv() {
  const candidates = [
    path.join(os.homedir(), 'Library', 'Application Support', 'Viventium', 'runtime', 'runtime.env'),
    path.join(
      os.homedir(),
      'Library',
      'Application Support',
      'Viventium',
      'runtime',
      'runtime.local.env',
    ),
    path.join(
      os.homedir(),
      'Library',
      'Application Support',
      'Viventium',
      'runtime',
      'service-env',
      'librechat.env',
    ),
    path.join(LIBRECHAT_ROOT, '.env'),
  ];
  return candidates.reduce((acc, filePath) => Object.assign(acc, parseEnvFile(filePath)), {
    ...process.env,
  });
}

function expandHome(filePath) {
  if (!filePath) {
    return filePath;
  }
  if (filePath === '~') {
    return os.homedir();
  }
  if (filePath.startsWith('~/')) {
    return path.join(os.homedir(), filePath.slice(2));
  }
  return filePath;
}

function sqlQuote(value) {
  return `'${String(value ?? '').replace(/'/g, "''")}'`;
}

function sqliteUpdateStarterPrompt(dbPath, { userId, agentId }) {
  const resolvedPath = expandHome(dbPath);
  if (!resolvedPath || !fs.existsSync(resolvedPath)) {
    return { ok: false, reason: 'scheduling_db_missing' };
  }
  const updatedAt = new Date().toISOString();
  const updatedBy = agentId ? `agent:${agentId}` : 'agent:qa-fixture';
  const sql = [
    'UPDATE scheduled_tasks',
    `SET prompt = ${sqlQuote(STARTER_MORNING_BRIEFING_BASELINE_PROMPT)},`,
    `updated_at = ${sqlQuote(updatedAt)},`,
    `updated_by = ${sqlQuote(updatedBy)},`,
    "updated_source = 'qa_fixture'",
    `WHERE user_id = ${sqlQuote(userId)}`,
    `AND metadata_json LIKE ${sqlQuote(`%${STARTER_MORNING_BRIEFING_TEMPLATE_ID}%`)};`,
    'SELECT changes();',
  ].join(' ');
  const output = childProcess
    .execFileSync('sqlite3', ['-batch', '-noheader', resolvedPath, sql], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    .trim();
  const changed = Number.parseInt(output.split(/\r?\n/).pop() || '0', 10) || 0;
  return { ok: changed > 0, changed, dbPathHash: hashValue(resolvedPath) };
}

function schedulingDbPathCandidates(env) {
  const profile = env.VIVENTIUM_RUNTIME_PROFILE || 'isolated';
  const candidates = [
    env.SCHEDULING_DB_PATH,
    path.join(
      os.homedir(),
      'Library',
      'Application Support',
      'Viventium',
      'state',
      'runtime',
      profile,
      'scheduling',
      'schedules.db',
    ),
    path.join(os.homedir(), '.viventium', 'scheduling', 'schedules.db'),
  ].filter(Boolean);
  return [...new Set(candidates.map(expandHome))];
}

function updateStarterPromptAcrossDbCandidates(env, { userId, agentId }) {
  const attempts = [];
  for (const candidate of schedulingDbPathCandidates(env)) {
    const result = sqliteUpdateStarterPrompt(candidate, { userId, agentId });
    attempts.push(result);
    if (result.ok) {
      return { ok: true, attempts };
    }
  }
  return { ok: false, attempts };
}

function schedulingBaseUrl(env) {
  const raw = (env.SCHEDULING_MCP_URL || 'http://localhost:7010').replace(/\/$/, '');
  return raw.replace(/\/mcp$/i, '');
}

function needsStarterMorningBriefingFixture(testCase) {
  return testCase?.fixture?.starter_morning_briefing === 'baseline_without_blockers';
}

async function applyStarterMorningBriefingFixture({ args, env, userId, agentId }) {
  if (!userId) {
    return { ok: false, reason: 'missing_qa_user_id' };
  }

  const timezone = process.env.VIVENTIUM_EVAL_QA_TIMEZONE || env.VIVENTIUM_DEFAULT_TIMEZONE || 'America/Toronto';
  const baseUrl = schedulingBaseUrl(env);
  const bootstrapPayload = {
    user_id: userId,
    template_id: STARTER_MORNING_BRIEFING_TEMPLATE_ID,
    agent_id: agentId || args.agentId,
    channels: null,
    timezone,
    time: process.env.VIVENTIUM_EVAL_MORNING_BRIEFING_TIME || '08:00',
    conversation_policy: 'same',
    prompt: STARTER_MORNING_BRIEFING_BASELINE_PROMPT,
    metadata: {
      template_id: STARTER_MORNING_BRIEFING_TEMPLATE_ID,
      bootstrap_source: 'prompt_architecture_eval_fixture',
    },
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10_000);
  let bootstrap = { ok: false, status: 0, body: { reason: 'not_attempted' } };
  try {
    const response = await fetch(`${baseUrl}/internal/bootstrap-schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bootstrapPayload),
      signal: controller.signal,
    });
    bootstrap = {
      ok: response.ok,
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  } catch (error) {
    bootstrap = { ok: false, status: 0, body: { reason: error.message } };
  } finally {
    clearTimeout(timeoutId);
  }

  const primaryUpdate = updateStarterPromptAcrossDbCandidates(env, {
    userId,
    agentId: agentId || args.agentId,
  });
  const mirrorUpdate = env.SCHEDULING_DB_MIRROR_PATH
    ? sqliteUpdateStarterPrompt(env.SCHEDULING_DB_MIRROR_PATH, { userId, agentId: agentId || args.agentId })
    : { ok: true, skipped: true };

  return {
    ok: primaryUpdate.ok,
    fixture: 'starter_morning_briefing_baseline_without_blockers',
    bootstrapStatus: bootstrap.status,
    bootstrapBodyStatus: scrubForPublic(bootstrap.body?.status || bootstrap.body?.reason || ''),
    primaryUpdate,
    mirrorUpdate,
  };
}

function hashValue(value, length = 16) {
  const text = typeof value === 'string' ? value : stableStringify(value);
  return crypto.createHash('sha256').update(text || '').digest('hex').slice(0, length);
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function scrubForPublic(value) {
  if (value == null) {
    return '';
  }
  return String(value)
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '[email]')
    .replace(
      /(?:file:\/\/)?(?:\/Users|\/home|\/tmp|\/var\/folders|\/private\/var\/folders|\/opt|\/etc)\/[^\r\n"'`<>]+/g,
      '[local_path]',
    )
    .replace(/\b(?:sk|xox|ghp|gho|AIza|ya29|eyJ)[A-Za-z0-9._~+/=-]{12,}\b/g, '[secret]')
    .replace(/\b[0-9a-f]{24}\b/gi, '[object_id]')
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, '[uuid]');
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function flattenPromptCases(promptBank) {
  return (promptBank.families || []).flatMap((family) =>
    (family.cases || []).map((testCase) => {
      const familySemanticJudge = family.semanticJudge === true;
      return {
        familyId: family.id,
        familyGoal: family.goal,
        ...testCase,
        familySemanticJudge,
        semanticJudge: familySemanticJudge || testCase.semanticJudge === true,
        promptRefs: [
          ...new Set([
            ...(Array.isArray(family.promptRefs) ? family.promptRefs : []),
            ...(Array.isArray(testCase.promptRefs) ? testCase.promptRefs : []),
          ]),
        ],
        decisionQualityContract: {
          ...(family.decisionQualityContract || {}),
          ...(testCase.decisionQualityContract || {}),
        },
      };
    }),
  );
}

function selectPromptCases(promptBank, args = {}) {
  if ((args.duplicateSelectors || []).length > 0) {
    throw new Error('native_surface_case_selection_duplicate_selector');
  }
  if (args.maxCasesInvalid) {
    throw new Error('native_surface_case_selection_invalid_max_cases');
  }
  if (
    (args.familySpecified && !args.family) ||
    (args.caseIdSpecified && !args.caseId) ||
    (args.surfaceSpecified && !args.surface) ||
    (args.promptIdSpecified && !args.promptId)
  ) {
    throw new Error('native_surface_case_selection_empty_selector');
  }
  if (args.caseIdSpecified && args.caseIdsSpecified) {
    throw new Error('native_surface_case_selection_conflict');
  }
  if (args.caseIdsSpecified && args.caseIds.length === 0) {
    throw new Error('native_surface_case_selection_empty_requested_ids');
  }
  if (args.caseIdsMalformed) {
    throw new Error('native_surface_case_selection_malformed_requested_ids');
  }
  if (new Set(args.caseIds || []).size !== (args.caseIds || []).length) {
    throw new Error('native_surface_case_selection_duplicate');
  }
  let cases = flattenPromptCases(promptBank);
  if (args.family) {
    cases = cases.filter((testCase) => testCase.familyId === args.family);
  }
  if (args.caseId) {
    cases = cases.filter((testCase) => testCase.id === args.caseId);
  }
  if (args.caseIdsSpecified) {
    const requested = new Set(args.caseIds);
    cases = cases.filter((testCase) => requested.has(testCase.id));
  }
  if (args.surface) {
    cases = cases.filter((testCase) => (testCase.surface || 'web') === args.surface);
  }
  if (args.promptId) {
    cases = cases.filter((testCase) => testCase.promptRefs.includes(args.promptId));
  }
  if (args.caseIdsSpecified) {
    const byId = new Map();
    for (const testCase of cases) {
      const matches = byId.get(testCase.id) || [];
      matches.push(testCase);
      byId.set(testCase.id, matches);
    }
    const missing = args.caseIds.filter((caseId) => !byId.has(caseId));
    if (missing.length > 0) {
      throw new Error(`native_surface_case_selection_missing:${missing.join(',')}`);
    }
    if (args.caseIds.some((caseId) => byId.get(caseId).length !== 1)) {
      throw new Error('native_surface_case_selection_ambiguous');
    }
    if (args.maxCases < args.caseIds.length) {
      throw new Error('native_surface_case_selection_truncated');
    }
    return args.caseIds.map((caseId) => byId.get(caseId)[0]);
  }
  if (cases.length === 0) {
    throw new Error('native_surface_case_selection_empty');
  }
  if (args.caseId && cases.length !== 1) {
    throw new Error('native_surface_case_selection_ambiguous');
  }
  return cases.slice(0, args.maxCases || Number.MAX_SAFE_INTEGER);
}

function caseRequiresSemanticJudge(testCase) {
  return (
    testCase?.familySemanticJudge === true ||
    testCase?.semanticJudge === true ||
    testCase?.decisionQualityContract?.transportPassIsSemanticPass === false
  );
}

function assertNativeLiveRunRequested(args = {}) {
  if (args.runLive !== true) {
    throw new Error('native_surface_live_run_not_authorized');
  }
}

function buildPromptFrameRequestIdentityHash({ ownerId, surface, sourceEventId } = {}) {
  const normalizedOwnerId = String(ownerId || '').trim();
  const normalizedSurface = String(surface || '')
    .trim()
    .toLowerCase();
  const normalizedSourceEventId = String(sourceEventId || '').trim();
  if (!normalizedOwnerId || !normalizedSurface || !normalizedSourceEventId) {
    throw new Error('prompt_frame_request_identity_context_invalid');
  }
  return hashValue(
    [
      'viventium.prompt-frame-request.v1',
      normalizedOwnerId,
      normalizedSurface,
      normalizedSourceEventId,
    ].join('\0'),
  );
}

function buildTelegramSourceOrderScope({
  ownerId,
  telegramUserId,
  telegramChatId,
  messageThreadId = '',
} = {}) {
  const values = [ownerId, telegramUserId, telegramChatId].map((value) =>
    String(value || '').trim(),
  );
  if (values.some((value) => !value)) {
    throw new Error('telegram_source_order_identity_invalid');
  }
  return crypto
    .createHash('sha256')
    .update(
      [
        'viventium.telegram-source-order.v2',
        'telegram-interactive-v1',
        ...values,
        String(messageThreadId || '').trim(),
      ].join('\0'),
    )
    .digest('hex');
}

function buildTelegramSourceEventId({ sourceOrderScope, sourceSequence } = {}) {
  if (
    !/^[0-9a-f]{64}$/.test(String(sourceOrderScope || '')) ||
    !Number.isSafeInteger(sourceSequence) ||
    sourceSequence <= 0
  ) {
    throw new Error('telegram_source_event_identity_invalid');
  }
  return crypto
    .createHash('sha256')
    .update(
      [
        'viventium.telegram-source-event.v1',
        String(sourceOrderScope),
        String(sourceSequence),
      ].join('\0'),
    )
    .digest('hex');
}

function nextTelegramSourceSequence() {
  const candidate = Date.now() * 1000 + crypto.randomInt(0, 1000);
  lastTelegramSourceSequence = Math.max(candidate, lastTelegramSourceSequence + 1);
  if (!Number.isSafeInteger(lastTelegramSourceSequence)) {
    throw new Error('telegram_source_sequence_overflow');
  }
  return lastTelegramSourceSequence;
}

function trustedCompletionSurface(nativeSurface) {
  const normalized = String(nativeSurface || 'web').trim() || 'web';
  if (normalized === 'scheduler') {
    return 'workbench';
  }
  if (normalized === 'wing' || normalized === 'listen_only') {
    return 'voice';
  }
  return normalized;
}

function completionPromptFrames(frames) {
  return (frames || []).filter(
    (frame) =>
      frame?.event === 'viventium.prompt_frame' &&
      COMPLETION_PROMPT_FAMILIES.has(String(frame.prompt_family || '')),
  );
}

function promptFramesForRequest(frames, requestIdentityHash) {
  const expectedRequestIdentityHash = String(requestIdentityHash || '').trim().toLowerCase();
  if (!/^[0-9a-f]{16}$/.test(expectedRequestIdentityHash)) {
    return [];
  }
  return (frames || []).filter(
    (frame) =>
      frame?.event === 'viventium.prompt_frame' &&
      frame.request_identity_hash === expectedRequestIdentityHash,
  );
}

function completionPromptFramesForRequest(frames, requestIdentityHash) {
  return completionPromptFrames(promptFramesForRequest(frames, requestIdentityHash));
}

function assertCompletionPromptFrameSurface(frames, requestedSurface, requestIdentityHash) {
  const expected = String(requestedSurface || 'web').trim() || 'web';
  const expectedRequestIdentityHash = String(requestIdentityHash || '').trim().toLowerCase();
  if (!/^[0-9a-f]{16}$/.test(expectedRequestIdentityHash)) {
    throw new Error('completion_prompt_frame_request_identity_expected_invalid');
  }
  const allCompletionFrames = completionPromptFrames(frames);
  if (allCompletionFrames.length === 0) {
    throw new Error('completion_prompt_frame_missing');
  }
  if (
    allCompletionFrames.some(
      (frame) => !/^[0-9a-f]{16}$/.test(String(frame.request_identity_hash || '')),
    )
  ) {
    throw new Error('completion_prompt_frame_request_identity_missing');
  }
  const completionFrames = completionPromptFramesForRequest(
    allCompletionFrames,
    expectedRequestIdentityHash,
  );
  if (completionFrames.length === 0) {
    throw new Error('completion_prompt_frame_request_identity_unrelated_only');
  }
  const observed = [...new Set(completionFrames.map((frame) => String(frame.surface || '')))].sort();
  if (observed.length !== 1 || observed[0] !== expected) {
    throw new Error('completion_prompt_frame_surface_mismatch');
  }
  const observedAgentIdHashes = completionFrames.map((frame) =>
    String(frame.agent_id_hash || '').toLowerCase(),
  );
  const agentIdHashes = [...new Set(observedAgentIdHashes)];
  if (
    observedAgentIdHashes.some((value) => !/^[0-9a-f]{16}$/.test(value)) ||
    agentIdHashes.length !== 1
  ) {
    throw new Error(
      observedAgentIdHashes.some((value) => !/^[0-9a-f]{16}$/.test(value))
        ? 'completion_prompt_frame_agent_identity_missing'
        : 'completion_prompt_frame_agent_identity_mixed',
    );
  }
  const providers = completionFrames.map((frame) => String(frame.provider || '').trim());
  const models = completionFrames.map((frame) => String(frame.model || '').trim());
  const requestedProviders = completionFrames.map((frame) =>
    String(frame.requested_provider || '').trim(),
  );
  const requestedModels = completionFrames.map((frame) =>
    String(frame.requested_model || '').trim(),
  );
  const requestedEfforts = completionFrames.map((frame) =>
    String(frame.requested_effort || '').trim(),
  );
  const effectiveEfforts = completionFrames.map((frame) =>
    String(frame.effective_effort || '').trim(),
  );
  const fallbackReasons = completionFrames.map((frame) =>
    String(frame.fallback_reason || '').trim(),
  );
  if (
    providers.some((value) => !value || ['missing', 'none', 'unknown'].includes(value.toLowerCase())) ||
    models.some((value) => !value || ['missing', 'none', 'unknown'].includes(value.toLowerCase())) ||
    requestedProviders.some(
      (value) => !value || ['missing', 'none', 'unknown'].includes(value.toLowerCase()),
    ) ||
    requestedModels.some(
      (value) => !value || ['missing', 'none', 'unknown'].includes(value.toLowerCase()),
    ) ||
    requestedEfforts.some((value) => !value || ['missing', 'unknown'].includes(value.toLowerCase())) ||
    effectiveEfforts.some((value) => !value || ['missing', 'unknown'].includes(value.toLowerCase())) ||
    fallbackReasons.some((value) => !value || ['missing', 'unknown'].includes(value.toLowerCase()))
  ) {
    throw new Error('completion_prompt_frame_route_identity_missing');
  }
  const fallbackUsedValues = [...new Set(completionFrames.map((frame) => frame.fallback_used))];
  if (
    fallbackUsedValues.some((value) => typeof value !== 'boolean') ||
    fallbackUsedValues.length !== 1 ||
    (fallbackUsedValues[0]
      ? fallbackReasons.some((value) => value === 'none')
      : fallbackReasons.some((value) => value !== 'none'))
  ) {
    throw new Error('completion_prompt_frame_fallback_lineage_invalid');
  }
  const completionProviderHashes = [
    ...new Set(providers.map((value) => hashValue(value))),
  ].sort();
  const completionModelHashes = [
    ...new Set(models.map((value) => hashValue(value))),
  ].sort();
  return {
    verified: true,
    requestedSurface: expected,
    observedSurface: observed[0],
    completionFrameCount: completionFrames.length,
    requestIdentityHash: expectedRequestIdentityHash,
    actualCompletionAgentIdHash: agentIdHashes[0],
    completionProviderHashes,
    completionModelHashes,
    requestedProviderHashes: [...new Set(requestedProviders.map((value) => hashValue(value)))].sort(),
    requestedModelHashes: [...new Set(requestedModels.map((value) => hashValue(value)))].sort(),
    requestedEfforts: [...new Set(requestedEfforts)].sort(),
    effectiveEfforts: [...new Set(effectiveEfforts)].sort(),
    fallbackUsed: fallbackUsedValues[0],
    fallbackReasons: [...new Set(fallbackReasons)].sort(),
  };
}

function completionEvidenceForCase(
  frames,
  requestedSurface,
  requestIdentityHash,
  completionExpected = true,
) {
  const expectedRequestIdentityHash = String(requestIdentityHash || '').trim().toLowerCase();
  if (!/^[0-9a-f]{16}$/.test(expectedRequestIdentityHash)) {
    throw new Error('completion_prompt_frame_request_identity_expected_invalid');
  }
  if (completionExpected) {
    return {
      completionExpected: true,
      ...assertCompletionPromptFrameSurface(
        frames,
        requestedSurface,
        expectedRequestIdentityHash,
      ),
    };
  }
  const allCompletionFrames = completionPromptFrames(frames);
  if (
    allCompletionFrames.some(
      (frame) => !/^[0-9a-f]{16}$/.test(String(frame.request_identity_hash || '')),
    )
  ) {
    throw new Error('completion_prompt_frame_request_identity_missing');
  }
  const observed = completionPromptFramesForRequest(frames, expectedRequestIdentityHash);
  if (observed.length > 0) {
    throw new Error('unexpected_completion_prompt_frame');
  }
  return {
    completionExpected: false,
    verified: true,
    requestedSurface: String(requestedSurface || 'web').trim() || 'web',
    observedSurface: 'none',
    completionFrameCount: 0,
    requestIdentityHash: expectedRequestIdentityHash,
    actualCompletionAgentIdHash: 'not_applicable',
    completionProviderHashes: [],
    completionModelHashes: [],
  };
}

function caseAllowsEmpty(testCase) {
  return (
    testCase.expected_surface === '{NTA}' ||
    testCase.expected_decision === 'suppress' ||
    testCase.surface === 'listen_only' ||
    testCase.surface === 'wing'
  );
}

function caseAllowsDuplicateResponse(testCase) {
  return caseAllowsEmpty(testCase) || testCase.allow_duplicate_response_hash === true;
}

function caseAllowsUnresolvedAsync(testCase) {
  return testCase.allow_unresolved_async === true;
}

function isPendingCortexStatus(status) {
  return ['activating', 'brewing', 'running', 'pending'].includes(String(status || '').trim());
}

function resultHasResolvedRuntimeHoldEvidence(item) {
  return (
    item?.hasRuntimeHold &&
    item?.hasCortexActivation &&
    (Number(item.delayedFollowUpCount || 0) > 0 ||
      Number(item.cortexInsightCount || 0) > 0)
  );
}

function structuredDecisionCaseText(testCase) {
  if (
    !testCase?.question ||
    !testCase?.evidencePacket ||
    Object.keys(testCase.evidencePacket).length === 0
  ) {
    return null;
  }
  return [
    `User position: ${testCase.userPosition || 'No position stated.'}`,
    `Question: ${testCase.question}`,
    'Evidence packet:',
    ...Object.entries(testCase.evidencePacket).map(
      ([label, value]) => `- ${label}: ${String(value)}`,
    ),
    `Response instructions: ${testCase.responseInstructions || 'Give the strongest conclusion the evidence supports and the best next action.'}`,
  ].join('\n');
}

function buildText(testCase) {
  return [
    testCase.context,
    normalizeSeedPrompts(testCase).length ? null : testCase.setup,
    structuredDecisionCaseText(testCase) || testCase.prompt,
  ].filter(Boolean).join('\n\n');
}

function normalizeSeedPrompts(testCase) {
  if (Array.isArray(testCase.seed_prompts)) {
    return testCase.seed_prompts.map((item) => String(item || '').trim()).filter(Boolean);
  }
  return [];
}

function baseChatPayload(testCase, args, overrides = {}) {
  const messageId = overrides.messageId || crypto.randomUUID();
  return {
    text: overrides.text ?? buildText(testCase),
    sender: 'User',
    clientTimestamp: new Date().toISOString(),
    clientTimezone: 'America/Toronto',
    isCreatedByUser: true,
    parentMessageId: overrides.parentMessageId || NO_PARENT,
    conversationId: overrides.conversationId || 'new',
    messageId,
    responseMessageId: `${messageId}_`,
    endpoint: 'agents',
    endpointType: 'agents',
    agent_id: args.agentId,
    model: args.agentId,
    viventiumSurface: testCase.surface || 'web',
    viventiumInputMode: testCase.surface === 'voice' ? 'voice' : 'text',
    viventiumQaRun: true,
    viventiumQaRunId: args.qaRunId,
    isTemporary: true,
  };
}

async function fetchJson(url, options = {}, timeoutMs = 30_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = { raw: text };
    }
    return { ok: response.ok, status: response.status, body, text };
  } catch (error) {
    return { ok: false, status: 0, body: { error: error.message }, text: error.message };
  } finally {
    clearTimeout(timer);
  }
}

function parseSseBlock(block) {
  const lines = block.split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
    }
  }
  if (!dataLines.length) {
    return null;
  }
  try {
    return JSON.parse(dataLines.join('\n'));
  } catch {
    return { raw: dataLines.join('\n') };
  }
}

function extractTextFromContent(content) {
  if (typeof content === 'string') {
    return content;
  }
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') {
          return part;
        }
        if (part?.type === 'text') {
          if (typeof part.text === 'string') {
            return part.text;
          }
          if (typeof part.text?.value === 'string') {
            return part.text.value;
          }
        }
        return '';
      })
      .filter(Boolean)
      .join('\n\n');
  }
  if (typeof content?.text === 'string') {
    return content.text;
  }
  return '';
}

function extractVisibleText(events) {
  const finalEvent = [...events].reverse().find((event) => event && event.final != null);
  const responseMessage = finalEvent?.responseMessage || finalEvent?.message || null;
  const finalText =
    responseMessage?.text ||
    responseMessage?.textOverride ||
    extractTextFromContent(responseMessage?.content);
  if (typeof finalText === 'string' && finalText.trim()) {
    return finalText;
  }
  return events
    .map(
      (event) =>
        event?.text ||
        extractTextFromContent(event?.data?.delta?.content) ||
        (typeof event?.data?.delta?.text === 'string' ? event.data.delta.text : '') ||
        (typeof event?.delta === 'string' ? event.delta : '') ||
        event?.content ||
        event?.response?.text ||
        (typeof event?.responseMessage?.text === 'string' && event.responseMessage.text.trim()
          ? event.responseMessage.text
          : '') ||
        extractTextFromContent(event?.responseMessage?.content) ||
        '',
    )
    .filter((value) => typeof value === 'string')
    .join('');
}

function extractFinalStreamError(events) {
  const finalEvent = [...(events || [])].reverse().find((event) => event && event.final != null);
  if (!finalEvent) return null;
  if (finalEvent.error != null) return finalEvent.error;
  const content = finalEvent.responseMessage?.content;
  if (!Array.isArray(content)) return null;
  for (const part of content) {
    if (part?.type !== 'error') continue;
    const code = String(
      part.error_class || part.errorClass || part.error_code || part.code || '',
    )
      .trim()
      .toLowerCase();
    return /^[a-z0-9_.:-]{1,120}$/.test(code) ? code : 'final_response_error';
  }
  return null;
}

function extractFinalMeta(events) {
  const finalEvent = [...(events || [])].reverse().find((event) => event && event.final != null);
  return {
    conversationId:
      finalEvent?.conversation?.conversationId ||
      finalEvent?.responseMessage?.conversationId ||
      finalEvent?.message?.conversationId ||
      '',
    responseMessageId: finalEvent?.responseMessage?.messageId || finalEvent?.message?.messageId || '',
    requestMessageId: finalEvent?.requestMessage?.messageId || '',
  };
}

function contentToText(value) {
  if (!value) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === 'string') {
          return part;
        }
        if (part?.type === 'text' && typeof part.text === 'string') {
          return part.text;
        }
        if (part?.type === 'cortex_insight' && typeof part.insight === 'string') {
          return `[${part.cortex_name || 'cortex'} insight] ${part.insight}`;
        }
        return '';
      })
      .filter(Boolean)
      .join('\n');
  }
  if (typeof value.text === 'string') {
    return value.text;
  }
  return '';
}

function hasCortexActivation(events) {
  return (events || []).some((event) => {
    if (event?.event === 'on_cortex_update') {
      return true;
    }
    return JSON.stringify(event || {}).includes('cortex_activation');
  });
}

function hasRuntimeHold(events) {
  return (events || []).some((event) => {
    if (event?.final !== true || !Array.isArray(event.responseMessage?.content)) {
      return false;
    }
    return event.responseMessage.content.some((part) => Boolean(part?.viventium_runtime_hold));
  });
}

function summarizeNativeEventsForJudge(events) {
  const toolCalls = [];
  const cortexUpdates = [];
  const finalContent = [];
  const webSearchSources = [];
  for (const event of events || []) {
    if (event?.event === 'on_cortex_update' && event.data && typeof event.data === 'object') {
      cortexUpdates.push({
        type: scrubForPublic(event.data.type || ''),
        cortex_name: scrubForPublic(event.data.cortex_name || ''),
        status: scrubForPublic(event.data.status || ''),
        reason: scrubForPublic(event.data.reason || ''),
        activation_scope: scrubForPublic(event.data.activation_scope || ''),
      });
    }
    if (event?.event === 'attachment' && event?.data?.type === 'web_search') {
      const organic = Array.isArray(event.data.web_search?.organic)
        ? event.data.web_search.organic
        : [];
      const turn = Number.isFinite(Number(event.data.web_search?.turn))
        ? Number(event.data.web_search.turn)
        : 0;
      for (const source of organic.slice(0, 8)) {
        const position = Number.isFinite(Number(source.position)) ? Number(source.position) : 0;
        webSearchSources.push({
          anchor: position > 0 ? `turn${turn}search${position - 1}` : '',
          title: scrubForPublic(source.title || ''),
          attribution: scrubForPublic(source.attribution || ''),
          link_host: scrubForPublic(
            (() => {
              try {
                return new URL(source.link || '').hostname;
              } catch {
                return '';
              }
            })(),
          ),
          processed: Boolean(source.processed),
          snippet_preview: scrubForPublic(String(source.snippet || '').slice(0, 240)),
        });
      }
    }
    const stepDetails = event?.data?.stepDetails || event?.data?.result || {};
    const rawToolCalls =
      stepDetails?.tool_calls ||
      stepDetails?.tool_call ||
      stepDetails?.toolCalls ||
      stepDetails?.toolCall ||
      [];
    const normalizedToolCalls = Array.isArray(rawToolCalls) ? rawToolCalls : [rawToolCalls];
    for (const call of normalizedToolCalls) {
      if (!call || typeof call !== 'object') {
        continue;
      }
      const toolCall = call.tool_call || call;
      const outputText =
        typeof toolCall.output === 'string'
          ? toolCall.output
          : typeof toolCall.result === 'string'
            ? toolCall.result
            : '';
      toolCalls.push({
        event: scrubForPublic(event.event || ''),
        name: scrubForPublic(toolCall.name || call.name || ''),
        has_output: Boolean(outputText),
        output_preview: scrubForPublic(outputText.slice(0, 500)),
      });
    }
    if (event?.final === true && Array.isArray(event.responseMessage?.content)) {
      for (const part of event.responseMessage.content) {
        if (!part || typeof part !== 'object') {
          continue;
        }
        finalContent.push({
          type: scrubForPublic(part.type || ''),
          cortex_name: scrubForPublic(part.cortex_name || ''),
          status: scrubForPublic(part.status || ''),
          reason: scrubForPublic(part.reason || ''),
          activation_scope: scrubForPublic(part.activation_scope || ''),
          runtime_hold: Boolean(part.viventium_runtime_hold),
        });
      }
    }
  }
  return scrubForPublic(
    JSON.stringify(
      {
        tool_calls: toolCalls.slice(0, 20),
        web_search_sources: webSearchSources.slice(0, 30),
        cortex_updates: cortexUpdates.slice(0, 20),
        final_content: finalContent.slice(0, 20),
      },
      null,
      2,
    ),
  );
}

async function readSseToFinal({ url, headers = {}, timeoutMs }) {
  const response = await fetch(url, { headers: { 'User-Agent': USER_AGENT, ...headers } });
  if (!response.ok || !response.body) {
    return {
      ok: false,
      status: response.status,
      events: [],
      text: '',
      error: `stream_http_${response.status}`,
    };
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  const startedAt = Date.now();
  let buffer = '';
  const events = [];
  try {
    while (Date.now() - startedAt < timeoutMs) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\n\n/);
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        const event = parseSseBlock(block);
        if (!event) {
          continue;
        }
        events.push(event);
        if (event.final != null || event.error != null) {
          const streamError = event.error || extractFinalStreamError(events);
          await reader.cancel().catch(() => {});
          return {
            ok: streamError == null,
            status: response.status,
            events,
            text: extractVisibleText(events),
            error: streamError || null,
          };
        }
      }
    }
  } catch (error) {
    return {
      ok: false,
      status: response.status,
      events,
      text: extractVisibleText(events),
      error: `stream_read_failed:${error.message || error.name || 'unknown'}`,
    };
  }
  await reader.cancel().catch(() => {});
  return {
    ok: false,
    status: response.status,
    events,
    text: extractVisibleText(events),
    error: 'stream_timeout',
  };
}

function collectFrameOffsets() {
  const offsets = {};
  if (!fs.existsSync(FRAME_ROOT)) {
    return offsets;
  }
  for (const dateDir of fs.readdirSync(FRAME_ROOT)) {
    const fullDir = path.join(FRAME_ROOT, dateDir);
    if (!fs.statSync(fullDir).isDirectory()) {
      continue;
    }
    for (const fileName of fs.readdirSync(fullDir)) {
      if (!fileName.endsWith('.jsonl')) {
        continue;
      }
      const filePath = path.join(fullDir, fileName);
      offsets[filePath] = fs.statSync(filePath).size;
    }
  }
  return offsets;
}

function readFrameDelta(beforeOffsets) {
  const frames = [];
  const afterOffsets = collectFrameOffsets();
  for (const [filePath, size] of Object.entries(afterOffsets)) {
    const start = beforeOffsets[filePath] || 0;
    if (size <= start) {
      continue;
    }
    const fd = fs.openSync(filePath, 'r');
    try {
      const buffer = Buffer.alloc(size - start);
      fs.readSync(fd, buffer, 0, buffer.length, start);
      for (const line of buffer.toString('utf8').split(/\r?\n/)) {
        if (!line.trim()) {
          continue;
        }
        try {
          frames.push(JSON.parse(line));
        } catch {
          frames.push({ parse_error: true, raw_hash: hashValue(line) });
        }
      }
    } finally {
      fs.closeSync(fd);
    }
  }
  return { frames, afterOffsets };
}

function summarizeFrames(frames) {
  const surfaces = [...new Set(frames.map((frame) => frame.surface).filter(Boolean))].sort();
  const families = [...new Set(frames.map((frame) => frame.prompt_family).filter(Boolean))].sort();
  const models = [...new Set(frames.map((frame) => frame.model).filter(Boolean))].sort();
  const layers = {};
  for (const frame of frames) {
    for (const [layer, tokens] of Object.entries(frame.layer_token_estimates || {})) {
      layers[layer] = Math.max(layers[layer] || 0, Number(tokens) || 0);
    }
  }
  return { surfaces, families, models, layers, frameCount: frames.length };
}

function assertSelectedSyntheticQaUser({ qaEmail, ownerEmail, user }) {
  const selectedEmail = String(user?.email || '').trim().toLowerCase();
  const expectedQaEmail = String(qaEmail || '').trim().toLowerCase();
  const personalOwnerEmail = String(ownerEmail || '').trim().toLowerCase();
  if (!personalOwnerEmail) {
    throw new Error('personal_owner_identity_guard_required');
  }
  if (!user?._id || !expectedQaEmail || selectedEmail !== expectedQaEmail) {
    throw new Error('selected_synthetic_qa_account_mismatch');
  }
  if (selectedEmail === personalOwnerEmail) {
    throw new Error('personal_owner_account_refused');
  }
  const role = String(user.role || '').trim().toUpperCase();
  if (role === 'ADMIN') {
    throw new Error('admin_qa_account_refused');
  }
  if (role !== 'USER') {
    throw new Error('non_admin_synthetic_qa_role_required');
  }
  const emailParts = selectedEmail.split('@');
  if (
    emailParts.length !== 2 ||
    !emailParts[0] ||
    !new Set(['example.com', 'viventium.local', 'localhost']).has(emailParts[1])
  ) {
    throw new Error('synthetic_qa_account_required');
  }
  if (user.viventiumApprovalStatus !== 'approved') {
    throw new Error('approved_synthetic_qa_account_required');
  }
  if (
    user.locked === true ||
    user.isLocked === true ||
    user.banned === true
  ) {
    throw new Error('unavailable_qa_account_refused');
  }
  return String(user._id);
}

function normalizeIdentifierSet(values) {
  return new Set(
    [...(values || [])]
      .map((value) => String(value || '').trim())
      .filter((value) => value && value !== 'new'),
  );
}

async function cleanupExactQaArtifacts({
  db,
  qaUser,
  qaEmail,
  ownerEmail,
  qaRunId,
  runStartedAt,
  sessionRecord,
  mappingState,
  preexistingConversationIds,
  trackedConversationIds,
}) {
  const userId = assertSelectedSyntheticQaUser({ qaEmail, ownerEmail, user: qaUser });
  const startedAt = runStartedAt instanceof Date ? runStartedAt : new Date(runStartedAt || 0);
  const runId = String(qaRunId || '').trim();
  if (
    !db ||
    typeof db.collection !== 'function' ||
    Number.isNaN(startedAt.getTime()) ||
    !/^[A-Za-z0-9._:-]{1,128}$/.test(runId)
  ) {
    throw new Error('native_surface_qa_cleanup_context_invalid');
  }

  const failures = [];
  let removedMessageCount = 0;
  let removedConversationCount = 0;
  let removedSessionCount = 0;
  let mappingAction = 'skipped';

  try {
    const tracked = normalizeIdentifierSet(trackedConversationIds);
    const preexisting = normalizeIdentifierSet(preexistingConversationIds);
    const messages = await db
      .collection('messages')
      .find({
        user: userId,
        createdAt: { $gte: startedAt },
        'metadata.viventium.qaRun': true,
        'metadata.viventium.qaRunId': runId,
      })
      .limit(MAX_QA_CLEANUP_ROWS + 1)
      .toArray();
    if (messages.length > MAX_QA_CLEANUP_ROWS) {
      throw new Error('qa_cleanup_message_limit_exceeded');
    }
    if ([...tracked].some((conversationId) => preexisting.has(conversationId))) {
      throw new Error('qa_cleanup_preexisting_conversation_refused');
    }
    const scopedConversationIds = new Set(
      messages.map((message) => String(message?.conversationId || '').trim()).filter(Boolean),
    );
    const unprovenTrackedIds = [...tracked].filter(
      (conversationId) => !scopedConversationIds.has(conversationId),
    );
    if (unprovenTrackedIds.length > 0) {
      const unprovenRows = await db
        .collection('conversations')
        .find({ user: userId, conversationId: { $in: unprovenTrackedIds } })
        .limit(unprovenTrackedIds.length + 1)
        .toArray();
      if (unprovenRows.length > 0) {
        throw new Error('qa_cleanup_unproven_conversation_refused');
      }
    }
    for (const message of messages) {
      const createdAtMs = new Date(message?.createdAt || 0).getTime();
      if (
        !message?._id ||
        String(message.user || '') !== userId ||
        !scopedConversationIds.has(String(message.conversationId || '')) ||
        !Number.isFinite(createdAtMs) ||
        createdAtMs < startedAt.getTime() ||
        message?.metadata?.viventium?.qaRun !== true ||
        message?.metadata?.viventium?.qaRunId !== runId
      ) {
        throw new Error('qa_cleanup_message_scope_invalid');
      }
    }

    const conversations = scopedConversationIds.size
      ? await db
          .collection('conversations')
          .find({ user: userId, conversationId: { $in: [...scopedConversationIds] } })
          .limit(scopedConversationIds.size + 1)
          .toArray()
      : [];
    if (conversations.length > scopedConversationIds.size) {
      throw new Error('qa_cleanup_conversation_scope_ambiguous');
    }
    for (const conversation of conversations) {
      if (
        !conversation?._id ||
        String(conversation.user || '') !== userId ||
        !scopedConversationIds.has(String(conversation.conversationId || ''))
      ) {
        throw new Error('qa_cleanup_conversation_scope_invalid');
      }
    }
    for (const conversationId of scopedConversationIds) {
      const expectedCount = messages.filter(
        (message) => String(message.conversationId || '') === conversationId,
      ).length;
      const actualCount = await db
        .collection('messages')
        .countDocuments({ user: userId, conversationId });
      if (actualCount !== expectedCount) {
        throw new Error('qa_cleanup_conversation_contains_unowned_rows');
      }
    }

    for (const message of messages) {
      const removed = await db.collection('messages').deleteOne({
        _id: message._id,
        user: userId,
        conversationId: message.conversationId,
        'metadata.viventium.qaRun': true,
        'metadata.viventium.qaRunId': runId,
      });
      if (removed?.deletedCount !== 1) {
        throw new Error('qa_cleanup_message_delete_unverified');
      }
      removedMessageCount += 1;
    }
    for (const conversation of conversations) {
      const remaining = await db.collection('messages').countDocuments({
        user: userId,
        conversationId: conversation.conversationId,
      });
      if (remaining !== 0) {
        throw new Error('qa_cleanup_conversation_not_empty');
      }
      const removed = await db.collection('conversations').deleteOne({
        _id: conversation._id,
        user: userId,
        conversationId: conversation.conversationId,
      });
      if (removed?.deletedCount !== 1) {
        throw new Error('qa_cleanup_conversation_delete_unverified');
      }
      removedConversationCount += 1;
    }
    const remainingRunMessages = await db.collection('messages').countDocuments({
      user: userId,
      'metadata.viventium.qaRun': true,
      'metadata.viventium.qaRunId': runId,
    });
    if (remainingRunMessages !== 0) {
      throw new Error('qa_cleanup_message_residue');
    }
  } catch (error) {
    failures.push(error.message || 'qa_cleanup_artifact_failure');
  }

  try {
    if (mappingState) {
      const telegramUserId = String(mappingState.telegramUserId || '');
      const current = await db.collection('telegramusermappings').findOne({ telegramUserId });
      if (
        !current?._id ||
        String(current._id) !== String(mappingState.currentId || '') ||
        String(current.libreChatUserId || '') !== userId ||
        current[QA_MAPPING_RUN_FIELD] !== runId
      ) {
        throw new Error('qa_cleanup_mapping_scope_invalid');
      }
      if (mappingState.originalDocument) {
        const restored = await db.collection('telegramusermappings').replaceOne(
          {
            _id: current._id,
            telegramUserId,
            libreChatUserId: qaUser._id,
            [QA_MAPPING_RUN_FIELD]: runId,
          },
          mappingState.originalDocument,
        );
        if (restored?.matchedCount !== 1) {
          throw new Error('qa_cleanup_mapping_restore_unverified');
        }
        const verified = await db.collection('telegramusermappings').findOne({
          _id: mappingState.originalDocument._id,
        });
        if (stableStringify(verified) !== stableStringify(mappingState.originalDocument)) {
          throw new Error('qa_cleanup_mapping_restore_mismatch');
        }
        mappingAction = 'restored';
      } else {
        const removed = await db.collection('telegramusermappings').deleteOne({
          _id: current._id,
          telegramUserId,
          libreChatUserId: qaUser._id,
          [QA_MAPPING_RUN_FIELD]: runId,
        });
        if (removed?.deletedCount !== 1) {
          throw new Error('qa_cleanup_mapping_delete_unverified');
        }
        const residue = await db.collection('telegramusermappings').findOne({
          _id: current._id,
        });
        if (residue) {
          throw new Error('qa_cleanup_mapping_delete_residue');
        }
        mappingAction = 'deleted';
      }
    }
  } catch (error) {
    failures.push(error.message || 'qa_cleanup_mapping_failure');
  }

  try {
    if (sessionRecord) {
      if (
        !sessionRecord._id ||
        String(sessionRecord.user || '') !== userId ||
        !String(sessionRecord.refreshTokenHash || '')
      ) {
        throw new Error('qa_cleanup_session_scope_invalid');
      }
      const removed = await db.collection('sessions').deleteOne({
        _id: sessionRecord._id,
        user: sessionRecord.user,
        refreshTokenHash: sessionRecord.refreshTokenHash,
      });
      if (removed?.deletedCount !== 1) {
        throw new Error('qa_cleanup_session_delete_unverified');
      }
      const residue = await db.collection('sessions').findOne({ _id: sessionRecord._id });
      if (residue) {
        throw new Error('qa_cleanup_session_delete_residue');
      }
      removedSessionCount = 1;
    }
  } catch (error) {
    failures.push(error.message || 'qa_cleanup_session_failure');
  }

  if (failures.length > 0) {
    const error = new Error(`native_surface_qa_cleanup_failed:${failures.join(',')}`);
    error.code = 'native_surface_qa_cleanup_failed';
    throw error;
  }
  return {
    cleaned: true,
    mappingAction,
    removedSessionCount,
    removedMessageCount,
    removedConversationCount,
  };
}

async function createQaAuth({ args, env }) {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    throw new Error('Local QA JWT auth is forbidden in CI or production');
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    throw new Error(`Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1`);
  }

  const mongoUri = env.MONGO_URI;
  const jwtSecret = env.JWT_SECRET;
  const jwtRefreshSecret = env.JWT_REFRESH_SECRET;
  const configuredQaEmail = String(env.VIVENTIUM_QA_EMAIL || '').trim().toLowerCase();
  const ownerEmail = String(env.VIVENTIUM_QA_OWNER_EMAIL || '').trim().toLowerCase();
  if (!mongoUri || !jwtSecret || !jwtRefreshSecret || !configuredQaEmail || !ownerEmail) {
    throw new Error('Missing local QA auth prerequisites');
  }
  if (configuredQaEmail !== String(args.qaEmail || '').trim().toLowerCase()) {
    throw new Error('configured_synthetic_qa_account_mismatch');
  }

  const { MongoClient, ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
  const client = new MongoClient(mongoUri);
  const runStartedAt = new Date();
  let db = null;
  let user = null;
  let sessionRecord = null;
  let mappingState = null;
  let preexistingConversationIds = new Set();
  try {
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
    db = client.db(dbName);
    user = await db.collection('users').findOne({ email: configuredQaEmail });
    const userId = assertSelectedSyntheticQaUser({
      qaEmail: configuredQaEmail,
      ownerEmail,
      user,
    });
    const existingConversations = await db
      .collection('conversations')
      .find({ user: userId })
      .project({ conversationId: 1 })
      .toArray();
    preexistingConversationIds = normalizeIdentifierSet(
      existingConversations.map((conversation) => conversation.conversationId),
    );

    const accessToken = jwt.sign(
      {
        id: userId,
        username: user.username,
        provider: user.provider,
        email: user.email,
      },
      jwtSecret,
      { expiresIn: '2h' },
    );

    const sessionId = new ObjectId();
    const expiration = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const refreshToken = jwt.sign(
      { id: userId, sessionId: sessionId.toString() },
      jwtRefreshSecret,
      { expiresIn: Math.floor((expiration.getTime() - Date.now()) / 1000) },
    );
    const refreshTokenHash = crypto.createHash('sha256').update(refreshToken).digest('hex');
    sessionRecord = {
      _id: sessionId,
      user: user._id,
      expiration,
      refreshTokenHash,
    };
    const sessionInsert = await db.collection('sessions').insertOne(sessionRecord);
    if (sessionInsert?.acknowledged !== true) {
      throw new Error('native_surface_qa_session_creation_failed');
    }

    const syntheticTelegramUserId = `qa_native_${hashValue(`${userId}:${args.agentId}`, 12)}`;
    const mappingCollection = db.collection('telegramusermappings');
    const originalMapping = await mappingCollection.findOne({
      telegramUserId: syntheticTelegramUserId,
    });
    if (originalMapping && String(originalMapping.libreChatUserId || '') !== userId) {
      throw new Error('synthetic_telegram_mapping_owner_mismatch');
    }
    const mappingDocument = {
      telegramUserId: syntheticTelegramUserId,
      telegramUsername: 'qa_native_surface',
      libreChatUserId: user._id,
      linkedAt: new Date(),
      lastSeenAt: new Date(),
      alwaysVoiceResponse: false,
      voiceResponsesEnabled: true,
      [QA_MAPPING_RUN_FIELD]: args.qaRunId,
    };
    if (originalMapping) {
      mappingState = {
        telegramUserId: syntheticTelegramUserId,
        currentId: originalMapping._id,
        originalDocument: originalMapping,
      };
      const updated = await mappingCollection.updateOne(
        {
          _id: originalMapping._id,
          telegramUserId: syntheticTelegramUserId,
          libreChatUserId: user._id,
        },
        { $set: mappingDocument },
      );
      if (updated?.matchedCount !== 1) {
        throw new Error('synthetic_telegram_mapping_update_failed');
      }
    } else {
      const inserted = await mappingCollection.insertOne(mappingDocument);
      if (inserted?.acknowledged !== true || !inserted.insertedId) {
        throw new Error('synthetic_telegram_mapping_creation_failed');
      }
      mappingState = {
        telegramUserId: syntheticTelegramUserId,
        currentId: inserted.insertedId,
        originalDocument: null,
      };
    }

    const trackedConversationIds = new Set();
    let cleanupPromise = null;
    const cleanup = () => {
      if (!cleanupPromise) {
        cleanupPromise = (async () => {
          try {
            return await cleanupExactQaArtifacts({
              db,
              qaUser: user,
              qaEmail: configuredQaEmail,
              ownerEmail,
              qaRunId: args.qaRunId,
              runStartedAt,
              sessionRecord,
              mappingState,
              preexistingConversationIds,
              trackedConversationIds,
            });
          } finally {
            await client.close();
          }
        })();
      }
      return cleanupPromise;
    };

    return {
      cleanup,
      trackCreatedConversations(values) {
        for (const value of values || []) {
          const conversationId = String(value?.conversationId || value || '').trim();
          if (!conversationId || conversationId === 'new') {
            continue;
          }
          if (preexistingConversationIds.has(conversationId)) {
            throw new Error('qa_run_reused_preexisting_conversation');
          }
          trackedConversationIds.add(conversationId);
        }
      },
      db,
      userId,
      userEmailHash: hashValue(user.email || ''),
      accessToken,
      refreshToken,
      sessionId: sessionId.toString(),
      syntheticTelegramUserId,
    };
  } catch (error) {
    let cleanupError = null;
    if (db && user && (sessionRecord || mappingState)) {
      try {
        await cleanupExactQaArtifacts({
          db,
          qaUser: user,
          qaEmail: configuredQaEmail,
          ownerEmail,
          qaRunId: args.qaRunId,
          runStartedAt,
          sessionRecord,
          mappingState,
          preexistingConversationIds,
          trackedConversationIds: new Set(),
        });
      } catch (candidate) {
        cleanupError = candidate;
      }
    }
    await client.close().catch(() => {});
    if (cleanupError) {
      const failure = new Error('native_surface_qa_setup_cleanup_failed');
      failure.cause = cleanupError;
      throw failure;
    }
    throw error;
  }
}

async function createCallSession({ args, token, requestedVoiceRoute = null }) {
  const response = await fetchJson(
    `${args.apiBase}/api/viventium/calls`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
      },
      body: JSON.stringify({
        conversationId: 'new',
        agentId: args.agentId,
        requestedVoiceRoute,
      }),
    },
    30_000,
  );
  if (!response.ok || !response.body?.callSessionId) {
    throw new Error(`call_session_http_${response.status}`);
  }
  return response.body;
}

async function runAgentsTurn({
  args,
  token,
  ownerId,
  testCase,
  text,
  conversationId = 'new',
  parentMessageId = NO_PARENT,
}) {
  const payload = baseChatPayload(testCase, args, { text, conversationId, parentMessageId });
  const requestIdentityHash = buildPromptFrameRequestIdentityHash({
    ownerId,
    surface: trustedCompletionSurface(testCase.surface),
    sourceEventId: payload.messageId,
  });
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      startStatus: start.status,
      text: '',
      error: `agents_start_http_${start.status}`,
      route: 'agents_api',
      requestIdentityHash,
      startBodyKeys: Object.keys(start.body || {}).slice(0, 20),
    };
  }
  const stream = await readSseToFinal({
    url: `${args.apiBase}/api/agents/chat/stream/${encodeURIComponent(start.body.streamId)}`,
    headers: { Authorization: `Bearer ${token}` },
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok && (stream.text.trim() || caseAllowsEmpty(testCase)),
    startStatus: start.status,
    streamStatus: stream.status,
    text: stream.text,
    error: stream.error,
    route: 'agents_api',
    requestIdentityHash,
    streamIdHash: hashValue(start.body.streamId),
    eventCount: stream.events.length,
    finalMeta: extractFinalMeta(stream.events),
    hasCortexActivation: hasCortexActivation(stream.events),
    hasRuntimeHold: hasRuntimeHold(stream.events),
    privateEvents: stream.events,
  };
}

async function runAgentsSurface({ args, token, ownerId, testCase }) {
  const seedPrompts = normalizeSeedPrompts(testCase);
  let conversationId = 'new';
  let parentMessageId = NO_PARENT;
  const seedEvidence = [];
  const cleanupFinalMetas = [];

  for (const seedText of seedPrompts) {
    const seed = await runAgentsTurn({
      args,
      token,
      ownerId,
      testCase,
      text: seedText,
      conversationId,
      parentMessageId,
    });
    seedEvidence.push({
      ok: seed.ok,
      responseHash: hashValue(seed.text || ''),
      eventCount: seed.eventCount || 0,
    });
    if (seed.finalMeta?.conversationId) {
      cleanupFinalMetas.push(seed.finalMeta);
    }
    if (!seed.ok || !seed.finalMeta?.conversationId || !seed.finalMeta?.responseMessageId) {
      return {
        ...seed,
        ok: false,
        route: 'agents_api',
        error: seed.error || 'seed_turn_failed',
        seedEvidence,
      };
    }
    conversationId = seed.finalMeta.conversationId;
    parentMessageId = seed.finalMeta.responseMessageId;
  }

  const result = await runAgentsTurn({
    args,
    token,
    ownerId,
    testCase,
    text: buildText(testCase),
    conversationId,
    parentMessageId,
  });
  if (result.finalMeta?.conversationId) {
    cleanupFinalMetas.push(result.finalMeta);
  }
  return { ...result, seedEvidence, cleanupFinalMetas };
}

async function runVoiceSurface({
  args,
  token,
  ownerId,
  env,
  testCase,
  listenOnly = false,
  wingMode = false,
}) {
  const session = await createCallSession({
    args,
    token,
    requestedVoiceRoute: {
      stt: { provider: 'browser', variant: 'qa-browser-stt' },
      tts: { provider: 'plain_tts', variant: 'qa-sink' },
    },
  });
  const headers = {
    'X-VIVENTIUM-CALL-SESSION': session.callSessionId,
    'X-VIVENTIUM-CALL-SECRET': env.VIVENTIUM_CALL_SESSION_SECRET || '',
    'X-VIVENTIUM-JOB-ID': `qa-${crypto.randomUUID()}`,
    'X-VIVENTIUM-WORKER-ID': 'native-surface-playwright-qa',
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT,
  };
  const sourceEventId = crypto.randomUUID();
  const requestIdentityHash = buildPromptFrameRequestIdentityHash({
    ownerId,
    surface: 'voice',
    sourceEventId,
  });

  if (listenOnly) {
    await fetchJson(
      `${args.apiBase}/api/viventium/calls/${encodeURIComponent(session.callSessionId)}/state`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ listenOnlyModeEnabled: true, touch: true }),
      },
      20_000,
    );
  }

  if (wingMode) {
    await fetchJson(
      `${args.apiBase}/api/viventium/calls/${encodeURIComponent(session.callSessionId)}/state`,
      {
        method: 'POST',
        headers,
        body: JSON.stringify({ wingModeEnabled: true, touch: true }),
      },
      20_000,
    );
  }

  const start = await fetchJson(
    `${args.apiBase}/api/viventium/voice/chat`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        text: buildText(testCase),
        viventiumSurface: wingMode ? 'wing' : listenOnly ? 'listen_only' : 'voice',
        viventiumInputMode: 'voice_call',
        voiceMode: true,
        voiceProvider: 'plain_tts',
        sourceEventId,
        viventiumQaRun: true,
        viventiumQaRunId: args.qaRunId,
      }),
    },
    30_000,
  );

  if (listenOnly) {
    return {
      ok: start.ok && start.body?.listenOnly === true,
      startStatus: start.status,
      text: '',
      route: 'voice_gateway_listen_only',
      requestIdentityHash,
      error: start.ok ? null : `listen_only_http_${start.status}`,
      statusBodyHash: hashValue(start.body || {}),
      callSessionHash: hashValue(session.callSessionId),
    };
  }

  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      startStatus: start.status,
      text: '',
      route: 'voice_gateway',
      requestIdentityHash,
      error: `voice_start_http_${start.status}`,
      startBodyKeys: Object.keys(start.body || {}).slice(0, 20),
      callSessionHash: hashValue(session.callSessionId),
    };
  }
  const stream = await readSseToFinal({
    url: `${args.apiBase}/api/viventium/voice/stream/${encodeURIComponent(start.body.streamId)}`,
    headers,
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok && (stream.text.trim() || caseAllowsEmpty(testCase)),
    startStatus: start.status,
    streamStatus: stream.status,
    text: stream.text,
    route: 'voice_gateway',
    requestIdentityHash,
    error: stream.error,
    streamIdHash: hashValue(start.body.streamId),
    callSessionHash: hashValue(session.callSessionId),
    eventCount: stream.events.length,
    finalMeta: extractFinalMeta(stream.events),
    hasCortexActivation: hasCortexActivation(stream.events),
    hasRuntimeHold: hasRuntimeHold(stream.events),
    privateEvents: stream.events,
  };
}

async function runTelegramSurface({ args, env, qaAuth, testCase }) {
  const sourceSequence = nextTelegramSourceSequence();
  const sourceOrderScope = buildTelegramSourceOrderScope({
    ownerId: qaAuth.userId,
    telegramUserId: qaAuth.syntheticTelegramUserId,
    telegramChatId: qaAuth.syntheticTelegramUserId,
  });
  const sourceEventId = buildTelegramSourceEventId({ sourceOrderScope, sourceSequence });
  const requestIdentityHash = buildPromptFrameRequestIdentityHash({
    ownerId: qaAuth.userId,
    surface: 'telegram',
    sourceEventId,
  });
  const body = {
    text: buildText(testCase),
    conversationId: 'new',
    agentId: args.agentId,
    telegramUserId: qaAuth.syntheticTelegramUserId,
    telegramChatId: qaAuth.syntheticTelegramUserId,
    telegramUsername: 'qa_native_surface',
    telegramMessageId: String(sourceSequence),
    telegramUpdateId: String(sourceSequence),
    telegramMessageThreadId: '',
    sourceSequence,
    sourceOrderScope,
    sourceEventId,
    traceId: `qa-${crypto.randomUUID()}`,
    voiceMode: testCase.surface === 'voice',
    viventiumQaRun: true,
    viventiumQaRunId: args.qaRunId,
  };
  const headers = {
    'X-VIVENTIUM-TELEGRAM-SECRET': env.VIVENTIUM_TELEGRAM_SECRET || '',
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT,
  };
  let sourceOrder;
  let start;
  try {
    ({ sourceOrder, start } = await startTelegramSurfaceTurn({ args, headers, body }));
  } catch (error) {
    return {
      ok: false,
      startStatus: 0,
      text: '',
      route: 'telegram_gateway',
      requestIdentityHash,
      sourceOrderObserved: false,
      error: scrubForPublic(error?.message || 'telegram_source_order_observation_unverified'),
    };
  }
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      startStatus: start.status,
      text: '',
      route: 'telegram_gateway',
      requestIdentityHash,
      sourceOrderObserved: true,
      sourceOrderReceiptHash: hashValue(stableStringify(sourceOrder)),
      error: `telegram_start_http_${start.status}`,
      startBodyKeys: Object.keys(start.body || {}).slice(0, 20),
    };
  }
  const stream = await readSseToFinal({
    url: `${args.apiBase}/api/viventium/telegram/stream/${encodeURIComponent(
      start.body.streamId,
    )}?telegramUserId=${encodeURIComponent(qaAuth.syntheticTelegramUserId)}`,
    headers,
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok && (stream.text.trim() || caseAllowsEmpty(testCase)),
    startStatus: start.status,
    streamStatus: stream.status,
    text: stream.text,
    route: 'telegram_gateway',
    requestIdentityHash,
    sourceOrderObserved: true,
    sourceOrderReceiptHash: hashValue(stableStringify(sourceOrder)),
    error: stream.error,
    streamIdHash: hashValue(start.body.streamId),
    eventCount: stream.events.length,
    finalMeta: extractFinalMeta(stream.events),
    hasCortexActivation: hasCortexActivation(stream.events),
    hasRuntimeHold: hasRuntimeHold(stream.events),
    privateEvents: stream.events,
  };
}

async function startTelegramSurfaceTurn({ args, headers, body, fetcher = fetchJson }) {
  const sourceSequence = Number(body?.sourceSequence);
  const sourceOrder = await fetcher(
    `${args.apiBase}/api/viventium/telegram/source-order`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        telegramUserId: body?.telegramUserId,
        telegramChatId: body?.telegramChatId,
        telegramMessageThreadId: body?.telegramMessageThreadId,
        telegramMessageId: body?.telegramMessageId,
        sourceSequence,
      }),
    },
    30_000,
  );
  if (
    !Number.isSafeInteger(sourceSequence) ||
    sourceSequence < 0 ||
    !sourceOrder.ok ||
    sourceOrder.body?.observed !== true ||
    sourceOrder.body?.stale !== false ||
    sourceOrder.body?.sourceOrderScope !== body?.sourceOrderScope ||
    sourceOrder.body?.sourceEventId !== body?.sourceEventId ||
    sourceOrder.body?.latestSourceSequence !== sourceSequence
  ) {
    throw new Error('telegram_source_order_observation_unverified');
  }
  const start = await fetcher(
    `${args.apiBase}/api/viventium/telegram/chat`,
    { method: 'POST', headers, body: JSON.stringify(body) },
    30_000,
  );
  return {
    sourceOrder: {
      observed: true,
      sourceOrderScope: sourceOrder.body.sourceOrderScope,
      sourceEventId: sourceOrder.body.sourceEventId,
      latestSourceSequence: sourceOrder.body.latestSourceSequence,
      stale: false,
      durability: scrubForPublic(sourceOrder.body.durability || ''),
      replicaSafe: sourceOrder.body.replicaSafe === true,
    },
    start,
  };
}

async function runSchedulerSurface({ args, env, qaAuth, testCase }) {
  const sourceEventId = crypto.randomUUID();
  const requestIdentityHash = buildPromptFrameRequestIdentityHash({
    ownerId: qaAuth.userId,
    surface: 'workbench',
    sourceEventId,
  });
  const headers = {
    'X-VIVENTIUM-SCHEDULER-SECRET': env.VIVENTIUM_SCHEDULER_SECRET || '',
    'Content-Type': 'application/json',
    'User-Agent': USER_AGENT,
  };
  const start = await fetchJson(
    `${args.apiBase}/api/viventium/scheduler/chat`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        text: buildText(testCase),
        conversationId: 'new',
        agentId: args.agentId,
        userId: qaAuth.userId,
        scheduleId: `qa-native-${hashValue(testCase.id, 10)}`,
        sourceEventId,
        viventiumSurface: 'scheduler',
        viventiumQaRun: true,
        viventiumQaRunId: args.qaRunId,
      }),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      startStatus: start.status,
      text: '',
      route: 'scheduler_gateway',
      requestIdentityHash,
      error: `scheduler_start_http_${start.status}`,
      startBodyKeys: Object.keys(start.body || {}).slice(0, 20),
    };
  }
  const stream = await readSseToFinal({
    url: `${args.apiBase}/api/viventium/scheduler/stream/${encodeURIComponent(
      start.body.streamId,
    )}?userId=${encodeURIComponent(qaAuth.userId)}`,
    headers,
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok && (stream.text.trim() || caseAllowsEmpty(testCase)),
    startStatus: start.status,
    streamStatus: stream.status,
    text: stream.text,
    route: 'scheduler_gateway',
    requestIdentityHash,
    error: stream.error,
    streamIdHash: hashValue(start.body.streamId),
    eventCount: stream.events.length,
    finalMeta: extractFinalMeta(stream.events),
    hasCortexActivation: hasCortexActivation(stream.events),
    hasRuntimeHold: hasRuntimeHold(stream.events),
    privateEvents: stream.events,
  };
}

async function runSurfaceCase({ args, env, qaAuth, token, testCase }) {
  if (testCase.surface === 'voice') {
    return runVoiceSurface({ args, token, ownerId: qaAuth.userId, env, testCase });
  }
  if (testCase.surface === 'telegram') {
    return runTelegramSurface({ args, env, qaAuth, testCase });
  }
  if (testCase.surface === 'scheduler') {
    return runSchedulerSurface({ args, env, qaAuth, testCase });
  }
  if (testCase.surface === 'listen_only') {
    return runVoiceSurface({
      args,
      token,
      ownerId: qaAuth.userId,
      env,
      testCase,
      listenOnly: true,
    });
  }
  if (testCase.surface === 'wing') {
    return runVoiceSurface({
      args,
      token,
      ownerId: qaAuth.userId,
      env,
      testCase,
      wingMode: true,
    });
  }
  return runAgentsSurface({ args, token, ownerId: qaAuth.userId, testCase });
}

async function observePostCaseDbEvidence({ db, result, maxObserveMs, followUpGraceMs }) {
  const conversationId = result?.finalMeta?.conversationId || '';
  if (!conversationId || !db) {
    return {
      observed: false,
      delayedMessageCount: 0,
      delayedVisibleText: '',
      cortexInsightCount: 0,
      cortexInsights: [],
    };
  }

  const deadline = Date.now() + Math.max(0, maxObserveMs);
  const followUpGraceBudget = Math.max(0, followUpGraceMs || 0);
  let cortexSettledAt = 0;
  let latest = null;
  while (Date.now() <= deadline) {
    latest = await readConversationEvidence({ db, result, conversationId });
    const hasPendingCortex = latest.primaryCortexStatuses.some((status) =>
      ['activating', 'brewing', 'running', 'pending'].includes(status),
    );
    if (!result.hasCortexActivation) {
      break;
    }
    if (!hasPendingCortex) {
      cortexSettledAt = cortexSettledAt || Date.now();
      const awaitingAsyncFollowUp =
        latest.cortexInsightCount > 0 &&
        latest.delayedMessageCount === 0 &&
        Date.now() - cortexSettledAt < followUpGraceBudget;
      if (!awaitingAsyncFollowUp) {
        break;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return latest || readConversationEvidence({ db, result, conversationId });
}

async function readConversationEvidence({ db, result, conversationId }) {
  const messages = await db
    .collection('messages')
    .find({ conversationId })
    .sort({ createdAt: 1 })
    .toArray();
  const responseMessageId = result?.finalMeta?.responseMessageId || '';
  const primary = messages.find((message) => message.messageId === responseMessageId);
  const delayed = messages.filter((message) => {
    if (message.messageId === responseMessageId) {
      return false;
    }
    if (message.isCreatedByUser === true || message.sender === 'User') {
      return false;
    }
    return Boolean(contentToText(message.text || message.content).trim());
  });
  const cortexItems = Array.isArray(primary?.content)
    ? primary.content.filter((part) => part?.type === 'cortex_insight' || part?.type === 'cortex_activation')
    : [];
  const cortexInsights = cortexItems
    .filter((part) => part?.type === 'cortex_insight')
    .map((part) => ({
      cortexName: part.cortex_name || '',
      status: part.status || '',
      silent: Boolean(part.silent),
      noResponse: Boolean(part.no_response),
      insightHash: hashValue(part.insight || ''),
      privateInsight: part.insight || '',
    }));
  return {
    observed: true,
    conversationIdHash: hashValue(conversationId),
    responseMessageIdHash: hashValue(responseMessageId),
    delayedMessageCount: delayed.length,
    delayedVisibleText: delayed.map((message) => contentToText(message.text || message.content)).join('\n\n'),
    delayedMessageHashes: delayed.map((message) => hashValue(message.messageId || '')),
    cortexInsightCount: cortexInsights.length,
    cortexInsights,
    primaryCortexStatuses: cortexItems.map((part) => part.status || '').filter(Boolean),
  };
}

function buildJudgePrompt(
  testCase,
  result,
  comparisonResult = null,
  comparisonTestCase = null,
) {
  const hasDecisionQualityContract =
    Object.keys(testCase.decisionQualityContract || {}).length > 0 ||
    Object.keys(testCase.groundTruth || {}).length > 0;
  return [
    'You are a strict QA judge for a local Viventium prompt architecture eval.',
    'Use only the supplied prompt, expected behavior, assistant output, route status, and rubric.',
    'Do not browse, do not call tools, and do not infer private facts.',
    ...(hasDecisionQualityContract
      ? [
          'Decision-quality note: Transport or route success is never evidence of semantic correctness.',
          'Do not reward agreement, disagreement, caution, confidence, or caveats as ends in themselves. Score whether the conclusion follows the supplied evidence, quantities, causal design, uncertainty, and decision tradeoffs.',
          'Do not require an unsupported caveat merely to sound balanced. Penalize both reflexive agreement and reflexive rejection, and apply the same evidentiary standard to paired cases.',
          'The assistant under test received the evidence packet but not the private ground truth below. Use the private gold to score the conclusion, evidence-specific reasoning, calculations, calibration, and next action; never expose it or infer a preferred sentiment from the user\'s proposed action.',
          'Score every declared evaluated dimension from 0 to 1 with response-specific evidence. These scores are mechanically weighted by the runner.',
          'When a declared comparison case is supplied, comparison_consistency passes only if the two responses change their conclusion or update direction exactly as the changed evidence requires. Different wording or a canned template is insufficient.',
        ]
      : []),
    'Conditional rubric note: if a rubric item is explicitly conditional ("if available", "if unavailable", "when present", "if an actual fallback event occurs") and the condition is not evidenced in this case, do not fail solely because the conditional behavior did not appear.',
    'Memory/context note: natural use of relevant user memory is allowed unless a rubric item explicitly forbids it. Phrases like "hidden prompt or memory keys" mean internal key names, prompt text, source metadata, IDs, or system plumbing, not ordinary personalized context.',
    'Hold/delayed-work note: for live productivity, browser, worker, or cortex cases, a brief hold is acceptable when native stream evidence shows an activated tool/cortex route and no verified final result has returned yet. Judge the route evidence plus delayed evidence, not only the first visible sentence.',
    'Scheduling-tool evidence note: when runtime evidence shows schedule search/get/update tool calls, treat timezone and identity handling as satisfied by the tool-owned contract unless the visible response or tool evidence contradicts it. Do not require the assistant to expose timezone, identity, task IDs, metadata, or schedule internals in the user-facing answer.',
    'Direct-action callback-window note: do not fail a worker/delegation case solely because the callback or final inspection result did not arrive within this runner’s observation window. If native evidence shows a tool_call/delegation route and the visible text only promises future results, treat it as a valid pending delegation. Fail only if the answer claims completed inspection, concrete findings, or local UI state without verified evidence.',
    'Citation marker note: web-search citation markers such as turn0search2 are acceptable user-facing source anchors when matching web_search_sources evidence is supplied. Do not classify matching citation anchors as plumbing exposure.',
    'Snippet-limitation note: if the response explicitly says the retrieved snippets/results do not directly support or confirm a precise rule, treat that as an honest evidence limitation, not as a fabricated page-content check.',
    'Voice evidence note: the Assistant output field is authoritative visible/TTS text even when native final_content is sparse.',
    'Observability note: prompt-frame and token-budget logging is private QA telemetry in frame summaries/evidence. Do not require the assistant to display token estimates to the user.',
    'Verdict rule: for an ordinary case, pass when every listed rubric item is met. For a decision-quality case, the mechanical contract owns the verdict: comparison consistency must pass when required, the weighted dimension score must reach the declared threshold, and conclusion correctness must reach its minimum. Rubric results supply evidence for those scores; a minor miss or an equivalent but less detailed next action does not independently veto an otherwise passing weighted result. Any rubric miss that changes the conclusion or misreads the evidence must lower the relevant dimension score. Do not downgrade for a preference outside those supplied gates.',
    'Return only valid JSON with this exact shape:',
    '{"verdict":"pass|partial|fail","score":0.0,"rubric":[{"item":"...","met":true,"evidence":"..."}],"dimension_results":[{"dimension":"...","score":0.0,"evidence":"..."}],"comparison_consistency":{"required":false,"pass":true,"evidence":"..."},"notes":"..."}',
    '',
    `Case id: ${testCase.id}`,
    `Family: ${testCase.familyId}`,
    `Surface: ${testCase.surface || 'web'}`,
    `Expected surface: ${testCase.expected_surface || 'visible_or_contextual'}`,
    `Expected decision: ${testCase.expected_decision || 'n/a'}`,
    `Route status: ${result.ok ? 'ok' : 'failed'} ${result.error || ''}`,
    ...(hasDecisionQualityContract
      ? [
          `Private decision-quality contract: ${scrubForPublic(JSON.stringify(testCase.decisionQualityContract || {}))}`,
          `Private decision-quality ground truth: ${scrubForPublic(JSON.stringify(testCase.groundTruth || {}))}`,
          `Evaluated dimensions: ${(testCase.evaluatedDimensions || []).join(', ') || 'none'}`,
          `Declared comparison expectation: ${testCase.comparisonExpectation || 'none'}`,
        ]
      : []),
    '',
    'User/setup prompt:',
    buildText(testCase),
    '',
    'Rubric:',
    (testCase.rubric || []).map((item) => `- ${item}`).join('\n'),
    '',
    'Assistant output:',
    result.text || '[empty_or_suppressed]',
    ...(comparisonResult
      ? [
          '',
          `Declared comparison case: ${scrubForPublic(comparisonTestCase?.id || 'unknown')}`,
          `Private comparison ground truth: ${scrubForPublic(JSON.stringify(comparisonTestCase?.groundTruth || {}))}`,
          'Comparison assistant output:',
          comparisonResult.text || '[empty_or_suppressed]',
        ]
      : []),
    '',
    'Native stream evidence:',
    summarizeNativeEventsForJudge(result.privateEvents || []),
    '',
    'Delayed DB follow-up / cortex evidence observed after native stream:',
    result.postCaseEvidence?.delayedVisibleText ||
      (result.postCaseEvidence?.cortexInsights || [])
        .map((item) => `${item.cortexName}: ${item.privateInsight}`)
        .filter(Boolean)
        .join('\n') ||
      '[none_observed]',
  ].join('\n');
}

function parseJudgeJson(text) {
  const trimmed = String(text || '').trim();
  const direct = tryParseJson(trimmed);
  if (direct) {
    return direct;
  }
  const match = trimmed.match(/\{[\s\S]*\}/);
  return match ? tryParseJson(match[0]) : null;
}

function tryParseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function encodeEphemeralAgentId({ endpoint, model, sender }) {
  const encodePart = (value) => String(value || '').replace(/:/g, '__');
  return `${encodePart(endpoint)}__${encodePart(model)}___${encodePart(sender || 'SemanticJudge')}`;
}

async function runEphemeralJudgeTurn({ args, token, prompt }) {
  const messageId = crypto.randomUUID();
  const agentId = encodeEphemeralAgentId({
    endpoint: args.judgeEndpoint,
    model: args.judgeModel,
    sender: 'SemanticJudge',
  });
  const payload = {
    text: prompt,
    sender: 'User',
    clientTimestamp: new Date().toISOString(),
    clientTimezone: 'America/Toronto',
    isCreatedByUser: true,
    parentMessageId: NO_PARENT,
    conversationId: 'new',
    messageId,
    responseMessageId: `${messageId}_`,
    endpoint: 'agents',
    endpointType: 'agents',
    agent_id: agentId,
    model: agentId,
    promptPrefix:
      'You are a strict semantic QA judge for Viventium native-surface regression tests. You are not Viventium. You do not answer the original user. You evaluate the supplied response and native evidence against the supplied rubric, then return exactly one JSON object with no markdown.',
    temperature: 0,
    top_p: 1,
    max_tokens: 2200,
    ephemeralAgent: {},
    viventiumSurface: 'web',
    viventiumInputMode: 'text',
    viventiumQaRun: true,
    viventiumQaRunId: args.qaRunId,
    isTemporary: true,
  };
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      text: '',
      error: `local_ephemeral_judge_start_http_${start.status}`,
      status: start.status,
    };
  }
  const stream = await readSseToFinal({
    url: `${args.apiBase}/api/agents/chat/stream/${encodeURIComponent(start.body.streamId)}`,
    headers: { Authorization: `Bearer ${token}` },
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok,
    text: stream.text || '',
    error: stream.error || null,
    status: stream.status,
    eventCount: stream.events.length,
    finalMeta: extractFinalMeta(stream.events),
  };
}

function scoreNativeDecisionQualityJudgment(testCase, judgment) {
  const contract = testCase?.decisionQualityContract || {};
  const weights = contract.dimensions || {};
  const evaluatedDimensions = testCase?.evaluatedDimensions || [];
  if (Object.keys(weights).length === 0 || evaluatedDimensions.length === 0) {
    return {
      verdict: String(judgment?.verdict || '').toLowerCase(),
      weightedScore: Number(judgment?.score ?? 0),
      error: null,
    };
  }
  const scores = new Map(
    (judgment?.dimension_results || []).map((item) => [
      String(item?.dimension || ''),
      Number(item?.score),
    ]),
  );
  const missing = evaluatedDimensions.filter(
    (dimension) =>
      !scores.has(dimension) ||
      !Number.isFinite(scores.get(dimension)) ||
      scores.get(dimension) < 0 ||
      scores.get(dimension) > 1,
  );
  if (missing.length > 0) {
    return {
      verdict: 'fail',
      weightedScore: 0,
      error: `missing_dimension_scores:${missing.join(',')}`,
    };
  }
  const totalWeight = evaluatedDimensions.reduce(
    (total, dimension) => total + Number(weights[dimension] || 0),
    0,
  );
  const weightedScore = totalWeight > 0
    ? evaluatedDimensions.reduce(
        (total, dimension) =>
          total + Number(weights[dimension] || 0) * scores.get(dimension),
        0,
      ) / totalWeight
    : 0;
  const rubricEvidenceComplete =
    Array.isArray(judgment?.rubric) &&
    judgment.rubric.length === (testCase.rubric || []).length &&
    judgment.rubric.every(
      (item, index) =>
        String(item?.item || '').trim() ===
          String(testCase.rubric[index] || '').trim(),
    );
  const pairPass =
    !testCase.comparisonCaseId ||
    (judgment?.comparison_consistency?.required === true &&
      judgment?.comparison_consistency?.pass === true);
  const pass =
    rubricEvidenceComplete &&
    pairPass &&
    weightedScore >= Number(contract.passingWeightedScore ?? 1) &&
    (scores.get('conclusion_correctness') ?? 0) >=
      Number(contract.minimumConclusionScore ?? 1);
  return { verdict: pass ? 'pass' : 'fail', weightedScore, error: null };
}

async function runJudge({
  args,
  token,
  testCase,
  result,
  comparisonResult = null,
  comparisonTestCase = null,
}) {
  let lastJudgeResult = null;
  const cleanupFinalMetas = [];
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const judgePrompt = [
      attempt === 0
        ? ''
        : 'STRICT RETRY: the prior judge attempt did not return parseable JSON. Return exactly one JSON object with no markdown, no prose, and no code fence.',
      buildJudgePrompt(
        testCase,
        result,
        comparisonResult,
        comparisonTestCase,
      ),
    ].filter(Boolean).join('\n\n');
    const judgeResult = await runEphemeralJudgeTurn({ args, token, prompt: judgePrompt });
    lastJudgeResult = judgeResult;
    if (judgeResult.finalMeta?.conversationId) {
      cleanupFinalMetas.push(judgeResult.finalMeta);
    }
    const parsed = parseJudgeJson(judgeResult.text);
    if (!parsed) {
      continue;
    }
    const verdict = String(parsed.verdict || '').toLowerCase();
    const score = Number(parsed.score);
    const decisionQuality = scoreNativeDecisionQualityJudgment(
      testCase,
      parsed,
    );
    return {
      ok: ['pass', 'partial', 'fail'].includes(verdict),
      verdict: ['pass', 'partial', 'fail'].includes(verdict)
        ? decisionQuality.verdict
        : 'invalid_verdict',
      score: decisionQuality.weightedScore,
      judgeReportedVerdict: verdict,
      judgeReportedScore: Number.isFinite(score) ? score : null,
      decisionQualityError: decisionQuality.error,
      responseHash: hashValue(judgeResult.text || ''),
      rubric: Array.isArray(parsed.rubric) ? parsed.rubric : [],
      dimensionResults: Array.isArray(parsed.dimension_results)
        ? parsed.dimension_results
        : [],
      comparisonConsistency: parsed.comparison_consistency || null,
      notes: typeof parsed.notes === 'string' ? parsed.notes : '',
      privateText: judgeResult.text,
      attempts: attempt + 1,
      cleanupFinalMetas,
    };
  }

  return {
    ok: false,
    verdict: 'judge_parse_failed',
    score: 0,
    responseHash: hashValue(lastJudgeResult?.text || ''),
    error: lastJudgeResult?.error || 'judge_json_parse_failed',
    privateText: lastJudgeResult?.text || '',
    attempts: 2,
    cleanupFinalMetas,
  };
}

async function runBrowserProbe({ args, qaAuth }) {
  const { chromium } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'playwright'));
  const browser = await chromium.launch({ channel: 'chrome', headless: args.headless });
  const context = await browser.newContext({
    baseURL: args.clientBase,
    userAgent: USER_AGENT,
    viewport: { width: 1440, height: 1100 },
  });
  await context.addCookies([
    {
      name: 'refreshToken',
      value: qaAuth.refreshToken,
      url: args.apiBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
    {
      name: 'token_provider',
      value: 'librechat',
      url: args.apiBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
    {
      name: 'refreshToken',
      value: qaAuth.refreshToken,
      url: args.clientBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
    {
      name: 'token_provider',
      value: 'librechat',
      url: args.clientBase,
      httpOnly: true,
      sameSite: 'Strict',
      expires: Math.floor(Date.now() / 1000) + 7200,
    },
  ]);
  const page = await context.newPage();
  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(scrubForPublic(message.text()).slice(0, 500));
    }
  });
  page.on('requestfailed', (request) => {
    failedRequests.push({
      urlHash: hashValue(request.url()),
      failure: scrubForPublic(request.failure()?.errorText || 'request_failed'),
    });
  });

  await page.goto(`${args.clientBase}/c/new`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => {});
  const refresh = await page.evaluate(async () => {
    const res = await fetch('/api/auth/refresh', { method: 'POST' });
    const body = await res.json().catch(() => ({}));
    return {
      status: res.status,
      ok: res.ok,
      hasToken: typeof body.token === 'string' && body.token.length > 10,
      userEmail: body.user?.email || '',
    };
  });
  const user = await page.evaluate(async () => {
    const refreshRes = await fetch('/api/auth/refresh', { method: 'POST' });
    const refreshBody = await refreshRes.json().catch(() => ({}));
    const token = refreshBody.token || '';
    const res = await fetch('/api/user', { headers: { Authorization: `Bearer ${token}` } });
    const body = await res.json().catch(() => ({}));
    return {
      status: res.status,
      ok: res.ok,
      email: body.email || body.user?.email || '',
    };
  });
  const mcpStatus = await page.evaluate(async (token) => {
    const res = await fetch('/api/mcp/connection/status', {
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await res.json().catch(() => ({}));
    return {
      status: res.status,
      ok: res.ok,
      connectionStatus: body.connectionStatus || {},
    };
  }, qaAuth.accessToken);

  const bodyText = await page.locator('body').innerText({ timeout: 20_000 }).catch(() => '');
  const screenshotPath = path.join(args.outputDir, 'chrome-qa-account-local-viventium.png');
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await browser.close();

  const mcpPublic = {};
  for (const [serverName, status] of Object.entries(mcpStatus.connectionStatus || {})) {
    mcpPublic[serverName] = {
      connectionState: status?.connectionState || 'unknown',
      requiresOAuth: Boolean(status?.requiresOAuth),
      hasError: Boolean(status?.error),
    };
  }

  return {
    ok:
      refresh.ok &&
      refresh.hasToken &&
      user.ok &&
      hashValue(user.email || '') === qaAuth.userEmailHash &&
      bodyText.includes('Viventium'),
    refreshStatus: refresh.status,
    userStatus: user.status,
    userEmailHash: hashValue(user.email || ''),
    expectedEmailHash: qaAuth.userEmailHash,
    bodyHasViventium: bodyText.includes('Viventium'),
    title: scrubForPublic(await pageTitleSafe(args.clientBase)),
    consoleErrors,
    failedRequests,
    mcpStatus: {
      ok: mcpStatus.ok,
      status: mcpStatus.status,
      public: mcpPublic,
    },
    screenshotPath,
  };
}

async function pageTitleSafe(_clientBase) {
  return 'captured_in_private_screenshot';
}

function hashFinalMeta(finalMeta) {
  if (!finalMeta || typeof finalMeta !== 'object') {
    return null;
  }
  const hashes = {};
  for (const [key, value] of Object.entries(finalMeta)) {
    if (String(value || '').trim()) {
      hashes[`${key}Hash`] = hashValue(String(value));
    }
  }
  return Object.keys(hashes).length > 0 ? hashes : null;
}

function artifactSafePromptFrame(frame) {
  if (!frame || typeof frame !== 'object') {
    return frame;
  }
  const { debug_redacted_layers: _debugLayers, ...safeFrame } = frame;
  return safeFrame;
}

function artifactSafeResult(result) {
  if (!result || typeof result !== 'object') {
    return result;
  }
  const {
    finalMeta,
    cleanupFinalMetas,
    privateEvents,
    ...safeResult
  } = result;
  const events = Array.isArray(privateEvents) ? privateEvents : [];
  const finalMetaHashes = hashFinalMeta(finalMeta);
  return {
    ...safeResult,
    ...(finalMetaHashes ? { finalMetaHashes } : {}),
    ...(Array.isArray(cleanupFinalMetas) && cleanupFinalMetas.length > 0
      ? {
          cleanupFinalMetaHashes: cleanupFinalMetas
            .map(hashFinalMeta)
            .filter(Boolean),
        }
      : {}),
    privateEventCount: events.length,
    privateEventHashes: events.map((event) => hashValue(event)),
    nativeEventSummary: summarizeNativeEventsForJudge(events),
  };
}

function artifactSafeJudge(judge) {
  if (!judge || typeof judge !== 'object') {
    return judge;
  }
  const { cleanupFinalMetas, ...safeJudge } = judge;
  return {
    ...safeJudge,
    ...(Array.isArray(cleanupFinalMetas) && cleanupFinalMetas.length > 0
      ? {
          cleanupFinalMetaHashes: cleanupFinalMetas
            .map(hashFinalMeta)
            .filter(Boolean),
        }
      : {}),
  };
}

function buildCanonicalArtifact(privateRun) {
  return {
    ...privateRun,
    cases: (privateRun.cases || []).map((item) => {
      const requestBoundFrames = promptFramesForRequest(
        item.private?.frames,
        item.requestIdentityHash,
      );
      const completionFrames = completionPromptFramesForRequest(
        item.private?.completionFrames,
        item.requestIdentityHash,
      );
      return {
        ...item,
        frameSummary: summarizeFrames(requestBoundFrames),
        judge: artifactSafeJudge(item.judge),
        private: item.private
          ? {
              ...item.private,
              result: artifactSafeResult(item.private.result),
              frames: requestBoundFrames.map(artifactSafePromptFrame),
              completionFrames: completionFrames.map(artifactSafePromptFrame),
            }
          : item.private,
      };
    }),
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  assertNativeLiveRunRequested(args);
  ensureDir(args.outputDir);
  ensureDir(path.dirname(args.publicReport));

  const env = loadLocalEnv();
  const promptBank = readJson(args.promptBank);
  const cases = selectPromptCases(promptBank, args);
  const selectedCaseIds = cases.map((testCase) => testCase.id);
  const semanticRequired = cases.some(caseRequiresSemanticJudge);
  const runtimeHealth = await fetchJson(`${args.apiBase}/health`, {}, 10_000);
  const runtimeConfig = await fetchJson(`${args.apiBase}/api/config`, {}, 10_000);

  let qaAuth;
  const privateRun = {
    generatedAt: new Date().toISOString(),
    args: {
      apiBaseHash: hashValue(args.apiBase),
      clientBaseHash: hashValue(args.clientBase),
      qaEmailHash: hashValue(args.qaEmail),
      agentIdHash: hashValue(args.agentId),
      qaRunIdHash: hashValue(args.qaRunId),
      maxCases: args.maxCases,
      family: args.family,
      caseId: args.caseId,
      caseIds: args.caseIds,
      surface: args.surface,
      promptId: args.promptId,
      runLive: args.runLive,
      runJudge: args.runJudge,
      semanticRequired,
      judgeRouteHash: args.runJudge ? hashValue(`${args.judgeEndpoint}:${args.judgeModel}`) : '',
      postCaseObserveMs: args.postCaseObserveMs,
      followUpGraceMs: args.followUpGraceMs,
      headless: args.headless,
    },
    runtime: {
      health: { ok: runtimeHealth.ok, status: runtimeHealth.status },
      config: {
        ok: runtimeConfig.ok,
        status: runtimeConfig.status,
        appTitle: scrubForPublic(runtimeConfig.body?.appTitle || runtimeConfig.body?.title || ''),
      },
    },
    browserProbe: null,
    selection: {
      requestedFamily: args.family || '',
      requestedCaseId: args.caseId || '',
      requestedCaseIds: args.caseIds,
      requestedSurface: args.surface || '',
      requestedPromptId: args.promptId || '',
      selectedCaseIds,
      selectedCaseCount: selectedCaseIds.length,
    },
    cleanup: { ok: false, status: 'pending' },
    cases: [],
  };

  try {
    qaAuth = await createQaAuth({ args, env });
    privateRun.qa = {
      userIdHash: hashValue(qaAuth.userId),
      userEmailHash: qaAuth.userEmailHash,
      sessionIdHash: hashValue(qaAuth.sessionId),
      syntheticTelegramUserHash: hashValue(qaAuth.syntheticTelegramUserId),
    };

    privateRun.browserProbe = await runBrowserProbe({ args, qaAuth });

    let offsets = collectFrameOffsets();
    for (const testCase of cases) {
      const startedAt = Date.now();
      const caseOffsets = offsets;
      let surfaceResult;
      let judge = null;
      let frameDelta = { frames: [], afterOffsets: offsets };
      let fixtureEvidence = [];
      let completionEvidence = {
        completionExpected: testCase.surface !== 'listen_only',
        verified: false,
        requestedSurface: trustedCompletionSurface(testCase.surface),
        observedSurface: 'unknown',
        completionFrameCount: 0,
        requestIdentityHash: 'missing',
        actualCompletionAgentIdHash: 'missing',
        completionProviderHashes: [],
        completionModelHashes: [],
      };
      try {
        if (needsStarterMorningBriefingFixture(testCase)) {
          const fixtureResult = await applyStarterMorningBriefingFixture({
            args,
            env,
            userId: qaAuth.userId,
            agentId: args.agentId,
          });
          fixtureEvidence = [fixtureResult];
          if (!fixtureResult.ok) {
            throw new Error(fixtureResult.reason || 'fixture_failed');
          }
        }
        surfaceResult = await runSurfaceCase({
          args,
          env,
          qaAuth,
          token: qaAuth.accessToken,
          testCase,
        });
        if (/^[0-9a-f]{16}$/.test(String(surfaceResult.requestIdentityHash || ''))) {
          completionEvidence.requestIdentityHash = surfaceResult.requestIdentityHash;
        }
        qaAuth.trackCreatedConversations([
          ...(surfaceResult.cleanupFinalMetas || []),
          surfaceResult.finalMeta,
        ]);
        const observeMs = surfaceResult.hasCortexActivation
          ? args.postCaseObserveMs
          : Math.min(args.postCaseObserveMs, 2500);
        surfaceResult.postCaseEvidence = await observePostCaseDbEvidence({
          db: qaAuth.db,
          result: surfaceResult,
          maxObserveMs: observeMs,
          followUpGraceMs: args.followUpGraceMs,
        });
        await new Promise((resolve) => setTimeout(resolve, 750));
        frameDelta = readFrameDelta(caseOffsets);
        offsets = frameDelta.afterOffsets;
        if (surfaceResult.ok) {
          completionEvidence = completionEvidenceForCase(
            frameDelta.frames,
            trustedCompletionSurface(testCase.surface),
            surfaceResult.requestIdentityHash,
            testCase.surface !== 'listen_only',
          );
        }
      } catch (error) {
        surfaceResult = {
          ...(surfaceResult || {}),
          ok: false,
          text: surfaceResult?.text || '',
          error: scrubForPublic(error.message || String(error)),
          route: surfaceResult?.route || testCase.surface || 'web',
        };
      }

      const requestBoundFrames = promptFramesForRequest(
        frameDelta.frames,
        surfaceResult.requestIdentityHash,
      );
      const frameSummary = summarizeFrames(requestBoundFrames);
      privateRun.cases.push({
        caseId: testCase.id,
        familyId: testCase.familyId,
        surface: testCase.surface || 'web',
        requestedSurface: testCase.surface || 'web',
        requestedCompletionSurface: completionEvidence.requestedSurface,
        observedCompletionSurface: completionEvidence.observedSurface,
        completionExpected: completionEvidence.completionExpected,
        completionSurfaceVerified: completionEvidence.verified,
        completionFrameCount: completionEvidence.completionFrameCount,
        requestIdentityHash: completionEvidence.requestIdentityHash,
        actualCompletionAgentIdHash: completionEvidence.actualCompletionAgentIdHash,
        completionProviderHashes: completionEvidence.completionProviderHashes,
        completionModelHashes: completionEvidence.completionModelHashes,
        requestedProviderHashes: completionEvidence.requestedProviderHashes || [],
        requestedModelHashes: completionEvidence.requestedModelHashes || [],
        requestedEfforts: completionEvidence.requestedEfforts || [],
        effectiveEfforts: completionEvidence.effectiveEfforts || [],
        fallbackUsed: completionEvidence.fallbackUsed === true,
        fallbackReasons: completionEvidence.fallbackReasons || [],
        route: surfaceResult.route || 'unknown',
        status: surfaceResult.ok ? 'completed' : 'failed',
        durationMs: Date.now() - startedAt,
        responseHash: hashValue(surfaceResult.text || ''),
        responsePreview: scrubForPublic((surfaceResult.text || '').slice(0, 800)),
        allowsDuplicateResponse: caseAllowsDuplicateResponse(testCase),
        allowsUnresolvedAsync: caseAllowsUnresolvedAsync(testCase),
        delayedFollowUpCount: surfaceResult.postCaseEvidence?.delayedMessageCount || 0,
        cortexInsightCount: surfaceResult.postCaseEvidence?.cortexInsightCount || 0,
        hasCortexActivation: Boolean(surfaceResult.hasCortexActivation),
        hasRuntimeHold: Boolean(surfaceResult.hasRuntimeHold),
        pendingCortexStatuses: (surfaceResult.postCaseEvidence?.primaryCortexStatuses || [])
          .filter(isPendingCortexStatus)
          .map(scrubForPublic),
        error: scrubForPublic(surfaceResult.error || ''),
        eventCount: surfaceResult.eventCount || 0,
        frameSummary,
        judge,
        semanticJudged: false,
        semanticPass: false,
        semanticState: 'not_run',
        private: {
          fixtureEvidence,
          result: surfaceResult,
          frames: requestBoundFrames,
          completionFrames: completionPromptFramesForRequest(
            frameDelta.frames,
            surfaceResult.requestIdentityHash,
          ),
        },
      });
    }

    if (args.runJudge) {
      const casesById = new Map(cases.map((testCase) => [testCase.id, testCase]));
      const resultsById = new Map(
        privateRun.cases.map((item) => [item.caseId, item.private?.result]),
      );
      for (let index = 0; index < privateRun.cases.length; index += 1) {
        const item = privateRun.cases[index];
        const testCase = casesById.get(item.caseId);
        if (!testCase || item.status !== 'completed') {
          continue;
        }
        const comparisonTestCase = testCase.comparisonCaseId
          ? casesById.get(testCase.comparisonCaseId)
          : null;
        const comparisonResult = comparisonTestCase
          ? resultsById.get(comparisonTestCase.id)
          : null;
        if (testCase.comparisonCaseId && !comparisonResult) {
          item.judge = {
            ok: false,
            verdict: 'semantic_pair_unavailable',
            score: 0,
            error: `comparison_case_unavailable:${scrubForPublic(testCase.comparisonCaseId)}`,
          };
          item.semanticJudged = true;
          item.semanticPass = false;
          item.semanticState = 'semantic_pair_unavailable';
          continue;
        }
        item.judge = await runJudge({
          args,
          token: qaAuth.accessToken,
          testCase,
          result: item.private.result,
          comparisonResult,
          comparisonTestCase,
        });
        qaAuth.trackCreatedConversations(item.judge.cleanupFinalMetas || []);
        item.semanticJudged = Boolean(item.judge?.verdict);
        item.semanticPass = item.judge?.verdict === 'pass';
        item.semanticState = item.judge?.verdict || 'not_run';
        await new Promise((resolve) => setTimeout(resolve, 500));
        const judgeDelta = readFrameDelta(offsets);
        offsets = judgeDelta.afterOffsets;
      }
    }
  } finally {
    let cleanupFailure = null;
    if (qaAuth) {
      try {
        const cleanup = await qaAuth.cleanup();
        if (cleanup?.cleaned !== true) {
          throw new Error('native_surface_qa_cleanup_unverified');
        }
        privateRun.cleanup = { ok: true, status: 'complete', ...cleanup };
      } catch (error) {
        cleanupFailure = error;
        privateRun.cleanup = {
          ok: false,
          status: 'failed',
          error: scrubForPublic(error?.code || error?.message || 'native_surface_qa_cleanup_failed'),
        };
      }
    }
    if (cleanupFailure) {
      privateRun.cleanupFailure = scrubForPublic(
        cleanupFailure?.code || cleanupFailure?.message || 'native_surface_qa_cleanup_failed',
      );
    }
  }

  const privateJsonPath = path.join(args.outputDir, 'native-surface-playwright-qa.json');
  const summary = summarizeRun(privateRun);
  privateRun.summary = summary;
  fs.writeFileSync(privateJsonPath, JSON.stringify(buildCanonicalArtifact(privateRun), null, 2));
  writePublicReport({ args, summary, privateRun, privateJsonPath });

  console.log(
    JSON.stringify(
      {
        status: summary.status,
        publicReport: path.relative(REPO_ROOT, args.publicReport),
        privateJsonPathHash: hashValue(privateJsonPath),
        privateJsonWritten: true,
        selectedCaseCount: summary.selectedCaseCount,
        resultCount: summary.resultCount,
        completedCount: summary.completedCount,
        failedCount: summary.failedCount,
        semanticJudgedCount: summary.semanticJudgedCount,
        semanticPassedCount: summary.semanticPassedCount,
        semanticFailedCount: summary.semanticFailedCount,
        completed: summary.completed,
        failed: summary.failed,
        semanticPass: summary.semanticPass,
        semanticFail: summary.semanticFail,
        duplicateResponseQualityFailureCount:
          summary.duplicateResponseQualityFailures.length,
        unresolvedAsyncQualityFailureCount:
          summary.unresolvedAsyncQualityFailures.length,
      },
      null,
      2,
    ),
  );

  if (
    !summary.selectedCoverageOk ||
    !summary.completionEvidenceOk ||
    !summary.cleanupOk ||
    summary.failedCount > 0 ||
    (summary.semanticRequired && summary.judged !== summary.total) ||
    summary.semanticPartial > 0 ||
    summary.semanticFail > 0 ||
    summary.duplicateResponseQualityFailures.length > 0 ||
    summary.unresolvedAsyncQualityFailures.length > 0 ||
    !summary.browserOk
  ) {
    process.exitCode = 1;
  }
}

function summarizeRun(privateRun) {
  const cases = privateRun.cases || [];
  const selectedCaseIds = (privateRun.selection?.selectedCaseIds || []).map(String);
  const resultCaseIds = cases.map((item) => String(item.caseId || ''));
  const selectedCaseCount = Number(privateRun.selection?.selectedCaseCount || 0);
  const resultCount = cases.length;
  const selectedCoverageOk =
    selectedCaseCount > 0 &&
    selectedCaseCount === selectedCaseIds.length &&
    selectedCaseCount === resultCount &&
    new Set(selectedCaseIds).size === selectedCaseIds.length &&
    new Set(resultCaseIds).size === resultCaseIds.length &&
    stableStringify(selectedCaseIds) === stableStringify(resultCaseIds);
  const completed = cases.filter((item) => item.status === 'completed').length;
  const failed = cases.length - completed;
  const judged = cases.filter((item) => item.judge?.verdict).length;
  const semanticPass = cases.filter((item) => item.judge?.verdict === 'pass').length;
  const semanticPartial = cases.filter((item) => item.judge?.verdict === 'partial').length;
  const semanticFail = cases.filter(
    (item) => item.judge && !['pass', 'partial'].includes(item.judge.verdict),
  ).length;
  const semanticFailedCount = judged - semanticPass;
  const completionEvidenceOk = cases.every((item) => {
    const contractPresent =
      typeof item.requestedSurface === 'string' &&
      item.requestedSurface.length > 0 &&
      typeof item.requestedCompletionSurface === 'string' &&
      item.requestedCompletionSurface.length > 0 &&
      typeof item.observedCompletionSurface === 'string' &&
      item.observedCompletionSurface.length > 0 &&
      typeof item.completionExpected === 'boolean' &&
      typeof item.completionSurfaceVerified === 'boolean' &&
      /^[0-9a-f]{16}$/.test(String(item.requestIdentityHash || '')) &&
      typeof item.actualCompletionAgentIdHash === 'string' &&
      Array.isArray(item.completionProviderHashes) &&
      Array.isArray(item.completionModelHashes) &&
      typeof item.semanticPass === 'boolean' &&
      Array.isArray(item.private?.completionFrames);
    if (!contractPresent || item.status !== 'completed') {
      return false;
    }
    if (item.completionExpected === false) {
      return (
        item.completionSurfaceVerified === true &&
        item.observedCompletionSurface === 'none' &&
        item.actualCompletionAgentIdHash === 'not_applicable' &&
        item.private.completionFrames.length === 0
      );
    }
    return (
      item.completionSurfaceVerified === true &&
      item.observedCompletionSurface === item.requestedCompletionSurface &&
      /^[0-9a-f]{16}$/.test(item.actualCompletionAgentIdHash) &&
      item.completionProviderHashes.length > 0 &&
      item.completionModelHashes.length > 0 &&
      item.private.completionFrames.length > 0 &&
      item.private.completionFrames.every(
        (frame) => frame.request_identity_hash === item.requestIdentityHash,
      )
    );
  });
  const cleanupOk = privateRun.cleanup?.ok === true;
  const routes = [...new Set(cases.map((item) => item.route).filter(Boolean))].sort();
  const surfaces = [...new Set(cases.map((item) => item.surface).filter(Boolean))].sort();
  const frameSurfaces = [
    ...new Set(cases.flatMap((item) => item.frameSummary?.surfaces || []).filter(Boolean)),
  ].sort();
  const mcpServers = Object.keys(privateRun.browserProbe?.mcpStatus?.public || {}).sort();
  const responseHashGroups = cases.reduce((acc, item) => {
    if (!item.responseHash || item.status !== 'completed') {
      return acc;
    }
    acc[item.responseHash] = acc[item.responseHash] || [];
    acc[item.responseHash].push(item);
    return acc;
  }, {});
  const duplicateResponseQualityFailures = Object.entries(responseHashGroups)
    .filter(([, group]) => group.length > 1)
    .map(([responseHash, group]) => ({
      responseHash,
      caseIds: group.map((item) => item.caseId),
      allowed:
        group.every((item) => item.allowsDuplicateResponse) ||
        group.every(resultHasResolvedRuntimeHoldEvidence),
    }))
    .filter((group) => !group.allowed);
  const unresolvedAsyncQualityFailures = cases
    .filter(
      (item) =>
        item.status === 'completed' &&
        item.hasCortexActivation &&
        item.hasRuntimeHold &&
        !item.allowsUnresolvedAsync &&
        !item.allowsDuplicateResponse &&
        (item.pendingCortexStatuses || []).length > 0 &&
        Number(item.delayedFollowUpCount || 0) === 0 &&
        Number(item.cortexInsightCount || 0) === 0,
    )
    .map((item) => ({
      caseId: item.caseId,
      responseHash: item.responseHash,
      pendingStatuses: item.pendingCortexStatuses || [],
    }));
  return {
    generatedAt: privateRun.generatedAt,
    status:
      privateRun.args?.semanticRequired && judged !== cases.length
        ? 'semantic_judge_required'
        : privateRun.browserProbe?.ok &&
      selectedCoverageOk &&
      completionEvidenceOk &&
      cleanupOk &&
      failed === 0 &&
      judged === cases.length &&
      semanticPartial === 0 &&
      semanticFail === 0 &&
      duplicateResponseQualityFailures.length === 0 &&
      unresolvedAsyncQualityFailures.length === 0
        ? 'completed_with_semantic_native_surface_evidence'
        : privateRun.browserProbe?.ok &&
            selectedCoverageOk &&
            completionEvidenceOk &&
            cleanupOk &&
            failed === 0 &&
            judged === 0
          ? 'completed_native_surface_evidence_without_semantic_judge'
          : 'completed_with_failures_or_gaps',
    browserOk: Boolean(privateRun.browserProbe?.ok),
    cleanupOk,
    selectedCoverageOk,
    completionEvidenceOk,
    semanticRequired: Boolean(privateRun.args?.semanticRequired),
    selectedCaseCount,
    resultCount,
    completedCount: completed,
    failedCount: failed,
    semanticJudgedCount: judged,
    semanticPassedCount: semanticPass,
    semanticFailedCount,
    total: cases.length,
    completed,
    failed,
    judged,
    semanticPass,
    semanticPartial,
    semanticFail,
    duplicateResponseQualityFailures,
    unresolvedAsyncQualityFailures,
    routes,
    surfaces,
    frameSurfaces,
    mcpServers,
  };
}

function writePublicReport({ args, summary, privateRun, privateJsonPath }) {
  const browser = privateRun.browserProbe || {};
  const mcpRows = Object.entries(browser.mcpStatus?.public || {}).map(
    ([server, status]) =>
      `| ${scrubForPublic(server)} | ${status.connectionState} | ${status.requiresOAuth ? 'yes' : 'no'} | ${status.hasError ? 'yes' : 'no'} |`,
  );
  const caseRows = (privateRun.cases || []).map((item) => {
    const judgeVerdict = item.judge?.verdict || 'not_run';
    const score = item.judge?.score == null ? '' : String(item.judge.score);
    const frameSurfaces = (item.frameSummary?.surfaces || []).join(', ');
    return `| ${scrubForPublic(item.caseId)} | ${scrubForPublic(item.surface)} | ${scrubForPublic(item.route)} | ${item.status} | ${judgeVerdict} | ${score} | ${item.delayedFollowUpCount || 0} | ${item.cortexInsightCount || 0} | ${item.frameSummary?.frameCount || 0} | ${scrubForPublic(frameSurfaces)} | ${scrubForPublic(item.error || '')} |`;
  });

  const lines = [
    '# Native-Surface Playwright QA',
    '',
    `Generated: ${summary.generatedAt}`,
    '',
    '## Status',
    '',
    `- Status: ${summary.status}`,
    `- Browser Chrome QA account probe: ${summary.browserOk ? 'pass' : 'fail'}`,
    `- Prompt-bank cases exercised: ${summary.total}`,
    `- Post-case observation window: ${args.postCaseObserveMs} ms`,
    `- Async follow-up grace after cortex completion: ${args.followUpGraceMs} ms`,
    `- Native/API completed: ${summary.completed}`,
    `- Native/API failed: ${summary.failed}`,
    `- Semantic judge cases: ${summary.judged}`,
    `- Semantic pass: ${summary.semanticPass}`,
    `- Semantic partial: ${summary.semanticPartial}`,
    `- Semantic fail or judge parse fail: ${summary.semanticFail}`,
    `- Duplicate response quality failures: ${summary.duplicateResponseQualityFailures.length}`,
    `- Unresolved async quality failures: ${summary.unresolvedAsyncQualityFailures.length}`,
    `- Routes exercised: ${summary.routes.join(', ') || 'none'}`,
    `- Prompt surfaces requested: ${summary.surfaces.join(', ') || 'none'}`,
    `- Prompt-frame surfaces observed: ${summary.frameSurfaces.join(', ') || 'none'}`,
    '',
    '## Browser Evidence',
    '',
    `- Local Chrome route: local-browser-route (${hashValue(args.clientBase, 12)})`,
    `- QA identity hash matched: ${
      browser.userEmailHash && browser.userEmailHash === browser.expectedEmailHash ? 'yes' : 'no'
    }`,
    `- Refresh status: ${browser.refreshStatus || 'n/a'}`,
    `- User endpoint status: ${browser.userStatus || 'n/a'}`,
    `- Body had Viventium shell: ${browser.bodyHasViventium ? 'yes' : 'no'}`,
    `- Console errors: ${(browser.consoleErrors || []).length}`,
    `- Failed requests: ${(browser.failedRequests || []).length}`,
    `- Private screenshot: ${scrubForPublic(browser.screenshotPath || '')}`,
    '',
    '## MCP Status',
    '',
    browser.mcpStatus
      ? `- MCP status endpoint: ${browser.mcpStatus.ok ? 'pass' : 'fail'} (${browser.mcpStatus.status})`
      : '- MCP status endpoint: not run',
    '',
    '| Server | State | OAuth | Error |',
    '| --- | --- | --- | --- |',
    ...(mcpRows.length ? mcpRows : ['| none | n/a | n/a | n/a |']),
    '',
    '## Case Matrix',
    '',
    '| Case | Surface | Native route | Route status | Semantic verdict | Score | Delayed msgs | Cortex insights | Frames | Frame surfaces | Error |',
    '| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |',
    ...caseRows,
    '',
    '## Quality Gate Failures',
    '',
    summary.duplicateResponseQualityFailures.length
      ? `- Duplicate non-silent response groups: ${summary.duplicateResponseQualityFailures
          .map((group) => `${group.responseHash} (${group.caseIds.map(scrubForPublic).join(', ')})`)
          .join('; ')}`
      : '- Duplicate non-silent response groups: none',
    summary.unresolvedAsyncQualityFailures.length
      ? `- Unresolved async holds: ${summary.unresolvedAsyncQualityFailures
          .map((failure) => `${scrubForPublic(failure.caseId)} (${failure.pendingStatuses.join(', ')})`)
          .join('; ')}`
      : '- Unresolved async holds: none',
    '',
    '## Evidence Policy',
    '',
    `- Private raw JSON: ${scrubForPublic(privateJsonPath)}`,
    '- Public report stores statuses, hashes, counts, route names, sanitized errors, and frame summaries only.',
    '- Full prompts, raw responses, frame payloads, screenshot pixels, cookies, tokens, user ids, and gateway secrets remain private.',
    '',
    '## Known Limits',
    '',
    '- Voice is exercised through the local voice gateway HTTP/SSE route with a fake browser STT/TTS selection, not a real microphone/audio device.',
    '- Wing mode is exercised through the agent surface metadata path; LiveKit ambient interruption policy remains a separate audio-session QA gate.',
    '- Semantic partial verdicts fail this gate unless a future runner adds an explicit reviewed-partial override.',
    '- The semantic judge is a live local model-route judge through the same Viventium stack, not a deterministic unit-test oracle or provider-enforced JSON Schema route.',
    '',
  ];
  fs.writeFileSync(args.publicReport, `${lines.join('\n')}\n`);
}

module.exports = {
  assertCompletionPromptFrameSurface,
  assertNativeLiveRunRequested,
  assertSelectedSyntheticQaUser,
  buildCanonicalArtifact,
  buildPromptFrameRequestIdentityHash,
  buildTelegramSourceEventId,
  buildTelegramSourceOrderScope,
  buildJudgePrompt,
  buildText,
  caseRequiresSemanticJudge,
  cleanupExactQaArtifacts,
  completionEvidenceForCase,
  extractFinalStreamError,
  extractVisibleText,
  flattenPromptCases,
  parseArgs,
  scoreNativeDecisionQualityJudgment,
  selectPromptCases,
  startTelegramSurfaceTurn,
  summarizeRun,
  trustedCompletionSurface,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(scrubForPublic(error.stack || error.message || String(error)));
    process.exit(1);
  });
}
