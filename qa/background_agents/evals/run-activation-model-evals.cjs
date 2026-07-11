#!/usr/bin/env node
'use strict';

/* === VIVENTIUM START ===
 * Feature: Prompt Workbench Phase A activation-model evaluations.
 * Purpose: Exercise the real BackgroundCortexService classifier against the canonical public-safe
 * prompt bank, measuring per-cortex precision, recall, sibling leakage, consistency, provider
 * attempts, and latency without duplicating prompt ownership or writing live agent state.
 * === VIVENTIUM END === */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const LIBRECHAT_ROOT = path.join(REPO_ROOT, 'viventium_v0_4', 'LibreChat');
const DEFAULT_PROMPT_BANK = path.join(
  REPO_ROOT,
  'qa',
  'prompt-architecture',
  'evals',
  'prompt-bank.json',
);
const DEFAULT_SOURCE_BUNDLE = path.join(
  LIBRECHAT_ROOT,
  'viventium',
  'source_of_truth',
  'local.viventium-agents.yaml',
);
const DEFAULT_PRIVATE_ROOT = path.join(
  os.homedir(),
  'Library',
  'Application Support',
  'Viventium',
  'private-user-data',
  'prompt-workbench',
  'activation-evals',
);
const ACTIVATION_FAMILY_RUNNER = 'background_activation';

function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

function parseArgs(argv) {
  const outputDir = path.join(DEFAULT_PRIVATE_ROOT, timestampSlug());
  const args = {
    promptBank: DEFAULT_PROMPT_BANK,
    sourceBundle: DEFAULT_SOURCE_BUNDLE,
    outputDir,
    publicReport: path.join(outputDir, 'public-safe-report.md'),
    runLive: process.env.VIVENTIUM_RUN_ACTIVATION_EVALS === '1',
    family: '',
    surface: '',
    caseId: '',
    promptId: '',
    provider: '',
    model: '',
    maxCases: Number.MAX_SAFE_INTEGER,
    repetitions: 1,
    concurrency: 6,
    timeoutMs: 2000,
    preserveFallbacks: false,
  };

  for (const arg of argv) {
    if (arg === '--run-live') {
      args.runLive = true;
    } else if (arg === '--no-live') {
      args.runLive = false;
    } else if (arg === '--with-fallbacks') {
      args.preserveFallbacks = true;
    } else if (arg.startsWith('--prompt-bank=')) {
      args.promptBank = path.resolve(arg.slice('--prompt-bank='.length));
    } else if (arg.startsWith('--source-bundle=')) {
      args.sourceBundle = path.resolve(arg.slice('--source-bundle='.length));
    } else if (arg.startsWith('--output-dir=')) {
      args.outputDir = path.resolve(arg.slice('--output-dir='.length));
    } else if (arg.startsWith('--public-report=')) {
      args.publicReport = path.resolve(arg.slice('--public-report='.length));
    } else if (arg.startsWith('--family=')) {
      args.family = arg.slice('--family='.length).trim();
    } else if (arg.startsWith('--surface=')) {
      args.surface = arg.slice('--surface='.length).trim();
    } else if (arg.startsWith('--case-id=')) {
      args.caseId = arg.slice('--case-id='.length).trim();
    } else if (arg.startsWith('--prompt-id=')) {
      args.promptId = arg.slice('--prompt-id='.length).trim();
    } else if (arg.startsWith('--provider=')) {
      args.provider = arg.slice('--provider='.length).trim();
    } else if (arg.startsWith('--model=')) {
      args.model = arg.slice('--model='.length).trim();
    } else if (arg.startsWith('--max-cases=')) {
      args.maxCases = positiveInt(
        arg.slice('--max-cases='.length),
        args.maxCases,
      );
    } else if (arg.startsWith('--repetitions=')) {
      args.repetitions = positiveInt(
        arg.slice('--repetitions='.length),
        args.repetitions,
      );
    } else if (arg.startsWith('--concurrency=')) {
      args.concurrency = positiveInt(
        arg.slice('--concurrency='.length),
        args.concurrency,
      );
    } else if (arg.startsWith('--timeout-ms=')) {
      args.timeoutMs = positiveInt(
        arg.slice('--timeout-ms='.length),
        args.timeoutMs,
      );
    }
  }
  return args;
}

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function hashValue(value, length = 16) {
  return crypto
    .createHash('sha256')
    .update(String(value || ''))
    .digest('hex')
    .slice(0, length);
}

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const values = {};
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) {
      continue;
    }
    const separator = line.indexOf('=');
    const key = line.slice(0, separator).trim();
    let value = line.slice(separator + 1).trim();
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

