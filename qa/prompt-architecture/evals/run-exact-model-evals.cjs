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
const DEFAULT_API_BASE = process.env.VIVENTIUM_EVAL_API_BASE || 'http://localhost:3180';
const DEFAULT_QA_EMAIL = process.env.VIVENTIUM_QA_EMAIL || 'qa@example.com';
const MAIN_AGENT_ID = 'agent_viventium_main_95aeb3';
const NO_PARENT = '00000000-0000-0000-0000-000000000000';
const LIVE_RUN_FLAG = 'VIVENTIUM_RUN_EXACT_MODEL_EVALS';
const QA_PASSWORD_ENV = 'VIVENTIUM_QA_PASSWORD';
const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';
const SEMANTIC_JUDGE_FLAG = 'VIVENTIUM_EVAL_SEMANTIC_JUDGE';
const DEFAULT_JUDGE_MODEL = process.env.VIVENTIUM_EVAL_JUDGE_MODEL || 'gpt-5.4';
const DEFAULT_JUDGE_ROUTE = process.env.VIVENTIUM_EVAL_JUDGE_ROUTE || 'local-ephemeral';
const STARTER_MORNING_BRIEFING_TEMPLATE_ID = 'morning_briefing_default_v1';
const STARTER_MORNING_BRIEFING_BASELINE_PROMPT =
  'Morning orientation: review my memories, calendar, pending tasks, ' +
  'and any overnight signals. Prepare a concise morning briefing for the user.';
const BROWSER_USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ViventiumPromptEval/1.0';
const PRIVATE_ROOT =
  process.env.VIVENTIUM_PROMPT_ARCH_PRIVATE_DIR ||
  path.join(os.homedir(), 'Library', 'Application Support', 'Viventium', 'private-user-data');

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function parseArgs(argv) {
  const args = {
    apiBase: DEFAULT_API_BASE,
    promptBank: PROMPT_BANK_PATH,
    outputDir: path.join(PRIVATE_ROOT, 'prompt-architecture-evals', timestampSlug()),
    publicReport: path.join(
      REPO_ROOT,
      'qa',
      'prompt-architecture',
      'reports',
      'phase-4-exact-model-eval-baseline.md',
    ),
    qaEmail: DEFAULT_QA_EMAIL,
    runLive: process.env[LIVE_RUN_FLAG] === '1',
    localJwtFallback: process.env.VIVENTIUM_QA_LOCAL_JWT_FALLBACK === '1',
    maxCases: Number.MAX_SAFE_INTEGER,
    timeoutMs: 120_000,
    postCaseObserveMs: Number.parseInt(process.env.VIVENTIUM_EVAL_POST_CASE_OBSERVE_MS || '20000', 10),
    followUpGraceMs: Number.parseInt(process.env.VIVENTIUM_EVAL_FOLLOWUP_GRACE_MS || '30000', 10),
    agentId: process.env.VIVENTIUM_EVAL_AGENT_ID || MAIN_AGENT_ID,
    semanticJudge: process.env[SEMANTIC_JUDGE_FLAG] === '1',
    judgeModel: DEFAULT_JUDGE_MODEL,
    judgeRoute: DEFAULT_JUDGE_ROUTE,
    judgeEndpoint: process.env.VIVENTIUM_EVAL_JUDGE_ENDPOINT || 'openAI',
    judgeAgentId: process.env.VIVENTIUM_EVAL_JUDGE_AGENT_ID || process.env.VIVENTIUM_EVAL_AGENT_ID || MAIN_AGENT_ID,
    family: '',
    surface: '',
    promptId: '',
  };

  for (const arg of argv) {
    if (arg === '--run-live') {
      args.runLive = true;
    } else if (arg === '--no-live') {
      args.runLive = false;
    } else if (arg === '--local-jwt-fallback') {
      args.localJwtFallback = true;
    } else if (arg.startsWith('--api-base=')) {
      args.apiBase = arg.slice('--api-base='.length).replace(/\/$/, '');
    } else if (arg.startsWith('--prompt-bank=')) {
      args.promptBank = path.resolve(arg.slice('--prompt-bank='.length));
    } else if (arg.startsWith('--output-dir=')) {
      args.outputDir = path.resolve(arg.slice('--output-dir='.length));
    } else if (arg.startsWith('--public-report=')) {
      args.publicReport = path.resolve(arg.slice('--public-report='.length));
    } else if (arg.startsWith('--qa-email=')) {
      args.qaEmail = arg.slice('--qa-email='.length).trim();
    } else if (arg.startsWith('--agent-id=')) {
      args.agentId = arg.slice('--agent-id='.length).trim() || MAIN_AGENT_ID;
    } else if (arg.startsWith('--max-cases=')) {
      const parsed = Number.parseInt(arg.slice('--max-cases='.length), 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        args.maxCases = parsed;
      }
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
    } else if (arg === '--semantic-judge') {
      args.semanticJudge = true;
    } else if (arg === '--no-semantic-judge') {
      args.semanticJudge = false;
    } else if (arg.startsWith('--judge-model=')) {
      args.judgeModel = arg.slice('--judge-model='.length).trim() || DEFAULT_JUDGE_MODEL;
    } else if (arg.startsWith('--judge-route=')) {
      const route = arg.slice('--judge-route='.length).trim();
      if (route) {
        args.judgeRoute = route;
      }
    } else if (arg.startsWith('--judge-endpoint=')) {
      args.judgeEndpoint = arg.slice('--judge-endpoint='.length).trim() || args.judgeEndpoint;
    } else if (arg.startsWith('--judge-agent-id=')) {
      args.judgeAgentId = arg.slice('--judge-agent-id='.length).trim() || args.judgeAgentId;
    } else if (arg.startsWith('--family=')) {
      args.family = arg.slice('--family='.length).trim();
    } else if (arg.startsWith('--surface=')) {
      args.surface = arg.slice('--surface='.length).trim();
    } else if (arg.startsWith('--prompt-id=')) {
      args.promptId = arg.slice('--prompt-id='.length).trim();
    }
  }

  return args;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function parseEnvFile(filePath) {
  const values = {};
  if (!fs.existsSync(filePath)) {
    return values;
  }
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) {
      continue;
    }
    const [key, ...rest] = line.split('=');
    let value = rest.join('=').trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values[key.trim()] = value;
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

  const bootstrap = await fetchJson(
    `${baseUrl}/internal/bootstrap-schedule`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bootstrapPayload),
    },
    10_000,
  ).catch((error) => ({ ok: false, status: 0, body: { reason: error.message } }));

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

function stableStringify(value) {
  return JSON.stringify(value, Object.keys(value || {}).sort());
}

function hashValue(value, length = 16) {
  const text = typeof value === 'string' ? value : stableStringify(value);
  return crypto.createHash('sha256').update(text || '').digest('hex').slice(0, length);
}

