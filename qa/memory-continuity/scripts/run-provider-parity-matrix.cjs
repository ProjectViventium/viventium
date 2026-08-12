#!/usr/bin/env node
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const PROMPT_BANK_PATH = path.join(
  REPO_ROOT,
  'qa/prompt-architecture/evals/prompt-bank.json',
);
const EVAL_RUNNER_PATH = path.join(
  REPO_ROOT,
  'qa/prompt-architecture/evals/run-exact-model-evals.cjs',
);
const VOICE_QA_HELPER_PATH = path.join(
  REPO_ROOT,
  'qa/modern-playground-voice/scripts/tts_artifact_browser_qa.cjs',
);
const DEFAULT_PUBLIC_REPORT = path.join(
  REPO_ROOT,
  `qa/memory-continuity/reports/${new Date().toISOString().slice(0, 10)}-direct-provider-continuity-matrix.md`,
);
const MATRIX_CATEGORIES = [
  'preference_constraint',
  'temporal_precision',
  'numeric_precision',
  'multilingual_paraphrase',
];

const promptBank = JSON.parse(fs.readFileSync(PROMPT_BANK_PATH, 'utf8'));
const memoryRecallFamily = promptBank.families.find((family) => family.id === 'memory_recall');
const MATRIX_CASES = MATRIX_CATEGORIES.map((category) => {
  const testCase = (memoryRecallFamily?.cases || []).find(
    (candidate) =>
      candidate?.fixture?.conversationRecall?.coverageCategory === category,
  );
  if (!testCase) {
    throw new Error(`provider_parity_case_missing:${category}`);
  }
  return {
    id: testCase.id,
    category,
    prompt: testCase.prompt,
    seedCorpusPrompts: testCase.fixture.conversationRecall.seedCorpusPrompts,
    requiredResponseFragments:
      testCase.fixture.conversationRecall.requiredResponseFragments,
    forbiddenResponseFragments:
      testCase.fixture.conversationRecall.forbiddenResponseFragments || [],
    requireSemanticRetrieval:
      testCase.fixture.conversationRecall.requireSemanticRetrieval === true,
  };
});

function hashValue(value) {
  return crypto
    .createHash('sha256')
    .update(typeof value === 'string' ? value : JSON.stringify(value))
    .digest('hex')
    .slice(0, 16);
}

function parseEnvFile(filePath) {
  const values = {};
  if (!filePath || !fs.existsSync(filePath)) return values;
  for (const rawLine of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const match = rawLine.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    values[match[1]] = match[2].trim().replace(/^['"](.*)['"]$/, '$1');
  }
  return values;
}

function loadProviderParityEnv(voiceQa) {
  const runtimeEnvPath = path.join(
    process.env.HOME || '',
    'Library/Application Support/Viventium/runtime/runtime.env',
  );
  return {
    ...voiceQa.loadEnv(),
    ...parseEnvFile(runtimeEnvPath),
    ...process.env,
  };
}

function dbNameFromMongoUri(uri) {
  return new URL(uri).pathname.replace(/^\//, '') || 'LibreChatViventium';
}

function parseSseBlock(block) {
  const data = String(block || '')
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice('data:'.length).trimStart())
    .join('\n');
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch (_error) {
    return { raw: data };
  }
}

function contentText(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content
    .map((part) => {
      if (typeof part === 'string') return part;
      if (part?.type !== 'text') return '';
      if (typeof part.text === 'string') return part.text;
      return typeof part.text?.value === 'string' ? part.text.value : '';
    })
    .filter(Boolean)
    .join('\n\n');
}

function visibleText(events) {
  const finalEvent = [...(events || [])]
    .reverse()
    .find((event) => event && event.final != null);
  const message = finalEvent?.responseMessage || finalEvent?.message || {};
  const finalText = message.text || message.textOverride || contentText(message.content);
  if (finalText) return finalText;
  return (events || [])
    .map(
      (event) =>
        event?.text ||
        (typeof event?.delta === 'string' ? event.delta : '') ||
        (typeof event?.content === 'string' ? event.content : '') ||
        contentText(event?.data?.delta?.content) ||
        (typeof event?.data?.delta?.text === 'string' ? event.data.delta.text : '') ||
        '',
    )
    .filter((value) => typeof value === 'string')
    .join('');
}

async function readVoiceStream({ apiBase, streamId, headers, timeoutMs = 180_000 }) {
  const response = await fetch(
    `${apiBase}/api/viventium/voice/stream/${encodeURIComponent(streamId)}`,
    { headers },
  );
  if (!response.ok || !response.body) {
    return { ok: false, status: response.status, events: [], text: '', error: `stream_http_${response.status}` };
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const startedAt = Date.now();
  let buffer = '';
  const events = [];
  while (Date.now() - startedAt < timeoutMs) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (!event) continue;
      events.push(event);
      if (event.final != null || event.error != null) {
        await reader.cancel().catch(() => {});
        return {
          ok: event.error == null,
          status: response.status,
          events,
          text: visibleText(events),
          error: event.error || null,
        };
      }
    }
  }
  await reader.cancel().catch(() => {});
  return {
    ok: false,
    status: response.status,
    events,
    text: visibleText(events),
    error: 'stream_timeout',
  };
}

async function patchRecallPreference({ apiBase, token, enabled, fetchJson }) {
  const response = await fetchJson(`${apiBase}/api/memories/preferences`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'User-Agent': 'ViventiumProviderParityQA/1.0',
    },
    body: JSON.stringify({ conversation_recall: enabled }),
  });
  if (!response.ok || response.body?.preferences?.conversation_recall !== enabled) {
    throw new Error(`conversation_recall_preference_http_${response.status}`);
  }
}