function loadCanonicalRuntimeEnv() {
  const runtimeRoot = path.join(
    os.homedir(),
    'Library',
    'Application Support',
    'Viventium',
    'runtime',
  );
  const candidates = [
    path.join(runtimeRoot, 'runtime.env'),
    path.join(runtimeRoot, 'runtime.local.env'),
    path.join(runtimeRoot, 'service-env', 'librechat.env'),
    path.join(LIBRECHAT_ROOT, '.env'),
  ];
  return candidates.reduce(
    (merged, filePath) => Object.assign(merged, parseEnvFile(filePath)),
    { ...process.env },
  );
}

function loadActivationFamily(promptBank, args) {
  const families = (promptBank.families || []).filter(
    (family) => family?.runner === ACTIVATION_FAMILY_RUNNER,
  );
  const family = args.family
    ? families.find((row) => row.id === args.family)
    : families.find((row) => {
        if (!args.promptId) {
          return true;
        }
        return (row.promptRefs || []).includes(args.promptId);
      });
  if (!family) {
    throw new Error('activation_eval_family_not_found');
  }
  return family;
}

function selectCases(family, args) {
  return (family.cases || [])
    .filter((testCase) => !args.surface || testCase.surface === args.surface)
    .filter((testCase) => !args.caseId || testCase.id === args.caseId)
    .slice(0, args.maxCases);
}

function selectTargets(family, args) {
  const targets = family.activationTargets || [];
  if (!args.promptId) {
    return targets;
  }
  return targets.filter((target) => target.promptRef === args.promptId);
}

function validateFamily(family, cases, targets) {
  if (!Array.isArray(targets) || targets.length === 0) {
    throw new Error('activation_eval_targets_missing');
  }
  const targetKeys = new Set(
    (family.activationTargets || []).map((target) => String(target.key || '')),
  );
  if (targetKeys.has('')) {
    throw new Error('activation_eval_target_key_missing');
  }
  if (!Array.isArray(cases) || cases.length === 0) {
    throw new Error('activation_eval_cases_missing');
  }
  for (const testCase of cases) {
    const required = new Set(testCase.required_activations || []);
    const allowed = new Set(testCase.allowed_activations || []);
    if (!Array.isArray(testCase.messages) || testCase.messages.length === 0) {
      throw new Error(
        `activation_eval_messages_missing:${testCase.id || 'unknown'}`,
      );
    }
    for (const key of required) {
      if (!allowed.has(key) || !targetKeys.has(key)) {
        throw new Error(
          `activation_eval_invalid_required_target:${testCase.id || 'unknown'}`,
        );
      }
    }
    for (const key of allowed) {
      if (!targetKeys.has(key)) {
        throw new Error(
          `activation_eval_invalid_allowed_target:${testCase.id || 'unknown'}`,
        );
      }
    }
  }
}

function writePreview(args, family, cases, targets) {
  const createdAt = new Date().toISOString();
  const summary = {
    mode: 'preview',
    status: 'preview',
    createdAt,
    familyId: family.id,
    selectedCaseCount: cases.length,
    selectedTargetCount: targets.length,
    plannedClassifierCallCount:
      cases.length * targets.length * args.repetitions,
    repetitions: args.repetitions,
  };
  writeArtifacts(args, { summary, results: [] });
  return { summary, results: [] };
}