function hashFileIfPresent(filePath) {
  try {
    return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex').slice(0, 16);
  } catch (_error) {
    return null;
  }
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
    .replace(/~\/[^\r\n"'`<>]+/g, '[local_path]')
    .replace(/\b[A-Za-z]:\\[^\r\n"'`<>]+/g, '[local_path]')
    .replace(/\\\\[A-Za-z0-9_.-]+\\[^\r\n"'`<>]+/g, '[local_path]')
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b/gi, 'Bearer [secret]')
    .replace(
      /\b(?:sk|pk|rk|ghp|gho|github_pat|xox[baprs]?)-[A-Za-z0-9_\-]{8,}\b/g,
      '[secret]',
    )
    .replace(
      /\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret)=([^&\s"'`<>]+)/gi,
      '$1=[secret]',
    )
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, '[uuid]')
    .replace(/\b[0-9a-f]{24}\b/gi, '[object_id]')
    .replace(/\b\d{10,}\b/g, '[numeric_id]');
}

async function fetchJson(url, options = {}, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'User-Agent': BROWSER_USER_AGENT,
        ...(options.headers || {}),
      },
    });
    const text = await response.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch (_error) {
      body = { raw: text.slice(0, 500) };
    }
    return {
      ok: response.ok,
      status: response.status,
      body,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function fetchText(url, options = {}, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return {
      ok: response.ok,
      status: response.status,
      text: await response.text(),
    };
  } finally {
    clearTimeout(timer);
  }
}

function runtimeIdentityVerdict(configResponse) {
  const config = configResponse.body || {};
  const appTitle = String(config.appTitle || '');
  const interfaceConfig = config.interface || {};
  const defaultAgent = String(interfaceConfig.defaultAgent || '');
  const connectedAccountsEnabled = config.viventiumConnectedAccountsEnabled === true;
  const hasViventiumTitle = appTitle === 'Viventium';
  const hasDefaultAgent = defaultAgent === MAIN_AGENT_ID;
  const ok = configResponse.ok && hasViventiumTitle && hasDefaultAgent && connectedAccountsEnabled;
  const reasons = [];

  if (!configResponse.ok) {
    reasons.push(`api_config_http_${configResponse.status}`);
  }
  if (!hasViventiumTitle) {
    reasons.push('app_title_not_viventium');
  }
  if (!hasDefaultAgent) {
    reasons.push('default_agent_not_main_viventium');
  }
  if (!connectedAccountsEnabled) {
    reasons.push('connected_account_mode_not_enabled');
  }

  return {
    ok,
    reasons,
    public: {
      appTitle: scrubForPublic(appTitle || 'missing'),
      defaultAgentHash: defaultAgent ? hashValue(defaultAgent) : 'missing',
      connectedAccountsEnabled,
    },
  };
}

function loadSourceHashes() {
  const sourceAgent = path.join(
    LIBRECHAT_ROOT,
    'viventium',
    'source_of_truth',
    'local.viventium-agents.yaml',
  );
  const sourceLibreChat = path.join(
    LIBRECHAT_ROOT,
    'viventium',
    'source_of_truth',
    'local.librechat.yaml',
  );
  const compiled = path.join(REPO_ROOT, '.viventium', 'runtime', 'isolated', 'librechat.generated.yaml');

  return {
    source_agent: hashFileIfPresent(sourceAgent),
    source_librechat: hashFileIfPresent(sourceLibreChat),
    compiled_librechat: hashFileIfPresent(compiled),
  };
}

function debugLocalPromptFrameEnabled() {
  return process.env.VIVENTIUM_PROMPT_FRAME_DEBUG_LOCAL === '1';
}

function promptFrameLogFiles() {
  const root = path.join(PRIVATE_ROOT, 'prompt-observability', 'frame-logs');
  if (!fs.existsSync(root)) {
    return [];
  }
  const files = [];
  for (const day of fs.readdirSync(root, { withFileTypes: true })) {
    if (!day.isDirectory()) {
      continue;
    }
    const dayDir = path.join(root, day.name);
    for (const entry of fs.readdirSync(dayDir, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.endsWith('.jsonl')) {
        files.push(path.join(dayDir, entry.name));
      }
    }
  }
  return files.sort();
}

function capturePromptFrameCursor() {
  const cursor = {};
  for (const filePath of promptFrameLogFiles()) {
    try {
      cursor[filePath] = fs.statSync(filePath).size;
    } catch (_error) {
      cursor[filePath] = 0;
    }
  }
  return cursor;
}

function summarizePromptFrameDelta(cursor) {
  const frames = [];
  for (const filePath of promptFrameLogFiles()) {
    let start = cursor[filePath] || 0;
    let end = 0;
    try {
      end = fs.statSync(filePath).size;
    } catch (_error) {
      continue;
    }
    if (end <= start) {
      continue;
    }
    if (start > end) {
      start = 0;
    }
    const fd = fs.openSync(filePath, 'r');
    try {
      const buffer = Buffer.alloc(end - start);
      fs.readSync(fd, buffer, 0, buffer.length, start);
      for (const line of buffer.toString('utf8').split(/\r?\n/)) {
        if (!line.trim()) {
          continue;
        }
        try {
          const frame = JSON.parse(line);
          frames.push({
            prompt_family: scrubForPublic(frame.prompt_family || ''),
            surface: scrubForPublic(frame.surface || ''),
            provider_hash: hashValue(frame.provider || ''),
            model_hash: hashValue(frame.model || ''),
            layer_token_estimates: frame.layer_token_estimates || {},
            source_hashes: frame.source_hashes || {},
            mcp_instruction_sources: frame.mcp_instruction_sources || {},
          });
        } catch (_error) {
          // Ignore partial lines from an active async writer.
        }
      }
    } finally {
      fs.closeSync(fd);
    }
  }
  const maxLayerTokens = {};
  for (const frame of frames) {
    for (const [layer, tokens] of Object.entries(frame.layer_token_estimates || {})) {
      maxLayerTokens[layer] = Math.max(maxLayerTokens[layer] || 0, Number(tokens) || 0);
    }
  }
  const heavyLayers = Object.entries(maxLayerTokens)
    .filter(([, tokens]) => tokens >= 1000)
    .map(([layer, tokens]) => ({ layer, tokens }))
    .sort((left, right) => right.tokens - left.tokens);
  return scrubForPublic(
    JSON.stringify(
      {
        prompt_frames: frames.slice(0, 20),
        prompt_budget_analysis: {
          frame_count: frames.length,
          max_layer_tokens: maxLayerTokens,
          heavy_layers_over_1000_tokens: heavyLayers,
          budget_review_required: heavyLayers.length > 0,
        },
      },
      null,
      2,
    ),
  );
}

function flattenPromptCases(promptBank) {
  return (promptBank.families || []).flatMap((family) =>
    (family.cases || []).map((testCase) => ({
      familyId: family.id,
      familyGoal: family.goal,
      ...testCase,
      promptRefs: [
        ...new Set([
          ...((family.promptRefs || family.prompt_refs || []).map((item) => String(item))),
          ...((testCase.promptRefs || testCase.prompt_refs || []).map((item) => String(item))),
        ]),
      ],
    })),
  );
}

function runnablePromptCases(promptBank, filters = {}) {
  return flattenPromptCases(promptBank).filter((testCase) => caseMatchesFilters(testCase, filters));
}

function caseMatchesFilters(testCase, filters = {}) {
  if (filters.family && testCase.familyId !== filters.family) {
    return false;
  }
  if (filters.surface && (testCase.surface || 'web') !== filters.surface) {
    return false;
  }
  if (
    filters.promptId &&
    filters.promptId !== 'main.conscious_agent' &&
    !(testCase.promptRefs || []).includes(filters.promptId)
  ) {
    return false;
  }
  return true;
}

function buildCaseText(testCase, { includeSetup = true } = {}) {
  return [
    testCase.context,
    includeSetup ? testCase.setup : null,
    testCase.prompt,
  ].filter(Boolean).join('\n\n');
}

function buildChatPayload(testCase, args, overrides = {}) {
  const messageId = overrides.messageId || crypto.randomUUID();
  const text = overrides.text ?? buildCaseText(testCase);
  const surface = testCase.surface || 'web';
  const inputMode =
    surface === 'voice' || surface === 'wing'
      ? 'voice_call'
      : surface === 'listen_only'
        ? 'listen_only'
        : 'text';
  return {
    text,
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
    viventiumSurface: surface,
    viventiumInputMode: inputMode,
    viventiumListenOnly: surface === 'listen_only',
    isTemporary: true,
  };
}

function normalizeSeedPrompts(testCase) {
  if (Array.isArray(testCase.seed_prompts)) {
    return testCase.seed_prompts.map((item) => String(item || '').trim()).filter(Boolean);
  }
  return [];
}

function parseSseBlock(block) {
  const lines = block.split(/\r?\n/);
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
    }
  }
  if (dataLines.length === 0) {
    return null;
  }
  try {
    return JSON.parse(dataLines.join('\n'));
  } catch (_error) {
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
  const finalText = responseMessage?.text || responseMessage?.textOverride || extractTextFromContent(responseMessage?.content);
  if (finalText) {
    return finalText;
  }
  return events
    .map(
      (event) =>
        event?.text ||
        event?.delta ||
        event?.content ||
        event?.response?.text ||
        event?.responseMessage?.text ||
        extractTextFromContent(event?.responseMessage?.content) ||
        '',
    )
    .filter((value) => typeof value === 'string')
    .join('');
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
        if (part?.type === 'text') {
          if (typeof part.text === 'string') {
            return part.text;
          }
          if (typeof part.text?.value === 'string') {
            return part.text.value;
          }
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

function extractOpenAIOutputText(body) {
  if (typeof body?.output_text === 'string') {
    return body.output_text;
  }
  if (Array.isArray(body?.output)) {
    return body.output
      .flatMap((item) => item?.content || [])
      .map((part) => part?.text || part?.content || '')
      .filter(Boolean)
      .join('\n');
  }
  if (typeof body?.choices?.[0]?.message?.content === 'string') {
    return body.choices[0].message.content;
  }
  return '';
}

function parseJsonObject(text) {
  try {
    return JSON.parse(text);
  } catch (_error) {
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if (start >= 0 && end > start) {
      return JSON.parse(text.slice(start, end + 1));
    }
    throw _error;
  }
}

function caseAllowsEmptyResponse(testCase) {
  return (
    testCase.expected_surface === '{NTA}' ||
    testCase.expected_decision === 'suppress' ||
    testCase.surface === 'listen_only' ||
    testCase.surface === 'wing'
  );
}

function caseAllowsDuplicateResponse(testCase) {
  return (
    caseAllowsEmptyResponse(testCase) ||
    testCase.allow_duplicate_response_hash === true
  );
}

function caseAllowsUnresolvedAsync(testCase) {
  return testCase.allow_unresolved_async === true;
}

function isPendingCortexStatus(status) {
  return ['activating', 'brewing', 'running', 'pending'].includes(String(status || '').trim());
}

function resultHasResolvedRuntimeHoldEvidence(result) {
  if (!result?.hasRuntimeHold || !result?.hasCortexActivation) {
    return false;
  }
  const evidence = result.postCaseEvidence || {};
  return (
    Number(evidence.delayedMessageCount || 0) > 0 ||
    Number(evidence.cortexInsightCount || 0) > 0
  );
}

function hasRuntimeHold(events) {
  return (events || []).some((event) => {
    if (event?.final !== true || !Array.isArray(event.responseMessage?.content)) {
      return false;
    }
    return event.responseMessage.content.some((part) => Boolean(part?.viventium_runtime_hold));
  });
}

function buildJudgeSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    required: [
      'pass',
      'score',
      'rubric_results',
      'summary',
      'failure_mode',
      'confidence',
    ],
    properties: {
      pass: { type: 'boolean' },
      score: { type: 'number', minimum: 0, maximum: 1 },
      rubric_results: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          required: ['rubric_item', 'pass', 'evidence'],
          properties: {
            rubric_item: { type: 'string' },
            pass: { type: 'boolean' },
            evidence: { type: 'string' },
          },
        },
      },
      summary: { type: 'string' },
      failure_mode: {
        type: 'string',
        enum: [
          'none',
          'identity_or_style_regression',
          'truthfulness_or_live_data_risk',
          'tool_routing_risk',
          'surface_contract_risk',
          'privacy_or_plumbing_exposure',
          'nta_or_followup_regression',
          'unclear_or_insufficient_evidence',
        ],
      },
      confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
    },
  };
}