function renderPublicReport(summary) {
  const lines = [
    '<!-- qa-evidence-exempt: Controlled direct-provider continuity artifact; full-view user-grade acceptance is owned by the universal cognitive-continuity report. -->',
    '',
    `# Direct-provider continuity matrix — ${summary.generatedAt.slice(0, 10)}`,
    '',
    `- Status: ${summary.status}`,
    `- Provider route: ${summary.providerRoute}`,
    `- Cases: ${summary.completedCount}/${summary.resultCount} passed`,
    `- Fixture cleanup: ${summary.cleanupVerified ? 'verified' : 'failed'}`,
    `- Original recall preference restored: ${summary.preferenceRestored ? 'yes' : 'no'}`,
    '',
    '| Category | Status | Duration ms | Native file_search | Unexpected tools | Error |',
    '| --- | --- | ---: | ---: | ---: | --- |',
  ];
  for (const result of summary.results) {
    lines.push(
      `| ${result.category} | ${result.status} | ${result.durationMs} | ${result.nativeFileSearchCompletedCount} | ${result.unexpectedNativeToolCount} | ${result.error || ''} |`,
    );
  }
  lines.push(
    '',
    'Synthetic non-personal fixtures were inserted into isolated prior conversations and removed after each case. Raw prompts and responses remain in private local QA output; this report stores only categories, hashes, counts, timings, and failure classes.',
    '',
  );
  return lines.join('\n');
}

