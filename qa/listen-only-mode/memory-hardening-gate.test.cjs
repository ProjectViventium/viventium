const assert = require('node:assert/strict');
const {
  validateProposal,
} = require('../../viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');

const now = new Date('2026-05-05T12:00:00.000Z');
const memoryConfig = {
  validKeys: ['core', 'context', 'world'],
  keyLimits: {
    core: 1000,
    context: 1000,
    world: 1000,
  },
  tokenLimit: 10000,
};

function proposalFor({ key = 'core', evidence, value = 'Synthetic durable memory candidate from listen-only QA.' }) {
  return {
    operations: [
      {
        action: 'set',
        key,
        value,
        evidence,
      },
    ],
  };
}

function validateWithListenOnlySources({ key = 'core', sourceIds, includeUserChat = false }) {
  const messageIds = sourceIds.map((_sourceId, index) => `lo-${index + 1}`);
  const evidence = messageIds.map((messageId) => ({
    source: 'conversation',
    messageId,
    createdAt: now.toISOString(),
  }));
  if (includeUserChat) {
    evidence.push({
      source: 'conversation',
      messageId: 'user-chat-1',
      createdAt: now.toISOString(),
    });
  }
  return validateProposal({
    proposal: proposalFor({
      key,
      evidence,
    }),
    memories: [],
    memoryConfig,
    options: {
      now,
      maxChangesPerUser: 5,
      allowDelete: false,
      validConversationMessageIds: new Set(includeUserChat ? [...messageIds, 'user-chat-1'] : messageIds),
      validUserConversationMessageIds: includeUserChat ? new Set(['user-chat-1']) : new Set(),
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
  'identity_memory_requires_conversation_corroboration',
);

const distinctCalls = validateWithListenOnlySources({
  sourceIds: ['call:listen-only-session-1', 'call:listen-only-session-2'],
});
assert.equal(distinctCalls.accepted.length, 0);
assert.equal(
  distinctCalls.rejected[0].reason,
  'identity_memory_requires_conversation_corroboration',
);

const stableWorld = validateWithListenOnlySources({
  key: 'world',
  sourceIds: ['call:listen-only-session-1', 'call:listen-only-session-2'],
});
assert.equal(stableWorld.accepted.length, 0);
assert.equal(
  stableWorld.rejected[0].reason,
  'stable_memory_requires_user_conversation_corroboration',
);

const userCorroborated = validateWithListenOnlySources({
  key: 'world',
  sourceIds: ['call:listen-only-session-1'],
  includeUserChat: true,
});
assert.equal(userCorroborated.accepted.length, 1);
assert.equal(userCorroborated.rejected.length, 0);

const transcriptScoped = validateWithListenOnlySources({
  key: 'context',
  sourceIds: ['call:listen-only-session-1'],
});
assert.equal(transcriptScoped.accepted.length, 1);

console.log('memory-hardening listen-only gate tests passed');