function effectiveRubricForExactRunner(testCase) {
  const excluded = new Set(
    Array.isArray(testCase.exact_runner_excluded_rubric_indices)
      ? testCase.exact_runner_excluded_rubric_indices
      : [],
  );
  return (testCase.rubric || []).filter((_, index) => !excluded.has(index));
}

function buildJudgePrompt(testCase, result) {
  const schema = buildJudgeSchema();
  const effectiveRubric = effectiveRubricForExactRunner(testCase);
  return [
    'Evaluate this Viventium prompt-architecture regression case. Judge only the behavior visible in the response against the rubric.',
    'Return exactly one JSON object matching the provided schema. Do not include markdown, code fences, prose, or extra keys.',
    'Do not reward verbosity. Do not require private data. If evidence is missing, mark that rubric item false.',
    'Range rubric note: if a rubric says "one or two", "1-2", or similar, one satisfying item is enough. Do not fail just because the response chose the lower end of the allowed range.',
    'Architecture-language note: if the user prompt itself asks about MCPs, Scheduling Cortex, GlassHive, prompts, or tool architecture, mentioning those user-provided concepts is not plumbing exposure by itself. Still fail raw IDs, metadata keys, hidden prompt tokens, no-response markers, memory key names, or unrelated internals.',
    'Citation marker note: web-search citation markers such as turn0search2 are acceptable user-facing source anchors when matching web_search_sources evidence is supplied. Do not classify matching citation anchors as plumbing exposure.',
    'Snippet-limitation note: if the response explicitly says the retrieved snippets/results do not directly support or confirm a precise rule, treat that as an honest evidence limitation, not as a fabricated page-content check.',
    'Conditional rubric note: if a rubric item is explicitly conditional ("if needed", "if unavailable", "when present") and the condition is not evidenced in this case, do not fail solely because the conditional behavior did not appear.',
    'Unavailable-condition note: a worker/tool case is not "unavailable" merely because the result is queued, deferred, accepted, or still in progress during the observation window. Only apply "if unavailable" rubric items when the response or evidence shows the tool was unavailable, disconnected, denied, or failed to start.',
    'Memory/context note: natural use of relevant user memory is allowed unless a rubric item explicitly forbids it. Phrases like "hidden prompt or memory keys" mean internal key names, prompt text, source metadata, IDs, or system plumbing, not ordinary personalized context.',
    'Clock note: for a "what time is it" case, allow normal elapsed clock drift during the run unless the prompt supplied an explicit timestamp to compare against.',
    'Runner scope note: this exact-model runner exercises the main chat endpoint with surface metadata for model behavior and prompt-frame evidence. True voice gateway, Wing Mode, Listen-Only bypass, Telegram, scheduler, and browser UI behavior are evaluated in the native-surface Playwright runner. If this case lists exact-runner exclusions, do not score those native-only rubric items here.',
    'Suppression note: when expected_decision is suppress, do not require the visible answer to reveal its private reasoning. If the supplied context contains a recent answer and repeated evidence, then an empty answer, {NTA}, or a short non-repeating acknowledgement can satisfy evidence-aware suppression.',
    'Hold/delayed-work note: for productivity, worker, scheduling, or cortex cases, a short hold such as "Checking now" is acceptable only when stream, prompt-frame, or delayed DB evidence shows a routed read-only/background path and either completed insight/delayed evidence, an explicit pending-callback contract for that case, or an honest limitation. A generic hold with still-pending statuses and no result evidence after the observation window is insufficient.',
    'Scheduling-tool evidence note: when runtime evidence shows schedule search/get/update tool calls, treat timezone and identity handling as satisfied by the tool-owned contract unless the visible response or tool evidence contradicts it. Do not require the assistant to expose timezone, identity, task IDs, metadata, or schedule internals in the user-facing answer.',
    'Pending-worker note: after a worker/tool call, a short acknowledgement such as "working on it", "checking now", or "I will send the result here" is not pretending to have inspected anything unless it claims a concrete finding, UI state, artifact, or completion without evidence.',
    'Direct-action callback-window note: do not fail a worker/delegation case solely because the callback or final inspection result did not arrive within this runner’s observation window. If native evidence shows a tool_call/delegation route and the visible text only promises future results, treat it as a valid pending delegation. Fail only if the answer claims completed inspection, concrete findings, or local UI state without verified evidence.',
    'Delayed-visible note: delayed_visible_text in post-case evidence is user-visible behavior. If it honestly reports completion, approval need, or a blocker, count that alongside the initial response; still fail it if the delayed text exposes raw IDs, provider names, queue mechanics, or internal plumbing.',
    'Observability note: prompt-frame token analysis is private QA telemetry. If prompt_budget_analysis reports heavy layers and budget_review_required=true, treat the measurement/flagging requirement as satisfied for this eval case.',
    'Verdict rule: if every listed rubric item is satisfied, pass the case; do not fail for an extra preference outside the supplied rubric.',
    '',
    'Required JSON Schema:',
    JSON.stringify(schema),
    '',
    `Case id: ${testCase.id}`,
    `Family: ${testCase.familyId}`,
    `Surface: ${testCase.surface || 'web'}`,
    `Expected visible surface: ${testCase.expected_surface || 'ordinary response'}`,
    `Expected decision: ${testCase.expected_decision || 'not specified'}`,
    `Exact-runner exclusions: ${(testCase.exact_runner_excluded_rubric_indices || []).join(', ') || 'none'}`,
    `Exact-runner notes: ${(testCase.exact_runner_notes || []).map(scrubForPublic).join(' | ') || 'none'}`,
    '',
    'Prompt/context sent to the system:',
    scrubForPublic(
      [
        testCase.context,
        ...(normalizeSeedPrompts(testCase).length
          ? normalizeSeedPrompts(testCase).map((seed, index) => `Prior seeded turn ${index + 1}: ${seed}`)
          : [testCase.setup].filter(Boolean)),
        `Evaluated prompt: ${testCase.prompt}`,
      ].filter(Boolean).join('\n\n'),
    ),
    '',
    'Rubric:',
    ...effectiveRubric.map((item, index) => `${index + 1}. ${item}`),
    '',
    'Sanitized response to evaluate:',
    result.responseForJudge || scrubForPublic(result.responsePreview || ''),
    '',
    'Sanitized runtime evidence from the streamed response:',
    result.eventEvidenceForJudge || 'none',
    '',
    'Sanitized prompt-frame telemetry captured during this case:',
    result.promptFrameEvidenceForJudge || 'none',
    '',
    'Sanitized delayed DB follow-up / cortex evidence observed after stream:',
    result.postCaseEvidenceForJudge || 'none',
  ].join('\n');
}