function loadResolvedSourceBundle(sourceBundle) {
  const yaml = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'js-yaml'));
  const { resolvePromptRefs } = require(
    path.join(LIBRECHAT_ROOT, 'scripts', 'viventium-sync-agents.js'),
  );
  const parsed = yaml.load(fs.readFileSync(sourceBundle, 'utf8'));
  return resolvePromptRefs(parsed);
}

function sourceCortexByAgentId(bundle) {
  const rows = bundle?.mainAgent?.background_cortices;
  if (!Array.isArray(rows)) {
    throw new Error('source_bundle_background_cortices_missing');
  }
  return new Map(rows.map((row) => [row.agent_id, row]));
}

function buildReqConfig(bundle) {
  const config =
    bundle?.config && typeof bundle.config === 'object' ? bundle.config : {};
  config.viventium = config.viventium || {};
  config.viventium.background_cortices =
    config.viventium.background_cortices || {};
  config.viventium.background_cortices.activation_format = config.viventium
    .background_cortices.activation_format || {
    response_format: `Respond with a JSON object:\n{\n  "should_activate": true,\n  "confidence": 1.0,\n  "reason": "2-4 explanatory words"\n}`,
  };
  return config;
}

async function runWithConcurrency(tasks, limit) {
  const results = new Array(tasks.length);
  let nextIndex = 0;
  async function worker() {
    while (nextIndex < tasks.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await tasks[index]();
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(limit, tasks.length) }, () => worker()),
  );
  return results;
}

async function runOneClassifier({
  args,
  bundle,
  reqConfig,
  checkCortexActivation,
  cortexById,
  target,
  testCase,
  repetition,
}) {
  const source = cortexById.get(target.agentId);
  if (!source?.activation) {
    return failedResult({
      target,
      testCase,
      repetition,
      error: 'source_activation_missing',
    });
  }
  const activation = {
    ...source.activation,
    enabled: true,
    cooldown_ms: 0,
    provider: args.provider || source.activation.provider,
    model: args.model || source.activation.model,
    fallbacks: args.preserveFallbacks ? source.activation.fallbacks || [] : [],
  };
  const userScope = hashValue(
    `${testCase.id}:${target.key}:${repetition}:${Date.now()}`,
    12,
  );
  const startedAt = Date.now();
  let outcome = null;
  let error = null;
  try {
    outcome = await checkCortexActivation({
      cortexConfig: { ...source, agent_id: target.agentId, activation },
      messages: testCase.messages,
      runId: `activation-eval-${userScope}`,
      req: {
        config: reqConfig,
        user: { id: `activation-eval-${userScope}`, role: 'ADMIN' },
        body: {
          conversationId: `activation-eval-${userScope}`,
          viventiumSurface: testCase.surface || 'web',
          viventiumInputMode: testCase.surface === 'voice' ? 'voice' : 'text',
        },
      },
      mainAgent: bundle.mainAgent,
      timeoutMs: args.timeoutMs,
    });
  } catch (caught) {
    error = sanitizeError(caught);
  }

  const required = (testCase.required_activations || []).includes(target.key);
  const allowed = (testCase.allowed_activations || []).includes(target.key);
  const classified = classifyActivationOutcome(outcome);
  const actual = classified.actual;
  const pass =
    error == null &&
    actual !== null &&
    (required ? actual : allowed || !actual);
  return {
    caseId: testCase.id,
    familyId: testCase.familyId,
    surface: testCase.surface || 'web',
    targetKey: target.key,
    promptRef: target.promptRef,
    repetition,
    required,
    allowed,
    actual,
    pass,
    confidence: outcome?.confidence ?? null,
    reason: String(outcome?.reason || '').slice(0, 120),
    durationMs: Date.now() - startedAt,
    providerUsed: outcome?.providerUsed || activation.provider,
    modelUsed: outcome?.modelUsed || activation.model,
    providerAttempts: summarizeProviderAttempts(outcome?.providerAttempts),
    error: error || classified.error,
  };
}

