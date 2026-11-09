'use strict';

const path = require('path');
const { createRequire } = require('module');
const { isDeepStrictEqual } = require('util');

function withNativeAccountEnv(env, startRequest) {
  const keys = ['GLASSHIVE_PROVIDER_BASE_URL', 'WPR_API_TOKEN',
    'VIVENTIUM_GLASSHIVE_SERVICE_ASSERTION_SECRET', 'VIVENTIUM_TENANT_ID'];
  const previous = keys.map((key) => [key, process.env[key]]);
  try {
    for (const key of keys) if (env[key] != null) process.env[key] = env[key];
    return startRequest();
  } finally {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
}

/** QA reads the production presentation owner. It never publishes, settles or starts work. */
async function readNativeBackgroundObservation({
  db, result, conversationId, ownerId, env = {}, messages, libreChatRoot, request,
}) {
  if (!ownerId) return { results: [], messages: [] };
  const tenantId = env.VIVENTIUM_TENANT_ID || 'local';
  const selectedIds = new Set([...(result.cleanupFinalMetas || []), result.finalMeta]
    .filter((meta) => meta?.conversationId === conversationId)
    .flatMap((meta) => [meta.requestMessageId, meta.responseMessageId]).filter(Boolean));
  const parents = messages.filter((message) => message.user === ownerId && selectedIds.has(message.messageId));
  if (!parents.length) return { results: [], messages: [] };
  const bindings = await db.collection('viventium_glasshive_callback_bindings').find({
    kind: 'native_coordinator_binding', active: true, tenantId, ownerId, conversationId,
  }).toArray();
  if (!bindings.length) return { results: [], messages: [] };
  const sources = await db.collection('viventium_glasshive_callback_bindings').find({
    kind: 'native_coordinator_source', bindingRef: { $in: bindings.map((binding) => binding._id) },
    $or: [{ 'requestBody.messageId': { $in: parents.map((parent) => parent.messageId) } },
      { 'requestBody.parentMessageId': { $in: parents.map((parent) => parent.messageId) } }],
  }).toArray();
  if (!sources.length) return { results: [], messages: [] };
  const localRequire = createRequire(path.join(libreChatRoot, 'api/server/services/viventium/nativeCoordinatorPresentation.js'));
  const { createNativeCoordinatorPresentationService } = localRequire('./nativeCoordinatorPresentation');
  const { requiredSurfacesFor, requestAccountApi } = localRequire('@librechat/api');
  // The account client owns origin validation, signing and response bounds. Runtime env is loaded
  // by this QA process, not by the server module. Restore the synchronous request setup immediately.
  const nativeRequest = request || ((input) =>
    withNativeAccountEnv(env, () => requestAccountApi({ ...input, method: 'GET' })));
  const results = [], delivered = [];
  for (const parentMessageId of new Set(sources.map((source) =>
    source.requestBody.messageId || source.requestBody.parentMessageId))) {
    const rows = await db.collection('viventiumcortexinsightdeliveries').find({
      userId: ownerId, conversationId, parentMessageId,
    }).toArray();
    const groups = new Map();
    for (const row of rows) {
      const key = row.publicationId || '';
      groups.set(key, [...(groups.get(key) || []), row]);
    }
    if (!groups.size) { results.push({ state: 'pending', hasFollowUp: false }); continue; }
    for (const [publicationId, group] of groups) {
      const service = createNativeCoordinatorPresentationService({
        tenantId: () => tenantId,
        readRows: async () => group,
        readMessage: async ({ messageId }) => messages.find((message) =>
          message.user === ownerId && message.messageId === messageId) || null,
        findMessages: async ({ deliveryIds }) => messages.filter((message) =>
          message.user === ownerId &&
          message.metadata?.viventium?.cortexPresentationParentMessageId === parentMessageId &&
          message.metadata?.viventium?.cortexInsightDeliveryIds?.length === deliveryIds.length &&
          deliveryIds.every((id) => message.metadata.viventium.cortexInsightDeliveryIds.includes(id))),
        readSources: async (_parent, retained) => sources.filter((source) =>
          (source.requestBody.messageId || source.requestBody.parentMessageId) === parentMessageId &&
          (!retained || (source.bindingRef === retained.bindingRef && source.turnId === retained.sourceTurnId)))
          .map((source) => ({ source, binding: bindings.find((binding) => binding._id === source.bindingRef) })),
        readSnapshot: (binding) => nativeRequest({ ownerId,
          path: `/v1/coordinator/conversations/${encodeURIComponent(binding.nativeConversationId)}?include_history=false`,
          maxResponseBytes: null }),
        readResult: (binding, goal) => nativeRequest({ ownerId,
          path: `/v1/coordinator/conversations/${encodeURIComponent(binding.nativeConversationId)}/goals/${encodeURIComponent(goal.goal_id)}/result?run_id=${encodeURIComponent(goal.run_id)}&offset=0&max_chars=1` }),
        readTurnResult: (binding, turn) => nativeRequest({ ownerId,
          path: `/v1/coordinator/conversations/${encodeURIComponent(binding.nativeConversationId)}/turns/${encodeURIComponent(turn.turn_id)}/result?request_id=${encodeURIComponent(turn.request_id)}&run_id=${encodeURIComponent(turn.run_id)}&offset=0&max_chars=1` }),
        async readPublications(binding) {
          const publications = [], seen = new Set(); let cursor = null;
          do {
            const page = await nativeRequest({ ownerId,
              path: `/v1/coordinator/conversations/${encodeURIComponent(binding.nativeConversationId)}/publications${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}` });
            if (page?.conversation_id !== binding.nativeConversationId || !Array.isArray(page.publications) ||
              (page.next_cursor !== null && typeof page.next_cursor !== 'string')) throw Error('native_qa_publications_invalid');
            publications.push(...page.publications); cursor = page.next_cursor;
            if (cursor && seen.has(cursor)) throw Error('native_qa_publication_cursor_repeated');
            if (cursor) seen.add(cursor);
          } while (cursor);
          return publications;
        },
      });
      try {
        const owned = await service.resolve({ ownerId, conversationId, parentMessageId, publicationId });
        let state = 'pending', message = null;
        if (owned?.eligible === true) {
          const saved = messages.find((candidate) => candidate.user === ownerId &&
            candidate.messageId === owned.message?.messageId);
          const required = requiredSurfacesFor(group[0].surface);
          const settled = group.every((row) => row.status === 'sent' && row.sentAt &&
            row.persistenceStatus === 'persisted' && row.persistedMessageId === saved?.messageId &&
            row.requiredSurfaces?.length === required.length &&
            required.every((surface) => row.requiredSurfaces.includes(surface) && row.presentedSurfaces?.includes(surface)) &&
            row.presentationReceiptHashes?.length > 0);
          const sameDeliveryMessages = messages.filter((candidate) => candidate.user === ownerId &&
            candidate.metadata?.viventium?.cortexPresentationParentMessageId === parentMessageId &&
            group.every((row) => candidate.metadata?.viventium?.cortexInsightDeliveryIds?.includes(row.deliveryId)));
          if (sameDeliveryMessages.length === 1 &&
            saved?.metadata?.viventium?.mainGenerationPresentation?.version === 2 && settled &&
            isDeepStrictEqual(saved.metadata.viventium.mainGenerationPresentation,
              owned.message.metadata.viventium.mainGenerationPresentation)) {
            const receipts = group[0].surface === 'telegram'
              ? await db.collection('viventiumglasshivecallbackdeliveries').find({ userId: ownerId,
                conversationId, callbackMessageId: saved.messageId, status: 'sent', surface: 'telegram' }).toArray() : [];
            if (group[0].surface !== 'telegram' || receipts.some((receipt) => receipt.sentAt &&
              receipt.originRef === owned.binding._id && (receipt.telegramSentMessageIds?.length || receipt.telegramMessageId) &&
              receipt.text?.trim() === saved.text?.trim() &&
              isDeepStrictEqual(receipt.mainGenerationPresentation, saved.metadata.viventium.mainGenerationPresentation))) {
              state = 'completed'; message = saved;
            }
          }
          const decision = parents.find((parent) => parent.messageId === parentMessageId)
            ?.metadata?.viventium?.cortexFollowUpDecision;
          const exactSilence = decision?.deliveryStatus === 'dropped' &&
            decision.dropReason === 'semantic_suppression' && !decision.persistedMessageId &&
            ['suppressed', 'dropped'].includes(decision.result) &&
            ((decision.selectedStrategy === 'no_response_suppressed' && decision.suppressionReason === 'no_response_tag') ||
              (decision.nativeSilentDecision === true && decision.selectedStrategy === 'native_silent_suppressed' &&
                decision.suppressionReason === 'native_authored_silence'));
          const savedCandidates = messages.filter((candidate) => candidate.user === ownerId &&
            candidate.metadata?.viventium?.cortexPresentationParentMessageId === parentMessageId);
          if (exactSilence && !savedCandidates.length && !owned.message &&
            group.every((row) => row.status === 'dropped' && row.dropReason === 'semantic_suppression' &&
              row.persistenceStatus === 'pending' && !row.persistedMessageId)) state = 'silent';
        }
        results.push({ state, hasFollowUp: Boolean(message) });
        if (message) delivered.push(message);
      } catch {
        // Unavailable, changed or ambiguous authority is never evidence of success or silence.
        results.push({ state: 'unavailable', hasFollowUp: false });
      }
    }
  }
  return { results, messages: [...new Map(delivered.map((message) => [message.messageId, message])).values()] };
}

module.exports = { readNativeBackgroundObservation, withNativeAccountEnv };