function validateJudgeJudgment(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ok: false, error: 'semantic_judge_invalid_shape:not_object' };
  }
  if (typeof value.pass !== 'boolean') {
    return { ok: false, error: 'semantic_judge_invalid_shape:pass_not_boolean' };
  }
  if (typeof value.score !== 'number' || value.score < 0 || value.score > 1) {
    return { ok: false, error: 'semantic_judge_invalid_shape:score_not_0_to_1_number' };
  }
  if (!Array.isArray(value.rubric_results)) {
    return { ok: false, error: 'semantic_judge_invalid_shape:rubric_results_not_array' };
  }
  if (typeof value.summary !== 'string') {
    return { ok: false, error: 'semantic_judge_invalid_shape:summary_not_string' };
  }
  if (typeof value.failure_mode !== 'string') {
    return { ok: false, error: 'semantic_judge_invalid_shape:failure_mode_not_string' };
  }
  if (typeof value.confidence !== 'string') {
    return { ok: false, error: 'semantic_judge_invalid_shape:confidence_not_string' };
  }
  return { ok: true };
}

async function callOpenAIJsonSchemaJudge({ apiKey, model, prompt, timeoutMs }) {
  const schema = buildJudgeSchema();
  const body = {
    model,
    input: [
      {
        role: 'system',
        content:
          'You are a strict QA judge for prompt-architecture regressions. Output only the requested JSON.',
      },
      { role: 'user', content: prompt },
    ],
    text: {
      format: {
        type: 'json_schema',
        name: 'viventium_prompt_eval_judgment',
        strict: true,
        schema,
      },
    },
    max_output_tokens: 1400,
  };
  const response = await fetchJson(
    'https://api.openai.com/v1/responses',
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        'User-Agent': BROWSER_USER_AGENT,
      },
      body: JSON.stringify(body),
    },
    timeoutMs,
  );
  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      error: `openai_responses_http_${response.status}`,
      bodyPreview: scrubForPublic(JSON.stringify(response.body || {}).slice(0, 500)),
    };
  }
  const text = extractOpenAIOutputText(response.body);
  const parsed = parseJsonObject(text);
  return {
    ok: true,
    status: response.status,
    judgment: parsed,
    rawHash: hashValue(text),
  };
}

async function callLocalAgentJsonJudge({ args, token, prompt, timeoutMs }) {
  const messageId = crypto.randomUUID();
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
    agent_id: args.judgeAgentId,
    model: args.judgeAgentId,
    viventiumSurface: 'web',
    viventiumInputMode: 'text',
    isTemporary: true,
  };
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      status: start.status,
      error: `local_agent_judge_start_http_${start.status}`,
      bodyPreview: scrubForPublic(JSON.stringify(start.body || {}).slice(0, 500)),
    };
  }
  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs,
  });
  if (!stream.ok) {
    return {
      ok: false,
      status: stream.status,
      error: `local_agent_judge_stream_${stream.error || stream.status}`,
      bodyPreview: scrubForPublic(stream.text.slice(0, 500)),
    };
  }
  const text = stream.text || '';
  try {
    return {
      ok: true,
      status: stream.status,
      judgment: parseJsonObject(text),
      rawHash: hashValue(text),
    };
  } catch (error) {
    return {
      ok: false,
      status: stream.status,
      error: `local_agent_judge_json_parse_failed:${scrubForPublic(error.message || 'unknown')}`,
      bodyPreview: scrubForPublic(text.slice(0, 500)),
    };
  }
}

function encodeEphemeralAgentId({ endpoint, model, sender }) {
  const encodePart = (value) => String(value || '').replace(/:/g, '__');
  return `${encodePart(endpoint)}__${encodePart(model)}___${encodePart(sender || 'SemanticJudge')}`;
}

async function callLocalEphemeralJsonJudge({ args, token, prompt, timeoutMs }) {
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
      'You are a strict semantic QA judge for Viventium prompt-regression tests. You are not Viventium. You do not answer the original user. You evaluate the supplied response against the supplied rubric and return exactly one JSON object matching the supplied schema.',
    temperature: 0,
    top_p: 1,
    max_tokens: 1600,
    ephemeralAgent: {},
    viventiumSurface: 'web',
    viventiumInputMode: 'text',
    isTemporary: true,
  };
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );
  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      status: start.status,
      error: `local_ephemeral_judge_start_http_${start.status}`,
      bodyPreview: scrubForPublic(JSON.stringify(start.body || {}).slice(0, 500)),
    };
  }
  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs,
  });
  if (!stream.ok) {
    return {
      ok: false,
      status: stream.status,
      error: `local_ephemeral_judge_stream_${stream.error || stream.status}`,
      bodyPreview: scrubForPublic(stream.text.slice(0, 500)),
    };
  }
  const text = stream.text || '';
  try {
    return {
      ok: true,
      status: stream.status,
      judgment: parseJsonObject(text),
      rawHash: hashValue(text),
    };
  } catch (error) {
    return {
      ok: false,
      status: stream.status,
      error: `local_ephemeral_judge_json_parse_failed:${scrubForPublic(error.message || 'unknown')}`,
      bodyPreview: scrubForPublic(text.slice(0, 500)),
    };
  }
}