function classifyActivationOutcome(outcome) {
  if (!outcome || typeof outcome !== 'object') {
    return {
      available: false,
      actual: null,
      error: 'activation_outcome_missing',
    };
  }
  const attempts = Array.isArray(outcome.providerAttempts)
    ? outcome.providerAttempts
    : [];
  const hasCompletedAttempt = attempts.some(
    (attempt) => attempt?.status === 'completed',
  );
  const terminalReason = String(outcome.reason || '')
    .trim()
    .toLowerCase();
  const unavailableReason =
    terminalReason === 'global_timeout' ||
    terminalReason === 'provider_unavailable' ||
    terminalReason === 'activation_provider_unavailable';
  if (unavailableReason || (attempts.length > 0 && !hasCompletedAttempt)) {
    return {
      available: false,
      actual: null,
      error: unavailableReason
        ? terminalReason
        : 'activation_provider_unavailable',
    };
  }
  return {
    available: true,
    actual: Boolean(outcome.shouldActivate),
    error: null,
  };
}

function failedResult({ target, testCase, repetition, error }) {
  return {
    caseId: testCase.id,
    surface: testCase.surface || 'web',
    targetKey: target.key,
    promptRef: target.promptRef,
    repetition,
    required: (testCase.required_activations || []).includes(target.key),
    allowed: (testCase.allowed_activations || []).includes(target.key),
    actual: null,
    pass: false,
    confidence: null,
    reason: '',
    durationMs: 0,
    providerUsed: '',
    modelUsed: '',
    providerAttempts: [],
    error,
  };
}

function summarizeProviderAttempts(attempts) {
  return (Array.isArray(attempts) ? attempts : []).map((attempt) => ({
    provider: String(attempt?.provider || ''),
    model: String(attempt?.model || ''),
    source: String(attempt?.source || ''),
    status: String(attempt?.status || ''),
    shouldActivate:
      typeof attempt?.shouldActivate === 'boolean'
        ? attempt.shouldActivate
        : null,
    error: attempt?.error
      ? {
          class: String(attempt.error.class || ''),
          status: attempt.error.status ?? null,
          code: String(attempt.error.code || ''),
          message: sanitizeError(attempt.error.message || ''),
        }
      : null,
  }));
}

function sanitizeError(error) {
  return String(error?.message || error || 'activation_eval_failed')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '<email>')
    .replace(/\/Users\/[^\s)]+/g, '<path>')
    .replace(/sk-[A-Za-z0-9._-]+/g, 'sk-<redacted>')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, 'Bearer <redacted>')
    .replace(/\s+/g, ' ')
    .slice(0, 240);
}

function percentile(values, percentileValue) {
  if (!values.length) {
    return 0;
  }
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil((percentileValue / 100) * sorted.length) - 1),
  );
  return sorted[index];
}

