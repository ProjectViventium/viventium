const assert = require('node:assert/strict');
const {
  validateProposal,
} = require('../../viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');

const now = new Date('2026-05-05T12:00:00.000Z');
const memoryConfig = {
  validKeys: ['core', 'context'],
  keyLimits: {
    core: 1000,
    context: 1000,
  },
  tokenLimit: 10000,
};

function proposalFor({ key = 'core', evidence }) {
  return {
    operations: [
      {
        action: 'set',
        key,
        value: 'Synthetic durable memory candidate from listen-only QA.',
        evidence,
      },
    ],
  };
}

function validateWithListenOnlySources({ key = 'core', sourceIds }) {
  const messageIds = sourceIds.map((_sourceId, index) => `lo-${index + 1}`);
  return validateProposal({
    proposal: proposalFor({
      key,
      evidence: messageIds.map((messageId) => ({
        source: 'conversation',
        messageId,
        createdAt: now.toISOString(),
      })),
    }),
    memories: [],
    memoryConfig,
    options: {
      now,
      maxChangesPerUser: 5,
      allowDelete: false,
      validConversationMessageIds: new Set(messageIds),
      listenOnlyConversationMessageIds: new Set(messageIds),
      listenOnlyConversationSourceIds: new Map(
        messageIds.map((messageId, index) => [messageId, sourceIds[index]]),
      ),
      transcriptStableEvidenceMaxAgeDays: 90,
    },
  });
}

const sameCall = validateWithListenOnlySources({
  sourceIds: ['call:listen-only-session-1', 'call:listen-only-session-1'],
});
assert.equal(sameCall.accepted.length, 0);
assert.equal(
  sameCall.rejected[0].reason,
  'stable_memory_requires_corroborated_listen_only_evidence',
);

const distinctCalls = validateWithListenOnlySources({
  sourceIds: ['call:listen-only-session-1', 'call:listen-only-session-2'],
});
assert.equal(distinctCalls.accepted.length, 1);
assert.equal(distinctCalls.rejected.length, 0);

const transcriptScoped = validateWithListenOnlySources({
  key: 'context',
  sourceIds: ['call:listen-only-session-1'],
});
assert.equal(transcriptScoped.accepted.length, 1);

console.log('memory-hardening listen-only gate tests passed');