async function callConfiguredJudge({ args, token, prompt, timeoutMs }) {
  if (args.judgeRoute === 'openai-direct') {
    const localEnv = loadLocalEnv();
    const apiKey = localEnv.OPENAI_API_KEY;
    if (!apiKey) {
      return {
        ok: false,
        status: 0,
        error: 'missing_OPENAI_API_KEY_for_semantic_judge',
      };
    }
    return callOpenAIJsonSchemaJudge({
      apiKey,
      model: args.judgeModel,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute === 'local-agent') {
    return callLocalAgentJsonJudge({
      args,
      token,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute === 'local-ephemeral') {
    return callLocalEphemeralJsonJudge({
      args,
      token,
      prompt,
      timeoutMs,
    });
  }
  if (args.judgeRoute !== 'local-agent') {
    return {
      ok: false,
      status: 0,
      error: `unsupported_semantic_judge_route:${scrubForPublic(args.judgeRoute)}`,
    };
  }
}

function semanticJudgeLabel(args, semanticJudge) {
  if (!semanticJudge?.enabled) {
    return 'disabled';
  }
  if (semanticJudge.blockedReason) {
    return `blocked:${semanticJudge.blockedReason}`;
  }
  return args.judgeRoute === 'openai-direct'
    ? 'openai_json_schema_semantic_judge'
    : args.judgeRoute === 'local-ephemeral'
      ? 'local_ephemeral_json_semantic_judge'
    : 'local_agent_json_semantic_judge';
}

async function judgeLiveResults(args, promptBank, liveResults, token) {
  if (!args.semanticJudge || liveResults.length === 0) {
    return {
      enabled: args.semanticJudge,
      blockedReason: args.semanticJudge && liveResults.length === 0 ? 'no_live_results_to_judge' : null,
      results: liveResults,
    };
  }

  const casesById = new Map(runnablePromptCases(promptBank).map((testCase) => [testCase.id, testCase]));
  const judgedResults = [];
  for (const result of liveResults) {
    const testCase = casesById.get(result.caseId);
    if (!testCase || result.status !== 'completed') {
      judgedResults.push(result);
      continue;
    }
    const prompt = buildJudgePrompt(testCase, result);
    try {
      const judge = await callConfiguredJudge({
        args,
        token,
        prompt,
        timeoutMs: Math.max(30_000, Math.min(args.timeoutMs, 120_000)),
      });
      const shape = judge.ok ? validateJudgeJudgment(judge.judgment) : { ok: false };
      judgedResults.push({
        ...result,
        semanticJudge: judge.ok && shape.ok
          ? {
              status: 'judged',
              pass: Boolean(judge.judgment?.pass),
              score: Number(judge.judgment?.score ?? 0),
              failureMode: judge.judgment?.failure_mode || 'unclear_or_insufficient_evidence',
              confidence: judge.judgment?.confidence || 'low',
              summary: scrubForPublic(judge.judgment?.summary || ''),
              rubricResults: Array.isArray(judge.judgment?.rubric_results)
                ? judge.judgment.rubric_results.map((item) => ({
                    rubricItem: scrubForPublic(item.rubric_item || ''),
                    pass: Boolean(item.pass),
                    evidence: scrubForPublic(item.evidence || ''),
                  }))
                : [],
              rawHash: judge.rawHash,
            }
          : {
              status: 'failed',
              pass: false,
              score: 0,
              failureMode: 'unclear_or_insufficient_evidence',
              confidence: 'low',
              summary: judge.error || shape.error,
              error: judge.error || shape.error,
              bodyPreview: judge.bodyPreview,
            },
      });
    } catch (error) {
      judgedResults.push({
        ...result,
        semanticJudge: {
          status: 'failed',
          pass: false,
          score: 0,
          failureMode: 'unclear_or_insufficient_evidence',
          confidence: 'low',
          summary: `judge_failed:${scrubForPublic(error.message || 'unknown')}`,
          error: `judge_failed:${scrubForPublic(error.message || 'unknown')}`,
        },
      });
    }
  }

  return {
    enabled: true,
    blockedReason: null,
    results: judgedResults,
  };
}

async function readSseToFinal({ apiBase, streamId, token, timeoutMs }) {
  const response = await fetch(`${apiBase}/api/agents/chat/stream/${encodeURIComponent(streamId)}`, {
    headers: { Authorization: `Bearer ${token}`, 'User-Agent': BROWSER_USER_AGENT },
  });
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
          await reader.cancel().catch(() => {});
          return {
            ok: event.error == null,
            status: response.status,
            events,
            text: extractVisibleText(events),
            error: event.error || null,
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
      error: `stream_read_failed:${scrubForPublic(error.message || error.name || 'unknown')}`,
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

async function runChatTurn({ args, token, testCase, text, conversationId = 'new', parentMessageId = NO_PARENT }) {
  const payload = buildChatPayload(testCase, args, {
    text,
    conversationId,
    parentMessageId,
  });
  const start = await fetchJson(
    `${args.apiBase}/api/agents/chat/agents`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'User-Agent': BROWSER_USER_AGENT,
      },
      body: JSON.stringify(payload),
    },
    30_000,
  );

  if (!start.ok || !start.body?.streamId) {
    return {
      ok: false,
      start,
      stream: null,
      payload,
      error: `chat_start_http_${start.status}`,
      finalMeta: {},
    };
  }

  const stream = await readSseToFinal({
    apiBase: args.apiBase,
    streamId: start.body.streamId,
    token,
    timeoutMs: args.timeoutMs,
  });
  return {
    ok: stream.ok,
    start,
    stream,
    payload,
    error: stream.error || null,
    finalMeta: extractFinalMeta(stream.events),
  };
}

function summarizeEventsForJudge(events) {
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
        direct_action_surfaces: Array.isArray(event.data.direct_action_surfaces)
          ? event.data.direct_action_surfaces.map(scrubForPublic)
          : [],
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
        cortex_updates: cortexUpdates.slice(0, 20),
        web_search_sources: webSearchSources.slice(0, 30),
        final_content: finalContent.slice(0, 20),
      },
      null,
      2,
    ),
  );
}

async function loginQaUser(args) {
  const password = process.env[QA_PASSWORD_ENV];
  if (!password) {
    if (args.localJwtFallback) {
      return createLocalQaJwt(args);
    }
    return {
      ok: false,
      reason: `missing_${QA_PASSWORD_ENV}`,
    };
  }

  const response = await fetchJson(
    `${args.apiBase}/api/auth/login`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: args.qaEmail,
        password,
      }),
    },
    20_000,
  );

  const userEmail = response.body?.user?.email || '';
  const ok = response.ok && response.body?.token && userEmail === args.qaEmail;
  return {
    ok,
    reason: ok ? null : `qa_login_http_${response.status}`,
    token: ok ? response.body.token : null,
    userId: ok ? String(response.body?.user?.id || response.body?.user?._id || '') : null,
    authMode: 'api_login',
    public: {
      authMode: 'api_login',
      userEmailHash: userEmail ? hashValue(userEmail) : 'missing',
      expectedEmailHash: hashValue(args.qaEmail),
    },
  };
}

async function createLocalQaJwt(args) {
  if (process.env.CI || process.env.NODE_ENV === 'production') {
    return {
      ok: false,
      reason: 'local_jwt_fallback_forbidden_in_ci_or_production',
      public: { authMode: 'local_jwt_fallback' },
    };
  }
  if (process.env[LOCAL_JWT_ALLOW_ENV] !== '1') {
    return {
      ok: false,
      reason: `local_jwt_fallback_requires_${LOCAL_JWT_ALLOW_ENV}`,
      public: { authMode: 'local_jwt_fallback' },
    };
  }

  const dotenv = parseEnvFile(path.join(LIBRECHAT_ROOT, '.env'));
  const mongoUri = process.env.MONGO_URI || dotenv.MONGO_URI;
  const jwtSecret = process.env.JWT_SECRET || dotenv.JWT_SECRET;
  if (!mongoUri || !jwtSecret) {
    return {
      ok: false,
      reason: 'missing_local_jwt_prerequisites',
      public: { authMode: 'local_jwt_fallback' },
    };
  }

  let client;
  try {
    const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
    const jwt = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'jsonwebtoken'));
    client = new MongoClient(mongoUri);
    await client.connect();
    const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
    const user = await client.db(dbName).collection('users').findOne({ email: args.qaEmail });
    if (!user?._id) {
      return {
        ok: false,
        reason: 'qa_user_not_found_for_local_jwt',
        public: { authMode: 'local_jwt_fallback' },
      };
    }
    const token = jwt.sign(
      {
        id: user._id.toString(),
        username: user.username,
        provider: user.provider,
        email: user.email,
      },
      jwtSecret,
      { expiresIn: '15m' },
    );
    return {
      ok: true,
      reason: null,
      token,
      userId: user._id.toString(),
      authMode: 'local_jwt_fallback',
      public: {
        authMode: 'local_jwt_fallback',
        userEmailHash: hashValue(user.email || ''),
        expectedEmailHash: hashValue(args.qaEmail),
      },
    };
  } catch (error) {
    return {
      ok: false,
      reason: `local_jwt_failed:${error.message}`,
      public: { authMode: 'local_jwt_fallback' },
    };
  } finally {
    if (client) {
      await client.close().catch(() => {});
    }
  }
}

async function connectLocalEvalDb() {
  const localEnv = loadLocalEnv();
  const mongoUri = localEnv.MONGO_URI;
  if (!mongoUri) {
    return { db: null, close: async () => {}, reason: 'missing_MONGO_URI' };
  }
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const client = new MongoClient(mongoUri);
  await client.connect();
  const dbName = new URL(mongoUri).pathname.replace(/^\//, '') || 'LibreChatViventium';
  return {
    db: client.db(dbName),
    close: () => client.close(),
    reason: null,
  };
}

async function observePostCaseDbEvidence({ db, result, maxObserveMs, followUpGraceMs }) {
  const conversationId = result?.finalMeta?.conversationId || '';
  if (!db || !conversationId) {
    return {
      observed: false,
      delayedMessageCount: 0,
      delayedVisibleText: '',
      cortexInsightCount: 0,
      cortexInsights: [],
      primaryCortexStatuses: [],
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
      cortexName: scrubForPublic(part.cortex_name || ''),
      status: scrubForPublic(part.status || ''),
      silent: Boolean(part.silent),
      noResponse: Boolean(part.no_response),
      insightHash: hashValue(part.insight || ''),
      insightPreview: scrubForPublic(String(part.insight || '').slice(0, 800)),
    }));
  return {
    observed: true,
    conversationIdHash: hashValue(conversationId),
    responseMessageIdHash: hashValue(responseMessageId),
    delayedMessageCount: delayed.length,
    delayedVisibleText: scrubForPublic(
      delayed.map((message) => contentToText(message.text || message.content)).join('\n\n').slice(0, 1600),
    ),
    delayedMessageHashes: delayed.map((message) => hashValue(message.messageId || '')),
    cortexInsightCount: cortexInsights.length,
    cortexInsights,
    primaryCortexStatuses: cortexItems.map((part) => scrubForPublic(part.status || '')).filter(Boolean),
  };
}