function summarizeResults({
  args,
  family,
  cases,
  targets,
  results,
  startedAt,
}) {
  const completed = results.filter(
    (result) => result.actual !== null && !result.error,
  );
  const unavailable = results.filter(
    (result) => result.actual === null || Boolean(result.error),
  );
  const failures = results.filter((result) => !result.pass);
  const requiredRows = results.filter((result) => result.required);
  const completedRequiredRows = requiredRows.filter(
    (result) => result.actual !== null && !result.error,
  );
  const activatedRows = results.filter((result) => result.actual === true);
  const falsePositives = results.filter(
    (result) => result.actual === true && !result.allowed,
  );
  const falseNegatives = results.filter(
    (result) => result.required && result.actual === false,
  );
  const unavailableRequired = results.filter(
    (result) =>
      result.required && (result.actual === null || Boolean(result.error)),
  );
  const timeoutRows = results.filter(
    (result) =>
      /timeout/i.test(result.error || result.reason || '') ||
      result.providerAttempts.some((attempt) => attempt.status === 'error'),
  );
  const caseGroups = new Map();
  for (const result of results) {
    const key = `${result.caseId}:${result.repetition}`;
    if (!caseGroups.has(key)) {
      caseGroups.set(key, []);
    }
    caseGroups.get(key).push(result);
  }
  const failedCaseRuns = [...caseGroups.entries()]
    .filter(([, rows]) => rows.some((row) => !row.pass))
    .map(([key, rows]) => ({
      key,
      missingRequired: rows
        .filter((row) => row.required && row.actual !== true)
        .map((row) => row.targetKey),
      forbiddenActivated: rows
        .filter((row) => row.actual === true && !row.allowed)
        .map((row) => row.targetKey),
      unavailable: rows
        .filter((row) => row.actual === null)
        .map((row) => row.targetKey),
    }));
  const consistencyGroups = new Map();
  const optionalActivationGroups = new Map();
  const availabilityGroups = new Map();
  for (const result of results) {
    const key = `${result.caseId}:${result.targetKey}`;
    if (result.actual !== null && !result.error) {
      const targetGroups = result.allowed && !result.required
        ? optionalActivationGroups
        : consistencyGroups;
      if (!targetGroups.has(key)) {
        targetGroups.set(key, new Set());
      }
      targetGroups.get(key).add(String(result.actual));
    }
    if (!availabilityGroups.has(key)) {
      availabilityGroups.set(key, new Set());
    }
    availabilityGroups
      .get(key)
      .add(String(result.actual !== null && !result.error));
  }
  const semanticInconsistentDecisionCount = [
    ...consistencyGroups.values(),
  ].filter((decisions) => decisions.size > 1).length;
  const optionalActivationVarianceCount = [
    ...optionalActivationGroups.values(),
  ].filter((decisions) => decisions.size > 1).length;
  const availabilityFlapCount = [...availabilityGroups.values()].filter(
    (states) => states.size > 1,
  ).length;
  const perTarget = targets.map((target) => {
    const rows = results.filter((result) => result.targetKey === target.key);
    const durations = rows
      .map((result) => result.durationMs)
      .filter((value) => value > 0);
    const targetRequired = rows.filter((result) => result.required);
    const targetCompletedRequired = targetRequired.filter(
      (result) => result.actual !== null && !result.error,
    );
    const targetActivated = rows.filter((result) => result.actual === true);
    return {
      key: target.key,
      passCount: rows.filter((result) => result.pass).length,
      resultCount: rows.length,
      requiredRecall:
        targetRequired.length === 0
          ? 1
          : targetRequired.filter((result) => result.actual === true).length /
            targetRequired.length,
      semanticRequiredRecall:
        targetCompletedRequired.length === 0
          ? 1
          : targetCompletedRequired.filter((result) => result.actual === true)
              .length / targetCompletedRequired.length,
      activationPrecision:
        targetActivated.length === 0
          ? 1
          : targetActivated.filter((result) => result.allowed).length /
            targetActivated.length,
      falsePositiveCount: rows.filter(
        (result) => result.actual === true && !result.allowed,
      ).length,
      falseNegativeCount: rows.filter(
        (result) => result.required && result.actual === false,
      ).length,
      unavailableRequiredCount: rows.filter(
        (result) =>
          result.required && (result.actual === null || Boolean(result.error)),
      ).length,
      p50Ms: percentile(durations, 50),
      p95Ms: percentile(durations, 95),
    };
  });
  const durations = completed.map((result) => result.durationMs);
  const allUnavailable = completed.length === 0 && results.length > 0;
  const status = allUnavailable
    ? 'blocked'
    : failures.length > 0
      ? 'failed'
      : 'passed';
  return {
    mode: 'live',
    status,
    createdAt: new Date().toISOString(),
    familyId: family.id,
    sourceBundleHash: hashValue(fs.readFileSync(args.sourceBundle, 'utf8')),
    promptBankHash: hashValue(fs.readFileSync(args.promptBank, 'utf8')),
    selectedCaseCount: cases.length,
    selectedTargetCount: targets.length,
    repetitions: args.repetitions,
    resultCount: results.length,
    completedCount: completed.length,
    passCount: results.filter((result) => result.pass).length,
    failureCount: failures.length,
    failedCaseRunCount: failedCaseRuns.length,
    requiredRecall:
      requiredRows.length === 0
        ? 1
        : requiredRows.filter((result) => result.actual === true).length /
          requiredRows.length,
    endToEndRequiredRecall:
      requiredRows.length === 0
        ? 1
        : requiredRows.filter((result) => result.actual === true).length /
          requiredRows.length,
    semanticRequiredRecall:
      completedRequiredRows.length === 0
        ? 1
        : completedRequiredRows.filter((result) => result.actual === true)
            .length / completedRequiredRows.length,
    activationPrecision:
      activatedRows.length === 0
        ? 1
        : activatedRows.filter((result) => result.allowed).length /
          activatedRows.length,
    falsePositiveCount: falsePositives.length,
    falseNegativeCount: falseNegatives.length,
    unavailableCount: unavailable.length,
    unavailableRequiredCount: unavailableRequired.length,
    completionRate:
      results.length === 0 ? 1 : completed.length / results.length,
    timeoutOrProviderErrorCount: timeoutRows.length,
    inconsistentDecisionCount: semanticInconsistentDecisionCount,
    semanticInconsistentDecisionCount,
    optionalActivationVarianceCount,
    availabilityFlapCount,
    p50Ms: percentile(durations, 50),
    p95Ms: percentile(durations, 95),
    maxMs: durations.length ? Math.max(...durations) : 0,
    wallDurationMs: Date.now() - startedAt,
    providerOverride: args.provider || null,
    modelOverride: args.model || null,
    fallbacksEnabled: args.preserveFallbacks,
    failedCaseRuns,
    perTarget,
  };
}

