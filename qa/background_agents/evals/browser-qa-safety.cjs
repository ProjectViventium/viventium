/* eslint-disable no-console */

function normalizedEmail(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function assertNonOwnerQaSelection({
  ownerEmail,
  requestedEmail,
  selectedUser,
}) {
  const owner = normalizedEmail(ownerEmail);
  const requested = normalizedEmail(requestedEmail);
  const selected = normalizedEmail(selectedUser?.email);
  if (!owner) {
    throw new Error("missing_owner_email_guard");
  }
  if (requested && requested === owner) {
    throw new Error("qa_email_matches_owner_refused");
  }
  if (selected && selected === owner) {
    throw new Error("selected_owner_account_refused");
  }
  return true;
}

function withQaRequestIsolation(body, qaRunId) {
  const normalizedRunId = String(qaRunId || "")
    .trim()
    .slice(0, 128);
  return {
    ...(body && typeof body === "object" ? body : {}),
    viventiumQaRun: true,
    ...(normalizedRunId ? { viventiumQaRunId: normalizedRunId } : {}),
    viventiumEvalIsolation: {
      savedMemory: true,
      conversationRecall: true,
      feelings: true,
    },
  };
}

async function installQaRequestIsolation(page, { qaRunId } = {}) {
  await page.route("**/api/agents/chat**", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      await route.continue();
      return;
    }
    const isolatedBody = withQaRequestIsolation(
      request.postDataJSON(),
      qaRunId,
    );
    const headers = {
      ...request.headers(),
      "content-type": "application/json",
    };
    delete headers["content-length"];
    await route.continue({ headers, postData: JSON.stringify(isolatedBody) });
  });
}

async function cleanupQaRunArtifacts({
  db,
  userId,
  startedAt,
  trackedConversationIds = [],
  qaRunId,
  meiliClient,
}) {
  if (
    !db ||
    !userId ||
    !(startedAt instanceof Date) ||
    Number.isNaN(startedAt.getTime())
  ) {
    throw new Error("qa_cleanup_missing_required_context");
  }

  const messageQuery = {
    user: String(userId),
    createdAt: { $gte: startedAt },
    ...(qaRunId ? { "metadata.viventium.qaRunId": String(qaRunId) } : {}),
  };
  const recentMessages = await db
    .collection("messages")
    .find(messageQuery)
    .toArray();
  const conversationIds = [
    ...new Set(
      [
        ...trackedConversationIds,
        ...recentMessages.map((message) => message?.conversationId),
      ].filter(Boolean),
    ),
  ];
  if (!conversationIds.length) {
    return { conversationIds: [], messagesDeleted: 0, conversationsDeleted: 0 };
  }

  const messageDelete = await db.collection("messages").deleteMany({
    user: String(userId),
    conversationId: { $in: conversationIds },
  });
  const conversationDelete = await db.collection("conversations").deleteMany({
    user: String(userId),
    conversationId: { $in: conversationIds },
  });
  let meiliMessagesDeleted = 0;
  let meiliConversationsDeleted = 0;
  if (meiliClient) {
    const encodeId = (value) => {
      let encoded = "";
      for (const character of String(value)) {
        encoded += character.charCodeAt(0).toString(16).padStart(4, "0");
      }
      return `m_${encoded}`;
    };
    const deleteFromIndex = async (name, sourceIds) => {
      if (!sourceIds.length) return 0;
      const index = meiliClient.index(name);
      const task = await index.deleteDocuments(sourceIds.map(encodeId));
      const completed = await index.waitForTask(task.taskUid, {
        timeOutMs: 60000,
        intervalMs: 50,
      });
      if (completed.status !== "succeeded") {
        throw new Error(`qa_cleanup_meili_${name}_failed`);
      }
      return sourceIds.length;
    };
    meiliMessagesDeleted = await deleteFromIndex(
      "messages",
      recentMessages.map((message) => message?.messageId).filter(Boolean),
    );
    meiliConversationsDeleted = await deleteFromIndex(
      "convos",
      conversationIds,
    );
  }
  return {
    conversationIds,
    messagesDeleted: messageDelete.deletedCount || 0,
    conversationsDeleted: conversationDelete.deletedCount || 0,
    meiliMessagesDeleted,
    meiliConversationsDeleted,
  };
}

module.exports = {
  assertNonOwnerQaSelection,
  cleanupQaRunArtifacts,
  installQaRequestIsolation,
  withQaRequestIsolation,
};