function summarizePostCaseEvidenceForJudge(postCaseEvidence) {
  if (!postCaseEvidence) {
    return 'none';
  }
  return scrubForPublic(
    JSON.stringify(
      {
        observed: Boolean(postCaseEvidence.observed),
        delayed_message_count: postCaseEvidence.delayedMessageCount || 0,
        delayed_visible_text: postCaseEvidence.delayedVisibleText || '',
        cortex_insight_count: postCaseEvidence.cortexInsightCount || 0,
        cortex_insights: (postCaseEvidence.cortexInsights || []).slice(0, 8),
        primary_cortex_statuses: postCaseEvidence.primaryCortexStatuses || [],
      },
      null,
      2,
    ),
  );
}

async function runLiveCases(args, promptBank, token, db = null, qaAuth = null) {
  const runnableCases = runnablePromptCases(promptBank, args).slice(0, args.maxCases);
  const results = [];
  const env = loadLocalEnv();

  for (const testCase of runnableCases) {
    const startedAt = Date.now();
    const promptFrameCursor = capturePromptFrameCursor();
    const seedPrompts = normalizeSeedPrompts(testCase);
    let conversationId = 'new';
    let parentMessageId = NO_PARENT;
    const seedEvidence = [];
    const fixtureEvidence = [];
    let failedSeed = null;

    if (needsStarterMorningBriefingFixture(testCase)) {
      const fixtureResult = await applyStarterMorningBriefingFixture({
        args,
        env,
        userId: qaAuth?.userId,
        agentId: args.agentId,
      }).catch((error) => ({
        ok: false,
        reason: `fixture_failed:${scrubForPublic(error.message || 'unknown')}`,
      }));
      fixtureEvidence.push(fixtureResult);
      if (!fixtureResult.ok) {
        results.push({
          caseId: testCase.id,
          familyId: testCase.familyId,
          surface: testCase.surface || 'web',
          status: 'failed_to_prepare_fixture',
          durationMs: Date.now() - startedAt,
          error: fixtureResult.reason || 'fixture_failed',
          requestHash: hashValue({ fixture: fixtureResult.fixture || 'starter_morning_briefing' }),
          responseHash: '',
          responsePreview: '',
          responseForJudge: '',
          eventEvidenceForJudge: 'none',
          promptFrameEvidenceForJudge: summarizePromptFrameDelta(promptFrameCursor),
          postCaseEvidenceForJudge: 'none',
          eventCount: 0,
          finalMeta: {},
          seedEvidence,
          fixtureEvidence,
          privateEvents: [],
        });
        continue;
      }
    }

    for (const seedText of seedPrompts) {
      const seedResult = await runChatTurn({
        args,
        token,
        testCase,
        text: seedText,
        conversationId,
        parentMessageId,
      });
      seedEvidence.push({
        ok: seedResult.ok,
        requestHash: hashValue(seedResult.payload),
        responseHash: hashValue(seedResult.stream?.text || ''),
        eventCount: seedResult.stream?.events?.length || 0,
      });
      if (!seedResult.ok || !seedResult.finalMeta.conversationId || !seedResult.finalMeta.responseMessageId) {
        failedSeed = seedResult;
        break;
      }
      conversationId = seedResult.finalMeta.conversationId;
      parentMessageId = seedResult.finalMeta.responseMessageId;
    }

    if (failedSeed) {
      results.push({
        caseId: testCase.id,
        familyId: testCase.familyId,
        surface: testCase.surface || 'web',
        status: 'failed_to_seed',
        durationMs: Date.now() - startedAt,
        error: failedSeed.error || 'seed_turn_failed',
        requestHash: hashValue(failedSeed.payload || {}),
        responseHash: hashValue(failedSeed.stream?.text || ''),
        responsePreview: scrubForPublic((failedSeed.stream?.text || '').slice(0, 300)),
        responseForJudge: scrubForPublic((failedSeed.stream?.text || '').slice(0, 4000)),
        eventEvidenceForJudge: summarizeEventsForJudge(failedSeed.stream?.events || []),
        promptFrameEvidenceForJudge: summarizePromptFrameDelta(promptFrameCursor),
        postCaseEvidenceForJudge: 'none',
        eventCount: failedSeed.stream?.events?.length || 0,
        finalMeta: failedSeed.finalMeta || {},
        seedEvidence,
        fixtureEvidence,
        privateEvents: failedSeed.stream?.events || [],
      });
      continue;
    }

    const promptText = buildCaseText(testCase, { includeSetup: seedPrompts.length === 0 });
    const turn = await runChatTurn({
      args,
      token,
      testCase,
      text: promptText,
      conversationId,
      parentMessageId,
    });
    const stream = turn.stream || { ok: false, events: [], text: '', error: turn.error };

    const responseText = stream.text || '';
    const emptyResponseAllowed = caseAllowsEmptyResponse(testCase);
    const completed = stream.ok && (responseText.trim() || emptyResponseAllowed);
    const turnEvidence = {
      finalMeta: turn.finalMeta || {},
      hasCortexActivation: hasCortexActivation(stream.events),
    };
    const observeMs = turnEvidence.hasCortexActivation
      ? args.postCaseObserveMs
      : Math.min(args.postCaseObserveMs, 2500);
    const postCaseEvidence = await observePostCaseDbEvidence({
      db,
      result: turnEvidence,
      maxObserveMs: observeMs,
      followUpGraceMs: args.followUpGraceMs,
    });

    results.push({
      caseId: testCase.id,
      familyId: testCase.familyId,
      surface: testCase.surface || 'web',
      status: completed ? 'completed' : 'failed',
      durationMs: Date.now() - startedAt,
      error: stream.error || (completed ? null : 'empty_visible_response'),
      requestHash: hashValue(turn.payload || {}),
      responseHash: hashValue(responseText),
      responsePreview: scrubForPublic(responseText.slice(0, 300)),
      responseForJudge: scrubForPublic(responseText.slice(0, 4000)),
      eventEvidenceForJudge: summarizeEventsForJudge(stream.events),
      promptFrameEvidenceForJudge: summarizePromptFrameDelta(promptFrameCursor),
      postCaseEvidenceForJudge: summarizePostCaseEvidenceForJudge(postCaseEvidence),
      eventCount: stream.events.length,
      finalMeta: turnEvidence.finalMeta,
      hasCortexActivation: turnEvidence.hasCortexActivation,
      hasRuntimeHold: hasRuntimeHold(stream.events),
      seedEvidence,
      fixtureEvidence,
      postCaseEvidence,
      privateEvents: stream.events,
    });
  }

  return results;
}

function casesByIdFromPromptBank(promptBank) {
  return new Map(runnablePromptCases(promptBank).map((testCase) => [testCase.id, testCase]));
}

function buildDuplicateResponseQualityFailures(liveResults, promptBank) {
  const casesById = casesByIdFromPromptBank(promptBank);
  const responseHashGroups = liveResults.reduce((acc, result) => {
    if (!result.responseHash || result.status !== 'completed') {
      return acc;
    }
    acc[result.responseHash] = acc[result.responseHash] || [];
    acc[result.responseHash].push(result.caseId);
    return acc;
  }, {});
  return Object.entries(responseHashGroups)
    .filter(([, caseIds]) => caseIds.length > 1)
    .map(([responseHash, caseIds]) => {
      const groupedResults = caseIds
        .map((caseId) => liveResults.find((result) => result.caseId === caseId))
        .filter(Boolean);
      const cases = caseIds.map((caseId) => casesById.get(caseId)).filter(Boolean);
      const allowedByCaseContract =
        cases.length > 0 && cases.every((testCase) => caseAllowsDuplicateResponse(testCase));
      const allowedResolvedHolds =
        groupedResults.length > 0 && groupedResults.every(resultHasResolvedRuntimeHoldEvidence);
      return {
        responseHash,
        caseIds,
        allowed: allowedByCaseContract || allowedResolvedHolds,
      };
    })
    .filter((group) => !group.allowed);
}