async function runProviderParityMatrix(options = {}) {
  const voiceQa = require(VOICE_QA_HELPER_PATH);
  const evalRunner = require(EVAL_RUNNER_PATH);
  voiceQa.requireLocalQaAuth();
  const env = loadProviderParityEnv(voiceQa);
  const requiredEnv = ['MONGO_URI', 'JWT_SECRET', 'JWT_REFRESH_SECRET', 'VIVENTIUM_CALL_SESSION_SECRET'];
  for (const key of requiredEnv) {
    if (!env[key]) throw new Error(`missing_${key}`);
  }
  const apiBase = String(options.apiBase || process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180').replace(/\/$/, '');
  const { MongoClient } = require(path.join(voiceQa.LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const mongo = new MongoClient(env.MONGO_URI);
  await mongo.connect();
  const db = mongo.db(dbNameFromMongoUri(env.MONGO_URI));
  const auth = await voiceQa.createQaAuth({ env, db });
  const user = await db.collection('users').findOne(
    { _id: auth.user._id },
    { projection: { 'personalization.conversation_recall': 1 } },
  );
  const originalRecallEnabled = user?.personalization?.conversation_recall === true;
  const agent = await db.collection('agents').findOne(
    { id: voiceQa.DEFAULT_AGENT_ID },
    { projection: { provider: 1, model: 1, voice_llm_provider: 1, voice_llm_model: 1 } },
  );
  const directProvider = String(agent?.voice_llm_provider || '').trim();
  if (!directProvider || directProvider === 'glasshive-harness') {
    throw new Error('direct_voice_provider_not_configured');
  }

  const selectedCases = Array.isArray(options.categories) && options.categories.length
    ? MATRIX_CASES.filter((matrixCase) => options.categories.includes(matrixCase.category))
    : MATRIX_CASES;
  const results = [];
  const fixtureConversationIds = [];
  let preferenceRestored = false;
  let cleanupVerified = false;
  try {
    await patchRecallPreference({
      apiBase,
      token: auth.accessToken,
      enabled: true,
      fetchJson: voiceQa.fetchJson,
    });
    for (const matrixCase of selectedCases) {
      const startedAt = Date.now();
      const runNonce = crypto.randomBytes(8).toString('hex');
      const corpusStateBeforeFixture = await evalRunner.readConversationRecallCorpusState({
        db,
        userId: auth.userId,
      });
      const fixture = evalRunner.conversationRecallFixtureFor(
        {
          fixture: {
            conversationRecall: {
              enabled: true,
              coverageCategory: matrixCase.category,
              seedCorpusPrompts: matrixCase.seedCorpusPrompts,
              requiredResponseFragments: matrixCase.requiredResponseFragments,
              forbiddenResponseFragments: matrixCase.forbiddenResponseFragments,
              requireNativeHostTool: true,
              forbidNativeCommandExecution: true,
            },
          },
        },
        runNonce,
      );
      const corpus = await evalRunner.insertConversationRecallCorpusFixture({
        db,
        userId: auth.userId,
        agentId: voiceQa.DEFAULT_AGENT_ID,
        prompts: fixture.seedCorpusPrompts,
      });
      fixtureConversationIds.push(corpus.conversationId);
      let call = null;
      try {
        if (matrixCase.requireSemanticRetrieval) {
          await patchRecallPreference({
            apiBase,
            token: auth.accessToken,
            enabled: true,
            fetchJson: voiceQa.fetchJson,
          });
          await evalRunner.waitForConversationRecallCorpusRefresh({
            db,
            userId: auth.userId,
            previousState: corpusStateBeforeFixture,
            timeoutMs: options.semanticRefreshTimeoutMs || 240_000,
          });
        }
        const callResponse = await voiceQa.fetchJson(`${apiBase}/api/viventium/calls`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${auth.accessToken}`,
            'Content-Type': 'application/json',
            'User-Agent': 'ViventiumProviderParityQA/1.0',
          },
          body: JSON.stringify({ conversationId: 'new', agentId: voiceQa.DEFAULT_AGENT_ID }),
        });
        if (!callResponse.ok || !callResponse.body?.callSessionId) {
          throw new Error(`call_session_http_${callResponse.status}`);
        }
        call = callResponse.body;
        const jobId = `provider-parity-${crypto.randomUUID()}`;
        const requestedStreamId = `provider-parity-${crypto.randomUUID()}`;
        const voiceHeaders = {
          'X-VIVENTIUM-CALL-SESSION': call.callSessionId,
          'X-VIVENTIUM-CALL-SECRET': env.VIVENTIUM_CALL_SESSION_SECRET,
          'X-VIVENTIUM-JOB-ID': jobId,
          'X-VIVENTIUM-WORKER-ID': 'provider-parity-qa',
          'X-VIVENTIUM-REQUEST-ID': requestedStreamId,
          'Content-Type': 'application/json',
        };
        const chatResponse = await voiceQa.fetchJson(`${apiBase}/api/viventium/voice/chat`, {
          method: 'POST',
          headers: voiceHeaders,
          body: JSON.stringify({
            text: matrixCase.prompt,
            streamId: requestedStreamId,
            voiceMode: true,
            voiceProvider: 'xai',
            viventiumTextDeltaMode: 'auto',
            viventiumInputMode: 'voice_call',
            viventiumSurface: 'voice',
          }),
        });
        if (!chatResponse.ok || !chatResponse.body?.streamId) {
          throw new Error(`voice_chat_http_${chatResponse.status}`);
        }
        const stream = await readVoiceStream({
          apiBase,
          streamId: chatResponse.body.streamId,
          headers: voiceHeaders,
          timeoutMs: options.timeoutMs || 180_000,
        });
        const audit = await evalRunner.auditConversationRecallExecution({
          env,
          responseMessageId: '',
          fixture,
          responseText: stream.text,
          responseEvents: stream.events,
        });
        const failures = [...(stream.ok ? [] : [stream.error || 'voice_stream_failed']), ...audit.failures];
        results.push({
          caseId: matrixCase.id,
          category: matrixCase.category,
          status: failures.length ? 'failed' : 'completed',
          durationMs: Date.now() - startedAt,
          responseHash: hashValue(stream.text || ''),
          error: failures[0] || null,
          nativeFileSearchCompletedCount:
            audit.evidence?.nativeFileSearchCompletedCount || 0,
          unexpectedNativeToolCount:
            audit.evidence?.unexpectedNativeToolNameHashes?.length || 0,
          missingRequiredCount:
            audit.evidence?.missingRequiredFragmentHashes?.length || 0,
          presentForbiddenCount:
            audit.evidence?.presentForbiddenFragmentHashes?.length || 0,
          privateEvidence: {
            responseText: stream.text,
            responseEvents: stream.events,
          },
        });
      } catch (error) {
        results.push({
          caseId: matrixCase.id,
          category: matrixCase.category,
          status: 'failed',
          durationMs: Date.now() - startedAt,
          responseHash: '',
          error: String(error?.message || error),
          nativeFileSearchCompletedCount: 0,
          unexpectedNativeToolCount: 0,
          missingRequiredCount: 0,
          presentForbiddenCount: 0,
        });
      } finally {
        if (call?.callSessionId) {
          await voiceQa.cleanupCallArtifacts(db, {
            userId: auth.userId,
            callSessionId: call.callSessionId,
            conversationId: call.conversationId,
          }).catch(() => {});
        }
        await db.collection('messages').deleteMany({ conversationId: corpus.conversationId });
        await db.collection('conversations').deleteOne({ conversationId: corpus.conversationId });
      }
    }
  } finally {
    await patchRecallPreference({
      apiBase,
      token: auth.accessToken,
      enabled: originalRecallEnabled,
      fetchJson: voiceQa.fetchJson,
    }).catch(() => {});
    const restoredUser = await db.collection('users').findOne(
      { _id: auth.user._id },
      { projection: { 'personalization.conversation_recall': 1 } },
    );
    preferenceRestored =
      (restoredUser?.personalization?.conversation_recall === true) ===
      originalRecallEnabled;
    const leftoverConversations = await db.collection('conversations').countDocuments({
      conversationId: { $in: fixtureConversationIds },
    });
    const leftoverMessages = await db.collection('messages').countDocuments({
      conversationId: { $in: fixtureConversationIds },
    });
    cleanupVerified = leftoverConversations === 0 && leftoverMessages === 0;
    await auth.cleanup().catch(() => {});
    await mongo.close();
  }

  const completedCount = results.filter((result) => result.status === 'completed').length;
  const summary = {
    generatedAt: new Date().toISOString(),
    status:
      results.length > 0 &&
      completedCount === results.length && preferenceRestored && cleanupVerified
        ? 'passed'
        : 'failed',
    providerRoute: `${directProvider}/${String(agent?.voice_llm_model || '')}`,
    providerRouteHash: hashValue({
      provider: directProvider,
      model: agent?.voice_llm_model || '',
    }),
    resultCount: results.length,
    completedCount,
    preferenceRestored,
    cleanupVerified,
    results,
  };
  const privateRoot =
    process.env.VIVENTIUM_PROMPT_ARCH_PRIVATE_DIR ||
    path.join(
      process.env.HOME,
      'Library/Application Support/Viventium/private-user-data/memory-continuity-evals',
    );
  const privateDir = path.join(privateRoot, new Date().toISOString().replace(/[:.]/g, '-'));
  fs.mkdirSync(privateDir, { recursive: true });
  fs.writeFileSync(
    path.join(privateDir, 'provider-parity-matrix.json'),
    `${JSON.stringify(summary, null, 2)}\n`,
  );
  const publicReport = path.resolve(options.publicReport || DEFAULT_PUBLIC_REPORT);
  fs.mkdirSync(path.dirname(publicReport), { recursive: true });
  fs.writeFileSync(publicReport, renderPublicReport(summary));
  return {
    ...summary,
    privateOutputHash: hashValue(privateDir),
    publicReport: path.relative(REPO_ROOT, publicReport),
  };
}

async function main() {
  const summary = await runProviderParityMatrix();
  process.stdout.write(
    `${JSON.stringify({
      status: summary.status,
      providerRoute: summary.providerRoute,
      resultCount: summary.resultCount,
      completedCount: summary.completedCount,
      preferenceRestored: summary.preferenceRestored,
      cleanupVerified: summary.cleanupVerified,
      publicReport: summary.publicReport,
      privateOutputHash: summary.privateOutputHash,
    }, null, 2)}\n`,
  );
  process.exitCode = summary.status === 'passed' ? 0 : 1;
}

module.exports = {
  MATRIX_CASES,
  loadProviderParityEnv,
  parseSseBlock,
  readVoiceStream,
  runProviderParityMatrix,
  visibleText,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(JSON.stringify({ error: String(error?.message || error) }));
    process.exit(1);
  });
}