function writeArtifacts(args, payload) {
  ensureDir(args.outputDir);
  ensureDir(path.dirname(args.publicReport));
  fs.writeFileSync(
    path.join(args.outputDir, 'activation-model-eval.json'),
    `${JSON.stringify(payload, null, 2)}\n`,
  );
  fs.writeFileSync(args.publicReport, renderPublicReport(payload.summary));
}

function renderPublicReport(summary) {
  const lines = [
    '# Background Activation Model Eval',
    '',
    `- Mode: ${summary.mode}`,
    `- Status: ${summary.status}`,
    `- Family: ${summary.familyId}`,
    `- Selected cases: ${summary.selectedCaseCount}`,
    `- Selected cortex targets: ${summary.selectedTargetCount}`,
    `- Repetitions: ${summary.repetitions}`,
  ];
  if (summary.mode === 'preview') {
    lines.push(
      `- Planned classifier calls: ${summary.plannedClassifierCallCount}`,
      '- No model calls were made; this is selection validation, not performance evidence.',
      '',
    );
    return `${lines.join('\n')}\n`;
  }
  lines.push(
    `- Pass: ${summary.passCount}/${summary.resultCount}`,
    `- End-to-end required recall: ${(summary.endToEndRequiredRecall * 100).toFixed(1)}%`,
    `- Semantic required recall (completed calls): ${(summary.semanticRequiredRecall * 100).toFixed(1)}%`,
    `- Activation precision: ${(summary.activationPrecision * 100).toFixed(1)}%`,
    `- False positives: ${summary.falsePositiveCount}`,
    `- False negatives: ${summary.falseNegativeCount}`,
    `- Completed calls: ${summary.completedCount}/${summary.resultCount} (${(summary.completionRate * 100).toFixed(1)}%)`,
    `- Unavailable required calls: ${summary.unavailableRequiredCount}`,
    `- Timeout/provider errors: ${summary.timeoutOrProviderErrorCount}`,
    `- Inconsistent repeated semantic decisions: ${summary.semanticInconsistentDecisionCount}`,
    `- Optional allowed-activation variance: ${summary.optionalActivationVarianceCount}`,
    `- Availability flaps across repetitions: ${summary.availabilityFlapCount}`,
    `- Classifier latency p50/p95/max: ${summary.p50Ms}/${summary.p95Ms}/${summary.maxMs} ms`,
    `- Wall duration: ${summary.wallDurationMs} ms`,
    `- Source bundle hash: ${summary.sourceBundleHash}`,
    `- Prompt bank hash: ${summary.promptBankHash}`,
    '',
    '## Per-cortex metrics',
    '',
    '| Cortex key | Pass | E2E recall | Semantic recall | Precision | FP | FN | Unavailable required | p50 | p95 |',
    '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    ...(summary.perTarget || []).map(
      (row) =>
        `| ${row.key} | ${row.passCount}/${row.resultCount} | ${(row.requiredRecall * 100).toFixed(1)}% | ${(row.semanticRequiredRecall * 100).toFixed(1)}% | ${(row.activationPrecision * 100).toFixed(1)}% | ${row.falsePositiveCount} | ${row.falseNegativeCount} | ${row.unavailableRequiredCount} | ${row.p50Ms} ms | ${row.p95Ms} ms |`,
    ),
    '',
    'Raw prompts, responses, account identifiers, and provider request details are private-only.',
    '',
  );
  return `${lines.join('\n')}\n`;
}

