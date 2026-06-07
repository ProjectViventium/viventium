#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const {
  DEFAULT_AGENT_ID,
  LIBRECHAT_ROOT,
  cleanupCallArtifacts,
  createQaAuth,
  fetchJson,
  loadCallSessionConversationId,
  loadEnv,
  requireLocalQaAuth,
  scanVoiceLog,
  shortHash,
} = require('./tts_artifact_browser_qa.cjs');
const {
  DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS,
  DEFAULT_VISIBLE_FORBIDDEN_ARTIFACT_KEYS,
  artifactCounts,
  sumForbiddenArtifacts,
} = require('./voice_artifact_contract.cjs');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const OUTPUT_DIR = path.join(REPO_ROOT, 'output', 'chrome', 'modern-playground-voice');

function outputPath(name) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  return path.join(OUTPUT_DIR, `${name}-${Date.now()}.json`);
}

function redactPath(filePath) {
  return filePath.replace(REPO_ROOT, '<repo>');
}

function dbNameFromMongoUri(uri) {
  return new URL(uri).pathname.replace(/^\//, '') || 'LibreChatViventium';
}

async function openDb(env) {
  const { MongoClient } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const client = new MongoClient(env.MONGO_URI);
  await client.connect();
  return { client, db: client.db(dbNameFromMongoUri(env.MONGO_URI)) };
}

async function create() {
  requireLocalQaAuth();
  const env = loadEnv();
  if (!env.MONGO_URI || !env.JWT_SECRET || !env.JWT_REFRESH_SECRET) {
    throw new Error('Missing MONGO_URI/JWT secrets');
  }
  const apiBase = process.env.VIVENTIUM_QA_API_BASE || 'http://localhost:3180';
  const { client, db } = await openDb(env);
  const auth = await createQaAuth({ env, db });
  const beforeOffset = fs.existsSync(require('./tts_artifact_browser_qa.cjs').LOG_PATH)
    ? fs.statSync(require('./tts_artifact_browser_qa.cjs').LOG_PATH).size
    : 0;
  try {
    const callResponse = await fetchJson(`${apiBase}/api/viventium/calls`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${auth.accessToken}`,
        'Content-Type': 'application/json',
        'User-Agent': 'ViventiumChromeVoiceArtifactQA/1.0',
      },
      body: JSON.stringify({
        conversationId: 'new',
        agentId: DEFAULT_AGENT_ID,
      }),
    });
    if (!callResponse.ok || !callResponse.body.callSessionId || !callResponse.body.playgroundUrl) {
      throw new Error(`call_session_http_${callResponse.status}`);
    }
    const setup = {
      createdAt: new Date().toISOString(),
      beforeOffset,
      callSessionId: callResponse.body.callSessionId,
      conversationId: callResponse.body.conversationId,
      playgroundUrl: callResponse.body.playgroundUrl.replace('autoConnect=1', 'autoConnect=0'),
      sessionId: auth.sessionId.toString(),
      userId: auth.userId,
      qaUserHash: shortHash(auth.user.email),
    };
    const filePath = outputPath('chrome-voice-artifact-setup');
    fs.writeFileSync(filePath, JSON.stringify(setup, null, 2) + '\n');
    return {
      ok: true,
      mode: 'create',
      setupPath: redactPath(filePath),
      callSessionHash: shortHash(setup.callSessionId),
      conversationHash: shortHash(setup.conversationId),
      qaUserHash: setup.qaUserHash,
    };
  } finally {
    await client.close();
  }
}

async function inspect(setupPath, { cleanup = false } = {}) {
  requireLocalQaAuth();
  const env = loadEnv();
  const { ObjectId } = require(path.join(LIBRECHAT_ROOT, 'node_modules', 'mongodb'));
  const setup = JSON.parse(fs.readFileSync(setupPath, 'utf8'));
  const { client, db } = await openDb(env);
  try {
    const resolvedConversationId = await loadCallSessionConversationId(db, setup.callSessionId);
    const assistantMessageFilter = {
      user: setup.userId,
      isCreatedByUser: false,
      $or: [
        { 'metadata.viventium.callSessionId': setup.callSessionId },
        ...(resolvedConversationId ? [{ conversationId: resolvedConversationId }] : []),
      ],
    };
    const persistedAssistantMessages = await db
      .collection('messages')
      .find(assistantMessageFilter, { projection: { messageId: 1, text: 1 } })
      .sort({ createdAt: 1 })
      .toArray();
    const persistedAssistantText = persistedAssistantMessages
      .map((message) => String(message.text || ''))
      .filter(Boolean)
      .join('\n');
    const persistedAssistantArtifacts = artifactCounts(persistedAssistantText);
    const logScan = scanVoiceLog(setup.beforeOffset);
    const ttsTextArtifactScanAvailable = Number(logScan.ttsEmitCount || 0) > 0;
    const forbiddenTtsArtifacts = ttsTextArtifactScanAvailable
      ? sumForbiddenArtifacts(logScan.ttsArtifacts || {}, DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS) +
        sumForbiddenArtifacts(logScan.ttsAggregateArtifacts || {}, DEFAULT_TTS_FORBIDDEN_ARTIFACT_KEYS)
      : 0;
    const forbiddenPersistedArtifacts = sumForbiddenArtifacts(
      persistedAssistantArtifacts,
      DEFAULT_VISIBLE_FORBIDDEN_ARTIFACT_KEYS,
    );
    const providerCompleted =
      logScan.ttsProviderMetricCount > 0 && logScan.ttsProviderCancelledCount === 0;
    const semanticModelHealthy =
      Number(logScan.rawDeltaCount || 0) + Number(logScan.streamDeltaCount || 0) > 0 ||
      (providerCompleted && persistedAssistantMessages.length > 0);
    const artifactOk =
      persistedAssistantMessages.length > 0 &&
      providerCompleted &&
      forbiddenTtsArtifacts === 0 &&
      forbiddenPersistedArtifacts === 0;
    let cleanupResult = null;
    if (cleanup) {
      cleanupResult = await cleanupCallArtifacts(db, {
        userId: setup.userId,
        callSessionId: setup.callSessionId,
        conversationId: setup.conversationId || resolvedConversationId,
      });
      await db.collection('sessions').deleteOne({ _id: new ObjectId(setup.sessionId) });
    }
    const result = {
      ok: artifactOk && semanticModelHealthy,
      mode: 'inspect',
      callSessionHash: shortHash(setup.callSessionId),
      conversationHash: shortHash(resolvedConversationId || setup.conversationId),
      persistedAssistantCount: persistedAssistantMessages.length,
      persistedAssistantTextHashes: persistedAssistantMessages.map((message) =>
        shortHash(`${message.messageId || ''}:${message.text || ''}`),
      ),
      persistedAssistantArtifacts,
      logScan,
      semanticModelHealthy,
      artifactOk,
      ttsTextArtifactEvidence: ttsTextArtifactScanAvailable
        ? 'debug_tts_chunks'
        : 'provider_metric_visible_persisted',
      forbiddenTtsArtifacts,
      forbiddenPersistedArtifacts,
      cleanup: cleanupResult,
    };
    const filePath = outputPath('chrome-voice-artifact-inspect');
    fs.writeFileSync(filePath, JSON.stringify(result, null, 2) + '\n');
    result.outputPath = redactPath(filePath);
    return result;
  } finally {
    await client.close();
  }
}

async function main() {
  const mode = process.argv[2] || 'create';
  let result;
  if (mode === 'create') {
    result = await create();
  } else if (mode === 'inspect') {
    const setupPath = process.argv[3];
    if (!setupPath) {
      throw new Error('inspect requires a setup file path');
    }
    result = await inspect(setupPath, { cleanup: process.argv.includes('--cleanup') });
  } else {
    throw new Error(`Unknown mode: ${mode}`);
  }
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = result.ok ? 0 : 1;
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message || String(error));
    process.exit(1);
  });
}