function buildUnresolvedAsyncQualityFailures(liveResults, promptBank) {
  const casesById = casesByIdFromPromptBank(promptBank);
  return liveResults.flatMap((result) => {
    const testCase = casesById.get(result.caseId);
    if (
      !testCase ||
      result.status !== 'completed' ||
      !result.hasCortexActivation ||
      !result.hasRuntimeHold ||
      caseAllowsEmptyResponse(testCase) ||
      caseAllowsUnresolvedAsync(testCase)
    ) {
      return [];
    }
    const evidence = result.postCaseEvidence || {};
    const pendingStatuses = (evidence.primaryCortexStatuses || []).filter(isPendingCortexStatus);
    const hasResolvedUserVisibleOrInsightEvidence =
      Number(evidence.delayedMessageCount || 0) > 0 ||
      Number(evidence.cortexInsightCount || 0) > 0;
    if (pendingStatuses.length === 0 || hasResolvedUserVisibleOrInsightEvidence) {
      return [];
    }
    return [
      {
        caseId: result.caseId,
        responseHash: result.responseHash,
        pendingStatuses,
      },
    ];
  });
}

function writeReports({
  args,
  promptBank,
  runtime,
  login,
  sourceHashes,
  liveResults,
  blockedReason,
  semanticJudge,
}) {
  ensureDir(args.outputDir);
  ensureDir(path.dirname(args.publicReport));

  const allCases = flattenPromptCases(promptBank);
  const runnableCases = runnablePromptCases(promptBank, args);
  const selectedCaseCount = Math.min(args.maxCases, runnableCases.length);
  const selectedCaseLimitLabel =
    args.maxCases >= runnableCases.length ? `all (${runnableCases.length})` : String(args.maxCases);
  const allCompleted =
    liveResults.length > 0 && liveResults.every((result) => result.status === 'completed');
  const fullCoverage =
    allCompleted &&
    liveResults.length === allCases.length &&
    liveResults.length === runnableCases.length;
  const responseHashGroups = liveResults.reduce((acc, result) => {
    if (!result.responseHash) {
      return acc;
    }
    acc[result.responseHash] = acc[result.responseHash] || [];
    acc[result.responseHash].push(result.caseId);
    return acc;
  }, {});
  const duplicateResponseHashes = Object.entries(responseHashGroups)
    .filter(([, caseIds]) => caseIds.length > 1)
    .map(([responseHash, caseIds]) => ({ responseHash, caseIds }));
  const duplicateResponseQualityFailures = buildDuplicateResponseQualityFailures(liveResults, promptBank);
  const unresolvedAsyncQualityFailures = buildUnresolvedAsyncQualityFailures(liveResults, promptBank);
  const judgedResults = liveResults.filter((result) => result.semanticJudge?.status === 'judged');
  const semanticFailedResults = liveResults.filter(
    (result) => result.semanticJudge && result.semanticJudge.pass !== true,
  );
  const semanticJudgeBlocked = Boolean(semanticJudge?.blockedReason);
  const completionFailed = liveResults.some((result) => result.status !== 'completed');
  const qualityFailed =
    duplicateResponseQualityFailures.length > 0 || unresolvedAsyncQualityFailures.length > 0;
  const semanticFailed =
    Boolean(args.semanticJudge) && (semanticJudgeBlocked || semanticFailedResults.length > 0);
  const status = blockedReason
    ? 'blocked'
    : completionFailed
      ? 'failed_completion'
      : semanticFailed
        ? 'semantic_failed'
        : qualityFailed
          ? 'quality_failed'
          : fullCoverage && args.semanticJudge
            ? 'completed_full_semantic_passed'
            : fullCoverage
              ? 'completed_full'
              : allCompleted && args.semanticJudge
                ? 'partial_semantic_passed'
                : allCompleted
                  ? 'partial_baseline'
                  : 'partial_or_failed';
  const summary = {
    generatedAt: new Date().toISOString(),
    status,
    blockedReason,
    runnerHash: hashFileIfPresent(__filename),
    apiBaseHash: hashValue(args.apiBase),
    runLiveRequested: args.runLive,
    promptBankHash: hashFileIfPresent(args.promptBank),
    agentIdHash: hashValue(args.agentId),
    promptFamilies: (promptBank.families || []).length,
    promptCases: allCases.length,
    runnablePromptCases: runnableCases.length,
    filters: {
      family: args.family || null,
      surface: args.surface || null,
      promptId: args.promptId || null,
    },
    selectedCaseLimit: selectedCaseLimitLabel,
    selectedCaseCount,
    surfacesInBank: [...new Set(allCases.map((testCase) => testCase.surface || 'web'))].sort(),
    surfacesRun: [...new Set(liveResults.map((result) => result.surface || 'web'))].sort(),
    runtime,
    debugLocalPromptFrameEnabled: debugLocalPromptFrameEnabled(),
    login: login?.public || null,
    sourceHashes,
    resultCount: liveResults.length,
    completedCount: liveResults.filter((result) => result.status === 'completed').length,
    failedCount: liveResults.filter((result) => result.status !== 'completed').length,
    behavioralGrading: semanticJudge?.enabled
      ? semanticJudgeLabel(args, semanticJudge)
      : 'disabled',
    judgeModelHash: semanticJudge?.enabled
      ? hashValue(`${args.judgeRoute}:${args.judgeRoute === 'local-agent' ? args.judgeAgentId : `${args.judgeEndpoint}:${args.judgeModel}`}`)
      : null,
    semanticJudgedCount: judgedResults.length,
    semanticPassedCount: judgedResults.filter((result) => result.semanticJudge?.pass === true).length,
    semanticFailedCount: semanticFailedResults.length,
    semanticJudgeBlockedReason: semanticJudge?.blockedReason || null,
    duplicateResponseHashes,
    duplicateResponseQualityFailures,
    unresolvedAsyncQualityFailures,
  };

  const privateJsonPath = path.join(args.outputDir, 'exact-model-eval.json');
  fs.writeFileSync(
    privateJsonPath,
    JSON.stringify(
      {
        summary,
        args: {
          apiBase: args.apiBase,
          promptBank: args.promptBank,
          qaEmailHash: hashValue(args.qaEmail),
          agentIdHash: hashValue(args.agentId),
          family: args.family || null,
          surface: args.surface || null,
          promptId: args.promptId || null,
          localJwtFallback: args.localJwtFallback,
          maxCases: args.maxCases,
          timeoutMs: args.timeoutMs,
          postCaseObserveMs: args.postCaseObserveMs,
          followUpGraceMs: args.followUpGraceMs,
          semanticJudge: args.semanticJudge,
          judgeRoute: args.judgeRoute,
          judgeModelHash: args.semanticJudge
            ? hashValue(`${args.judgeRoute}:${args.judgeRoute === 'local-agent' ? args.judgeAgentId : `${args.judgeEndpoint}:${args.judgeModel}`}`)
            : null,
        },
        liveResults,
      },
      null,
      2,
    ),
  );

  const publicLines = [
    '# Prompt Registry Slice: Exact-Model Completion Baseline',
    '',
    `Generated: ${summary.generatedAt}`,
    '',
    '## Status',
    '',
    `- Status: ${summary.status}`,
    `- Live run requested: ${summary.runLiveRequested ? 'yes' : 'no'}`,
    `- Blocked reason: ${summary.blockedReason || 'none'}`,
    `- Prompt families: ${summary.promptFamilies}`,
    `- Prompt cases: ${summary.promptCases}`,
    `- Agent hash: ${summary.agentIdHash}`,
    `- Runner hash: ${summary.runnerHash || 'missing'}`,
    `- Runnable cases for this runner: ${summary.runnablePromptCases}`,
    `- Selected case limit: ${summary.selectedCaseLimit}`,
    `- Post-case observation window ms: ${args.postCaseObserveMs}`,
    `- Async follow-up grace after cortex completion ms: ${args.followUpGraceMs}`,
    `- Result count: ${summary.resultCount}`,
    `- Completed: ${summary.completedCount}`,
    `- Failed/blocked: ${summary.failedCount}`,
    `- Behavioral grading: ${summary.behavioralGrading}`,
    `- Semantic judged: ${summary.semanticJudgedCount}`,
    `- Semantic passed: ${summary.semanticPassedCount}`,
    `- Semantic failed: ${summary.semanticFailedCount}`,
    `- Semantic judge blocked reason: ${summary.semanticJudgeBlockedReason || 'none'}`,
    `- Judge model hash: ${summary.judgeModelHash || 'not used'}`,
    `- Duplicate response hashes: ${summary.duplicateResponseHashes.length}`,
    `- Duplicate response quality failures: ${summary.duplicateResponseQualityFailures.length}`,
    `- Unresolved async quality failures: ${summary.unresolvedAsyncQualityFailures.length}`,
    `- Surfaces in bank: ${summary.surfacesInBank.join(', ') || 'none'}`,
    `- Surface metadata exercised: ${summary.surfacesRun.join(', ') || 'none'}`,
    '',
    '## Runtime Gate',
    '',
    `- API base hash: ${summary.apiBaseHash}`,
    `- Runtime identity: ${summary.runtime.identity.ok ? 'pass' : 'fail'}`,
    `- Runtime reasons: ${summary.runtime.identity.reasons.join(', ') || 'none'}`,
    `- App title: ${summary.runtime.identity.public.appTitle}`,
    `- Connected-account mode: ${summary.runtime.identity.public.connectedAccountsEnabled ? 'enabled' : 'not enabled'}`,
    `- Prompt debug-local gate: ${summary.debugLocalPromptFrameEnabled ? 'enabled' : 'disabled'}`,
    `- QA auth mode: ${summary.login?.authMode || 'not attempted'}`,
    '',
    '## Source Hashes',
    '',
    `- Agent source hash: ${summary.sourceHashes.source_agent || 'missing'}`,
    `- LibreChat source hash: ${summary.sourceHashes.source_librechat || 'missing'}`,
    `- Compiled LibreChat hash: ${summary.sourceHashes.compiled_librechat || 'missing'}`,
    '',
    '## Results',
    '',
    '| Case | Family | Surface | Status | Semantic | Duration ms | Response hash | Error |',
    '| --- | --- | --- | --- | --- | ---: | --- | --- |',
    ...liveResults.map((result) =>
      `| ${scrubForPublic(result.caseId)} | ${scrubForPublic(result.familyId)} | ${scrubForPublic(result.surface)} | ${result.status} | ${
        result.semanticJudge
          ? result.semanticJudge.pass
            ? `pass ${Number(result.semanticJudge.score || 0).toFixed(2)}`
            : `fail ${Number(result.semanticJudge.score || 0).toFixed(2)} ${scrubForPublic(result.semanticJudge.failureMode || '')}`
          : 'not run'
      } | ${result.durationMs || 0} | ${result.responseHash || ''} | ${scrubForPublic(result.error || result.semanticJudge?.error || '')} |`,
    ),
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
    '## Notes',
    '',
    '- Raw eval JSON and response previews are private-only.',
    '- Public output stores hashes, counts, statuses, and sanitized errors only.',
    '- When semantic judging is enabled, the runner uses a structured JSON judge and validates the returned shape locally. The `openai-direct` judge route uses provider-enforced JSON Schema; local account routes use prompt-constrained JSON plus local schema validation.',
    '- Duplicate response hashes are informational for intentional silence/suppression cases and resolved runtime holds, but fail the run when unrelated non-silent final answers collapse into the same visible answer.',
    '- Runtime-hold responses fail the run when cortex/tool work remains only pending after the observation window and no delayed or insight evidence arrived.',
    '- Semantic judge prompts and raw results are private-only; this public report stores only pass/fail counts, scores, hashes, and sanitized failure modes.',
    '- The harness fails closed on wrong runtime identity before model calls.',
    '- Source YAML and compiled YAML hashes are reported separately and are expected to differ when promptRefs render into plain LibreChat strings.',
    '- Treat prompt-bundle and runtime-config drift checks, not source-vs-compiled YAML hash equality, as the live prompt-registry drift gate.',
    '- `partial_baseline` and `partial_semantic_passed` mean the run completed only the selected subset, not the full prompt bank.',
    '- This completion-baseline runner uses the main chat endpoint with surface metadata; true voice, Telegram, scheduler, Wing, and Listen-Only surface runners remain separate gates.',
    '',
  ];

  fs.writeFileSync(args.publicReport, `${publicLines.join('\n')}\n`);

  return {
    summary,
    privateJsonPath,
    publicReport: args.publicReport,
  };
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  const promptBank = readJson(args.promptBank);
  const sourceHashes = loadSourceHashes();
  const health = await fetchText(`${args.apiBase}/health`, {}, 10_000).catch((error) => ({
    ok: false,
    status: 0,
    text: error.message,
  }));
  const config = await fetchJson(`${args.apiBase}/api/config`, {}, 10_000).catch((error) => ({
    ok: false,
    status: 0,
    body: { error: error.message },
  }));
  const identity = runtimeIdentityVerdict(config);
  const runtime = {
    health: {
      ok: health.ok,
      status: health.status,
      bodyHash: hashValue(health.text || ''),
    },
    identity,
  };

  let blockedReason = null;
  let login = null;
  let liveResults = [];
  let semanticJudge = { enabled: args.semanticJudge, blockedReason: null, results: [] };
  let dbHandle = null;

  if (!health.ok) {
    blockedReason = `api_health_http_${health.status}`;
  } else if (!identity.ok) {
    blockedReason = `runtime_identity_failed:${identity.reasons.join(',')}`;
  } else if (debugLocalPromptFrameEnabled()) {
    blockedReason = 'prompt_frame_debug_local_enabled';
  } else if (!args.runLive) {
    blockedReason = `live_eval_disabled_set_${LIVE_RUN_FLAG}_or_pass_--run-live`;
  } else {
    login = await loginQaUser(args);
    if (!login.ok) {
      blockedReason = login.reason;
    } else {
      try {
        dbHandle = await connectLocalEvalDb();
      } catch (error) {
        dbHandle = { db: null, close: async () => {}, reason: `db_connect_failed:${scrubForPublic(error.message || 'unknown')}` };
      }
      try {
        liveResults = await runLiveCases(args, promptBank, login.token, dbHandle.db, login);
        semanticJudge = await judgeLiveResults(args, promptBank, liveResults, login.token);
        liveResults = semanticJudge.results;
      } finally {
        if (dbHandle) {
          await dbHandle.close().catch(() => {});
        }
      }
    }
  }

  const report = writeReports({
    args,
    promptBank,
    runtime,
    login,
    sourceHashes,
    liveResults,
    blockedReason,
    semanticJudge,
  });

  console.log(
    JSON.stringify(
      {
        status: report.summary.status,
        blockedReason: report.summary.blockedReason,
        resultCount: report.summary.resultCount,
        completedCount: report.summary.completedCount,
        failedCount: report.summary.failedCount,
        semanticJudgedCount: report.summary.semanticJudgedCount,
        semanticPassedCount: report.summary.semanticPassedCount,
        semanticFailedCount: report.summary.semanticFailedCount,
        duplicateResponseQualityFailureCount:
          report.summary.duplicateResponseQualityFailures.length,
        unresolvedAsyncQualityFailureCount:
          report.summary.unresolvedAsyncQualityFailures.length,
        publicReport: path.relative(REPO_ROOT, report.publicReport),
        privateJsonPathHash: hashValue(report.privateJsonPath),
        privateJsonWritten: true,
      },
      null,
      2,
    ),
  );

  if (
    blockedReason ||
    liveResults.some((result) => result.status !== 'completed') ||
    report.summary.duplicateResponseQualityFailures.length > 0 ||
    report.summary.unresolvedAsyncQualityFailures.length > 0 ||
    (args.semanticJudge &&
      (semanticJudge.blockedReason || liveResults.some((result) => result.semanticJudge?.pass !== true)))
  ) {
    process.exitCode = 1;
  }
}

run().catch((error) => {
  console.error(
    JSON.stringify(
      {
        error: scrubForPublic(error.message),
        stack: scrubForPublic(error.stack),
      },
      null,
      2,
    ),
  );
  process.exit(1);
});