async function runLive(args, family, cases, targets) {
  const env = loadCanonicalRuntimeEnv();
  Object.assign(process.env, env);
  process.env.CONFIG_BYPASS_VALIDATION =
    process.env.CONFIG_BYPASS_VALIDATION || 'true';
  process.chdir(LIBRECHAT_ROOT);
  require(path.join(LIBRECHAT_ROOT, 'node_modules', 'module-alias'))({
    base: path.join(LIBRECHAT_ROOT, 'api'),
  });
  const { checkCortexActivation } = require(
    path.join(
      LIBRECHAT_ROOT,
      'api',
      'server',
      'services',
      'BackgroundCortexService.js',
    ),
  );
  const bundle = loadResolvedSourceBundle(args.sourceBundle);
  const reqConfig = buildReqConfig(bundle);
  const cortexById = sourceCortexByAgentId(bundle);
  const startedAt = Date.now();
  const tasks = [];
  for (let repetition = 1; repetition <= args.repetitions; repetition += 1) {
    for (const testCase of cases) {
      for (const target of targets) {
        tasks.push(() =>
          runOneClassifier({
            args,
            bundle,
            reqConfig,
            checkCortexActivation,
            cortexById,
            target,
            testCase,
            repetition,
          }),
        );
      }
    }
  }
  const results = await runWithConcurrency(tasks, args.concurrency);
  const summary = summarizeResults({
    args,
    family,
    cases,
    targets,
    results,
    startedAt,
  });
  const payload = { summary, results };
  writeArtifacts(args, payload);
  return payload;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  ensureDir(args.outputDir);
  const promptBank = readJson(args.promptBank);
  const family = loadActivationFamily(promptBank, args);
  const cases = selectCases(family, args);
  const targets = selectTargets(family, args);
  validateFamily(family, cases, targets);
  const payload = args.runLive
    ? await runLive(args, family, cases, targets)
    : writePreview(args, family, cases, targets);
  process.stdout.write(
    `${JSON.stringify({
      status: payload.summary.status,
      mode: payload.summary.mode,
      selectedCaseCount: payload.summary.selectedCaseCount,
      selectedTargetCount: payload.summary.selectedTargetCount,
      resultCount: payload.summary.resultCount || 0,
      passCount: payload.summary.passCount || 0,
    })}\n`,
  );
  if (payload.summary.status === 'blocked') {
    process.exitCode = 2;
  } else if (payload.summary.status === 'failed') {
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main()
    .then(() => process.exit(process.exitCode || 0))
    .catch((error) => {
      const args = parseArgs(process.argv.slice(2));
      const summary = {
        mode: args.runLive ? 'live' : 'preview',
        status: 'blocked',
        familyId: args.family || 'background_activation_routing',
        selectedCaseCount: 0,
        selectedTargetCount: 0,
        repetitions: args.repetitions,
        blockedReason: sanitizeError(error),
      };
      writeArtifacts(args, { summary, results: [] });
      process.stderr.write(`${summary.blockedReason}\n`);
      process.exit(2);
    });
}

module.exports = {
  classifyActivationOutcome,
  loadActivationFamily,
  parseArgs,
  percentile,
  selectCases,
  selectTargets,
  summarizeResults,
  validateFamily,
};
