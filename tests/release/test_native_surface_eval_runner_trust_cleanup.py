import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "qa"
    / "prompt-architecture"
    / "evals"
    / "run-native-surface-playwright-qa.cjs"
)


def _node(source: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", source, str(RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def test_cli_filters_select_one_exact_native_surface_case() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const args = runner.parseArgs([
  '--family=telegram_smart_delivery',
  '--case-id=telegram_copy_ready_email_skips_optional_audio',
  '--surface=telegram',
  '--max-cases=1',
]);
const bank = {
  families: [
    {
      id: 'telegram_smart_delivery',
      cases: [
        { id: 'telegram_copy_ready_email_skips_optional_audio', surface: 'telegram' },
        { id: 'telegram_conversation_keeps_smart_audio', surface: 'telegram' },
      ],
    },
    { id: 'other_family', cases: [{ id: 'web_case', surface: 'web' }] },
  ],
};
const selected = runner.selectPromptCases(bank, args);
assert.deepStrictEqual(selected.map((item) => item.id), [
  'telegram_copy_ready_email_skips_optional_audio',
]);
assert.strictEqual(args.family, 'telegram_smart_delivery');
assert.strictEqual(args.caseId, 'telegram_copy_ready_email_skips_optional_audio');
assert.strictEqual(args.surface, 'telegram');
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_visible_text_accepts_current_nested_sse_delta_shape() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const events = [
  { event: 'on_message_delta', data: { delta: { content: [{ type: 'text', text: '{"pass":' }] } } },
  { event: 'on_message_delta', data: { delta: { text: 'true}' } } },
  { final: true, responseMessage: { text: '   ' } },
];
assert.strictEqual(runner.extractVisibleText(events), '{"pass":true}');
assert.strictEqual(runner.extractFinalStreamError(events), null);
assert.strictEqual(
  runner.extractFinalStreamError([{
    final: true,
    responseMessage: {
      text: '',
      content: [{ type: 'error', error_class: 'provider_rate_limited' }],
    },
  }]),
  'provider_rate_limited',
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cli_filters_fail_closed_when_no_case_matches() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const args = runner.parseArgs(['--case-id=missing_case', '--surface=telegram']);
assert.throws(
  () => runner.selectPromptCases({ families: [] }, args),
  /native_surface_case_selection_empty/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_plural_case_filter_and_workbench_flags_are_exact_and_fail_closed() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const bank = {
  families: [{
    id: 'telegram_smart_delivery',
    promptRefs: ['main.conscious_agent', 'surface.telegram.text'],
    cases: [
      { id: 'telegram_first', surface: 'telegram' },
      { id: 'telegram_second', surface: 'telegram' },
      { id: 'web_third', surface: 'web' },
    ],
  }],
};
const args = runner.parseArgs([
  '--family=telegram_smart_delivery',
  '--case-ids=telegram_second,telegram_first',
  '--surface=telegram',
  '--prompt-id=surface.telegram.text',
  '--run-live',
]);
const selected = runner.selectPromptCases(bank, args);
assert.deepStrictEqual(selected.map((item) => item.id), ['telegram_second', 'telegram_first']);
assert.deepStrictEqual(args.caseIds, ['telegram_second', 'telegram_first']);
assert.strictEqual(args.promptId, 'surface.telegram.text');
assert.strictEqual(args.runLive, true);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-id=telegram_first', '--case-ids=telegram_first,telegram_second',
  ])),
  /native_surface_case_selection_conflict/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,telegram_first',
  ])),
  /native_surface_case_selection_duplicate/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,missing_case', '--surface=telegram',
  ])),
  /native_surface_case_selection_missing/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=',
  ])),
  /native_surface_case_selection_empty_requested_ids/,
);
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,,telegram_second',
  ])),
  /native_surface_case_selection_malformed_requested_ids/,
);
for (const emptySelector of ['--case-id=', '--family=', '--surface=', '--prompt-id=']) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs([emptySelector])),
    /native_surface_case_selection_empty_selector/,
  );
}
assert.throws(
  () => runner.selectPromptCases(bank, runner.parseArgs([
    '--case-ids=telegram_first,telegram_second', '--max-cases=1',
  ])),
  /native_surface_case_selection_truncated/,
);
for (const invalidLimit of ['--max-cases=', '--max-cases=0', '--max-cases=two']) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs([invalidLimit])),
    /native_surface_case_selection_invalid_max_cases/,
  );
}
for (const duplicateSelector of [
  ['--family=telegram_smart_delivery', '--family=telegram_smart_delivery'],
  ['--case-id=telegram_first', '--case-id=telegram_first'],
  ['--case-ids=telegram_first', '--case-ids=telegram_first'],
  ['--surface=telegram', '--surface=telegram'],
  ['--prompt-id=surface.telegram.text', '--prompt-id=surface.telegram.text'],
]) {
  assert.throws(
    () => runner.selectPromptCases(bank, runner.parseArgs(duplicateSelector)),
    /native_surface_case_selection_duplicate_selector/,
  );
}
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_selected_cases_retain_family_semantic_judge_requirement() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const cases = runner.flattenPromptCases({
  families: [
    {
      id: 'telegram_smart_delivery',
      semanticJudge: true,
      cases: [{ id: 'telegram_case', surface: 'telegram' }],
    },
    {
      id: 'case_override',
      semanticJudge: false,
      cases: [{ id: 'case_semantic', surface: 'voice', semanticJudge: true }],
    },
    {
      id: 'decision_quality',
      cases: [{
        id: 'decision_case',
        surface: 'scheduler',
        decisionQualityContract: { transportPassIsSemanticPass: false },
      }],
    },
  ],
});
assert.strictEqual(cases[0].semanticJudge, true);
assert.strictEqual(cases[0].familySemanticJudge, true);
assert.strictEqual(cases[1].semanticJudge, true);
assert.strictEqual(cases[1].familySemanticJudge, false);
assert.strictEqual(cases[2].semanticJudge, false);
assert.strictEqual(cases[2].familySemanticJudge, false);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[0]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[1]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge(cases[2]), true);
assert.strictEqual(runner.caseRequiresSemanticJudge({ semanticJudge: false }), false);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_native_runner_requires_explicit_live_authority() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
assert.doesNotThrow(() => runner.assertNativeLiveRunRequested(
  runner.parseArgs(['--run-live']),
));
assert.throws(
  () => runner.assertNativeLiveRunRequested(runner.parseArgs([])),
  /native_surface_live_run_not_authorized/,
);
assert.throws(
  () => runner.assertNativeLiveRunRequested(runner.parseArgs(['--run-live', '--no-live'])),
  /native_surface_live_run_not_authorized/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_completion_prompt_frame_surface_must_match_exactly() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const expectedRequestIdentityHash = runner.buildPromptFrameRequestIdentityHash({
  ownerId: 'synthetic-owner',
  surface: 'telegram',
  sourceEventId: 'server-valid-source-event',
});
const unrelatedRequestIdentityHash = 'fedcba9876543210';
const exactRoute = {
  requested_provider: 'openAI',
  requested_model: 'gpt-test',
  requested_effort: 'high',
  provider: 'openAI',
  model: 'gpt-test',
  effective_effort: 'high',
  fallback_used: false,
  fallback_reason: 'none',
};
const matching = runner.assertCompletionPromptFrameSurface([
  { event: 'viventium.prompt_frame', prompt_family: 'background_activation', surface: 'web' },
  {
    event: 'viventium.prompt_frame',
    prompt_family: 'main_run_create',
    surface: 'web',
    request_identity_hash: unrelatedRequestIdentityHash,
    agent_id_hash: 'fedcba9876543210',
    ...exactRoute,
    provider: 'other-provider',
    model: 'other-model',
  },
  {
    event: 'viventium.prompt_frame',
    prompt_family: 'main_run_create',
    surface: 'telegram',
    request_identity_hash: expectedRequestIdentityHash,
    agent_id_hash: '0123456789abcdef',
    ...exactRoute,
  },
], 'telegram', expectedRequestIdentityHash);
assert.strictEqual(matching.verified, true);
assert.strictEqual(matching.requestedSurface, 'telegram');
assert.strictEqual(matching.observedSurface, 'telegram');
assert.strictEqual(matching.completionFrameCount, 1);
assert.strictEqual(matching.requestIdentityHash, expectedRequestIdentityHash);
assert.strictEqual(matching.actualCompletionAgentIdHash, '0123456789abcdef');
assert.match(matching.completionProviderHashes[0], /^[0-9a-f]{16}$/);
assert.match(matching.completionModelHashes[0], /^[0-9a-f]{16}$/);
assert.deepStrictEqual(matching.requestedEfforts, ['high']);
assert.deepStrictEqual(matching.effectiveEfforts, ['high']);
assert.strictEqual(matching.fallbackUsed, false);
assert.deepStrictEqual(matching.fallbackReasons, ['none']);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'web',
      request_identity_hash: expectedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_surface_mismatch/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    { event: 'viventium.prompt_frame', prompt_family: 'background_activation', surface: 'telegram' },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_missing/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([{
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      request_identity_hash: unrelatedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
  }], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_request_identity_unrelated_only/,
);
assert.throws(
  () => runner.assertCompletionPromptFrameSurface([
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
    {
      event: 'viventium.prompt_frame', prompt_family: 'main_run_create', surface: 'telegram',
      request_identity_hash: expectedRequestIdentityHash,
      agent_id_hash: '0123456789abcdef', ...exactRoute,
    },
  ], 'telegram', expectedRequestIdentityHash),
  /completion_prompt_frame_request_identity_missing/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_request_identity_uses_exact_trusted_surface_and_telegram_source_event() -> None:
    script = r"""
const assert = require('assert');
const crypto = require('crypto');
const runner = require(process.argv[1]);
const ownerId = 'synthetic-owner-id';
const telegramUserId = 'qa_native_1234';
const telegramChatId = 'qa_native_1234';
const sourceSequence = 123456789;
const sourceOrderScope = runner.buildTelegramSourceOrderScope({
  ownerId,
  telegramUserId,
  telegramChatId,
  messageThreadId: '',
});
const sourceEventId = runner.buildTelegramSourceEventId({
  sourceOrderScope,
  sourceSequence,
});
const expectedSourceOrderScope = crypto.createHash('sha256').update([
  'viventium.telegram-source-order.v2',
  'telegram-interactive-v1',
  ownerId,
  telegramUserId,
  telegramChatId,
  '',
].join('\0')).digest('hex');
const expectedSourceEventId = crypto.createHash('sha256').update([
  'viventium.telegram-source-event.v1',
  expectedSourceOrderScope,
  String(sourceSequence),
].join('\0')).digest('hex');
const expectedRequestIdentityHash = crypto.createHash('sha256').update([
  'viventium.prompt-frame-request.v1',
  ownerId,
  'telegram',
  expectedSourceEventId,
].join('\0')).digest('hex').slice(0, 16);
assert.strictEqual(sourceOrderScope, expectedSourceOrderScope);
assert.strictEqual(sourceEventId, expectedSourceEventId);
assert.strictEqual(
  runner.buildPromptFrameRequestIdentityHash({
    ownerId,
    surface: 'telegram',
    sourceEventId,
  }),
  expectedRequestIdentityHash,
);
assert.strictEqual(runner.trustedCompletionSurface('wing'), 'voice');
assert.strictEqual(runner.trustedCompletionSurface('listen_only'), 'voice');
assert.strictEqual(runner.trustedCompletionSurface('scheduler'), 'workbench');
assert.strictEqual(runner.trustedCompletionSurface('telegram'), 'telegram');
assert.throws(
  () => runner.buildPromptFrameRequestIdentityHash({
    ownerId: '', surface: 'telegram', sourceEventId,
  }),
  /prompt_frame_request_identity_context_invalid/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_telegram_source_order_is_observed_and_verified_before_chat() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const sourceOrderScope = 'a'.repeat(64);
  const sourceEventId = 'b'.repeat(64);
  const sourceSequence = 123456789;
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/api/viventium/telegram/source-order')) {
      return {
        ok: true,
        status: 200,
        body: {
          observed: true,
          sourceOrderScope,
          sourceEventId,
          latestSourceSequence: sourceSequence,
          stale: false,
          durability: 'durable',
          replicaSafe: true,
        },
      };
    }
    return { ok: true, status: 200, body: { streamId: 'synthetic-stream' } };
  };
  const body = {
    text: 'Synthetic Telegram request',
    telegramUserId: 'qa_telegram_user',
    telegramChatId: 'qa_telegram_chat',
    telegramMessageThreadId: '',
    telegramMessageId: String(sourceSequence),
    sourceSequence,
    sourceOrderScope,
    sourceEventId,
  };
  const result = await runner.startTelegramSurfaceTurn({
    args: { apiBase: 'http://localhost:3180' },
    headers: { 'X-VIVENTIUM-TELEGRAM-SECRET': 'synthetic-secret' },
    body,
    fetcher,
  });
  assert.deepStrictEqual(calls.map((entry) => new URL(entry.url).pathname), [
    '/api/viventium/telegram/source-order',
    '/api/viventium/telegram/chat',
  ]);
  assert.strictEqual(result.sourceOrder.observed, true);
  assert.strictEqual(result.sourceOrder.sourceOrderScope, sourceOrderScope);
  assert.strictEqual(result.sourceOrder.sourceEventId, sourceEventId);
  assert.strictEqual(result.sourceOrder.latestSourceSequence, sourceSequence);
  assert.strictEqual(result.start.body.streamId, 'synthetic-stream');

  for (const badBody of [
    { observed: false, sourceOrderScope, sourceEventId, latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope: 'c'.repeat(64), sourceEventId, latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope, sourceEventId: 'd'.repeat(64), latestSourceSequence: sourceSequence },
    { observed: true, sourceOrderScope, sourceEventId, latestSourceSequence: sourceSequence + 1 },
  ]) {
    const badCalls = [];
    await assert.rejects(
      () => runner.startTelegramSurfaceTurn({
        args: { apiBase: 'http://localhost:3180' },
        headers: { 'X-VIVENTIUM-TELEGRAM-SECRET': 'synthetic-secret' },
        body,
        fetcher: async (url) => {
          badCalls.push(url);
          return { ok: true, status: 200, body: badBody };
        },
      }),
      /telegram_source_order_observation_unverified/,
    );
    assert.strictEqual(badCalls.length, 1);
    assert.match(badCalls[0], /\/api\/viventium\/telegram\/source-order$/);
  }
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_restores_mapping_and_removes_only_exact_qa_run_rows() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

function readPath(value, dotted) {
  return dotted.split('.').reduce((current, key) => current?.[key], value);
}
function equal(left, right) {
  return String(left) === String(right);
}
function matches(row, query) {
  return Object.entries(query || {}).every(([key, expected]) => {
    const actual = readPath(row, key);
    if (expected && typeof expected === 'object' && !Array.isArray(expected)) {
      if ('$in' in expected) return expected.$in.some((value) => equal(actual, value));
      if ('$gte' in expected) return new Date(actual).getTime() >= new Date(expected.$gte).getTime();
    }
    return equal(actual, expected);
  });
}
function database(seed) {
  const rows = structuredClone(seed);
  return {
    rows,
    collection(name) {
      const collection = rows[name];
      return {
        find(query) {
          let selected = collection.filter((row) => matches(row, query));
          return {
            project() { return this; },
            limit(count) { selected = selected.slice(0, count); return this; },
            async toArray() { return structuredClone(selected); },
          };
        },
        async findOne(query) {
          return structuredClone(collection.find((row) => matches(row, query)) || null);
        },
        async countDocuments(query) {
          return collection.filter((row) => matches(row, query)).length;
        },
        async deleteOne(query) {
          const index = collection.findIndex((row) => matches(row, query));
          if (index < 0) return { deletedCount: 0 };
          collection.splice(index, 1);
          return { deletedCount: 1 };
        },
        async replaceOne(query, replacement) {
          const index = collection.findIndex((row) => matches(row, query));
          if (index < 0) return { matchedCount: 0, modifiedCount: 0 };
          collection[index] = structuredClone(replacement);
          return { matchedCount: 1, modifiedCount: 1 };
        },
      };
    },
  };
}

(async () => {
  const runStartedAt = new Date('2026-08-25T20:00:00.000Z');
  const originalMapping = {
    _id: 'mapping-qa',
    telegramUserId: 'qa_native_1234',
    libreChatUserId: 'qa-user',
    telegramUsername: 'prior_synthetic',
  };
  const db = database({
    sessions: [
      { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'run-hash' },
      { _id: 'session-personal', user: 'personal-user', refreshTokenHash: 'personal-hash' },
    ],
    telegramusermappings: [{
      ...originalMapping,
      telegramUsername: 'qa_native_surface',
      viventiumNativeSurfaceQaRunId: 'native-run-1',
    }],
    messages: [
      {
        _id: 'message-run',
        user: 'qa-user',
        conversationId: 'conversation-run',
        createdAt: '2026-08-25T20:00:01.000Z',
        metadata: { viventium: { qaRun: true, qaRunId: 'native-run-1' } },
      },
      {
        _id: 'message-old-qa',
        user: 'qa-user',
        conversationId: 'conversation-old',
        createdAt: '2026-08-24T20:00:00.000Z',
        metadata: { viventium: { qaRun: false } },
      },
      {
        _id: 'message-personal',
        user: 'personal-user',
        conversationId: 'conversation-personal',
        createdAt: '2026-08-25T20:00:01.000Z',
        metadata: { viventium: { qaRun: true, qaRunId: 'native-run-1' } },
      },
    ],
    conversations: [
      { _id: 'conversation-row-run', user: 'qa-user', conversationId: 'conversation-run' },
      { _id: 'conversation-row-old', user: 'qa-user', conversationId: 'conversation-old' },
      { _id: 'conversation-row-personal', user: 'personal-user', conversationId: 'conversation-personal' },
    ],
  });

  const result = await runner.cleanupExactQaArtifacts({
    db,
    qaUser: {
      _id: 'qa-user', email: 'qa@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
    },
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    qaRunId: 'native-run-1',
    runStartedAt,
    sessionRecord: { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'run-hash' },
    mappingState: {
      telegramUserId: 'qa_native_1234',
      currentId: 'mapping-qa',
      originalDocument: originalMapping,
    },
    preexistingConversationIds: new Set(['conversation-old']),
    trackedConversationIds: new Set(['conversation-run']),
  });

  assert.deepStrictEqual(result, {
    cleaned: true,
    mappingAction: 'restored',
    removedSessionCount: 1,
    removedMessageCount: 1,
    removedConversationCount: 1,
  });
  assert.deepStrictEqual(db.rows.telegramusermappings, [originalMapping]);
  assert.deepStrictEqual(db.rows.sessions.map((row) => row._id), ['session-personal']);
  assert.deepStrictEqual(
    db.rows.messages.map((row) => row._id).sort(),
    ['message-old-qa', 'message-personal'],
  );
  assert.deepStrictEqual(
    db.rows.conversations.map((row) => row.conversationId).sort(),
    ['conversation-old', 'conversation-personal'],
  );
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_deletes_only_the_exact_new_mapping_and_failure_blocks_run() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const deletions = [];
  const db = {
    collection(name) {
      return {
        find() { return { project() { return this; }, limit() { return this; }, async toArray() { return []; } }; },
        async findOne(query) {
          if (name === 'telegramusermappings') {
            return {
              _id: 'new-mapping',
              telegramUserId: 'qa_native_5678',
              libreChatUserId: 'qa-user',
              viventiumNativeSurfaceQaRunId: 'native-run-2',
            };
          }
          return null;
        },
        async countDocuments() { return 0; },
        async deleteOne(query) {
          deletions.push({ name, query });
          return { deletedCount: name === 'sessions' ? 0 : 1 };
        },
        async replaceOne() { throw new Error('must_not_restore_new_mapping'); },
      };
    },
  };

  await assert.rejects(
    () => runner.cleanupExactQaArtifacts({
      db,
      qaUser: {
        _id: 'qa-user', email: 'qa@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
      },
      qaEmail: 'qa@example.com',
      ownerEmail: 'owner@example.com',
      qaRunId: 'native-run-2',
      runStartedAt: new Date('2026-08-25T20:00:00.000Z'),
      sessionRecord: { _id: 'session-run', user: 'qa-user', refreshTokenHash: 'run-hash' },
      mappingState: {
        telegramUserId: 'qa_native_5678',
        currentId: 'new-mapping',
        originalDocument: null,
      },
      preexistingConversationIds: new Set(),
      trackedConversationIds: new Set(),
    }),
    /native_surface_qa_cleanup_failed/,
  );
  assert.strictEqual(
    deletions.some((entry) => entry.name === 'telegramusermappings'),
    true,
  );

  const summary = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cleanup: { ok: false, error: 'native_surface_qa_cleanup_failed' },
    cases: [],
  });
  assert.strictEqual(summary.cleanupOk, false);
  assert.strictEqual(summary.status, 'completed_with_failures_or_gaps');
  const absentCleanup = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cases: [],
  });
  assert.strictEqual(absentCleanup.cleanupOk, false);
  const emptySelection = runner.summarizeRun({
    generatedAt: '2026-08-25T20:00:00.000Z',
    args: { semanticRequired: false },
    browserProbe: { ok: true },
    cleanup: { ok: true },
    selection: { selectedCaseIds: [], selectedCaseCount: 0 },
    cases: [],
  });
  assert.strictEqual(emptySelection.selectedCoverageOk, false);
  assert.strictEqual(emptySelection.status, 'completed_with_failures_or_gaps');
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_cleanup_refuses_unproven_conversation_and_cross_owner_session() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);

(async () => {
  const deletions = [];
  const db = {
    collection(name) {
      return {
        find(query) {
          const values = name === 'conversations'
            ? [{ _id: 'empty-row', user: 'qa-user', conversationId: 'unproven-empty' }]
            : [];
          return {
            project() { return this; },
            limit() { return this; },
            async toArray() { return values; },
          };
        },
        async findOne() { return null; },
        async countDocuments() { return 0; },
        async deleteOne(query) {
          deletions.push({ name, query });
          return { deletedCount: 1 };
        },
      };
    },
  };

  await assert.rejects(
    () => runner.cleanupExactQaArtifacts({
      db,
      qaUser: {
        _id: 'qa-user', email: 'qa@example.com', role: 'USER',
        viventiumApprovalStatus: 'approved',
      },
      qaEmail: 'qa@example.com',
      ownerEmail: 'owner@example.com',
      qaRunId: 'native-run-3',
      runStartedAt: new Date('2026-08-25T20:00:00.000Z'),
      sessionRecord: {
        _id: 'personal-session', user: 'personal-user', refreshTokenHash: 'personal-hash',
      },
      mappingState: null,
      preexistingConversationIds: new Set(),
      trackedConversationIds: new Set(['unproven-empty']),
    }),
    /native_surface_qa_cleanup_failed/,
  );
  assert.deepStrictEqual(deletions, []);
})().catch((error) => { console.error(error); process.exit(1); });
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_personal_or_admin_account_is_refused_before_any_cleanup() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'owner@example.com',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'owner', email: 'owner@example.com', role: 'USER', viventiumApprovalStatus: 'approved',
    },
  }),
  /personal_owner_account_refused/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'qa', email: 'qa@example.com', role: 'ADMIN', viventiumApprovalStatus: 'approved',
    },
  }),
  /admin_qa_account_refused/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@real-company.test',
    ownerEmail: 'owner@example.com',
    user: {
      _id: 'qa', email: 'qa@real-company.test', role: 'USER',
      viventiumApprovalStatus: 'approved',
    },
  }),
  /synthetic_qa_account_required/,
);
assert.throws(
  () => runner.assertSelectedSyntheticQaUser({
    qaEmail: 'qa@example.com',
    ownerEmail: 'owner@example.com',
    user: { _id: 'qa', email: 'qa@example.com', role: 'USER' },
  }),
  /approved_synthetic_qa_account_required/,
);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_canonical_artifact_summary_has_strict_workbench_coverage_fields() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const privateRun = {
  generatedAt: '2026-08-25T20:00:00.000Z',
  args: { semanticRequired: true },
  browserProbe: { ok: true, mcpStatus: { public: {} } },
  cleanup: { ok: true, mappingAction: 'restored' },
  selection: {
    selectedCaseIds: ['telegram_case'],
    selectedCaseCount: 1,
  },
  cases: [{
    caseId: 'telegram_case',
    status: 'completed',
    surface: 'telegram',
    route: 'telegram_gateway',
    responseHash: 'response-hash',
    requestedSurface: 'telegram',
    requestedCompletionSurface: 'telegram',
    observedCompletionSurface: 'telegram',
    completionExpected: true,
    completionSurfaceVerified: true,
    requestIdentityHash: '3333333333333333',
    actualCompletionAgentIdHash: '0123456789abcdef',
    completionProviderHashes: ['1111111111111111'],
    completionModelHashes: ['2222222222222222'],
    semanticPass: true,
    judge: { verdict: 'pass' },
    frameSummary: { surfaces: ['telegram'] },
    private: {
      completionFrames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
      }],
    },
  }],
};
const summary = runner.summarizeRun(privateRun);
assert.strictEqual(summary.selectedCoverageOk, true);
assert.strictEqual(summary.selectedCaseCount, 1);
assert.strictEqual(summary.resultCount, 1);
assert.strictEqual(summary.completedCount, 1);
assert.strictEqual(summary.failedCount, 0);
assert.strictEqual(summary.semanticJudgedCount, 1);
assert.strictEqual(summary.semanticPassedCount, 1);
assert.strictEqual(summary.semanticFailedCount, 0);
assert.strictEqual(summary.cleanupOk, true);
assert.strictEqual(summary.status, 'completed_with_semantic_native_surface_evidence');
const missingRequestIdentity = structuredClone(privateRun);
delete missingRequestIdentity.cases[0].requestIdentityHash;
assert.strictEqual(runner.summarizeRun(missingRequestIdentity).completionEvidenceOk, false);
const substitutedRequestIdentity = structuredClone(privateRun);
substitutedRequestIdentity.cases[0].private.completionFrames[0].request_identity_hash =
  '4444444444444444';
assert.strictEqual(runner.summarizeRun(substitutedRequestIdentity).completionEvidenceOk, false);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_canonical_artifact_keeps_frames_but_never_raw_runtime_ids() -> None:
    script = r"""
const assert = require('assert');
const runner = require(process.argv[1]);
const privateRun = {
  selection: { selectedCaseIds: ['safe_case'], selectedCaseCount: 1 },
      cases: [{
        caseId: 'safe_case',
        requestIdentityHash: '3333333333333333',
        judge: {
      verdict: 'pass',
      cleanupFinalMetas: [{
        conversationId: 'raw-judge-conversation', responseMessageId: 'raw-judge-message',
      }],
    },
    private: {
      result: {
        text: 'safe synthetic answer',
        finalMeta: {
          conversationId: 'raw-main-conversation',
          responseMessageId: 'raw-main-message',
          requestMessageId: 'raw-request-message',
        },
        privateEvents: [{
          messageId: 'raw-event-message',
          metadata: { viventium: { interactionContext: {
            source_event_id: 'raw-source-event', ownerId: 'raw-owner-id',
          } } },
        }],
      },
      frames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
        debug_redacted_layers: { prompt: 'must-not-enter-artifact' },
      }, {
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '4444444444444444',
        agent_id_hash: 'fedcba9876543210',
        provider: 'unrelated-private-provider',
        model: 'unrelated-private-model',
      }],
      completionFrames: [{
        event: 'viventium.prompt_frame',
        prompt_family: 'main_run_create',
        surface: 'telegram',
        request_identity_hash: '3333333333333333',
        agent_id_hash: '0123456789abcdef',
        provider: 'openAI',
        model: 'gpt-test',
      }],
    },
  }],
};
const artifact = runner.buildCanonicalArtifact(privateRun);
const encoded = JSON.stringify(artifact);
for (const raw of [
  'raw-judge-conversation', 'raw-judge-message', 'raw-main-conversation',
  'raw-main-message', 'raw-request-message', 'raw-event-message', 'raw-source-event',
  'raw-owner-id', 'must-not-enter-artifact',
  'unrelated-private-provider', 'unrelated-private-model',
]) {
  assert.strictEqual(encoded.includes(raw), false, raw);
}
assert.strictEqual(
  artifact.cases[0].private.result.finalMetaHashes.conversationIdHash.length,
  16,
);
assert.strictEqual(artifact.cases[0].private.result.privateEventHashes.length, 1);
assert.strictEqual(artifact.cases[0].private.frames[0].provider, 'openAI');
assert.strictEqual(artifact.cases[0].private.frames[0].model, 'gpt-test');
assert.strictEqual(artifact.cases[0].private.frames[0].request_identity_hash, '3333333333333333');
assert.strictEqual(artifact.cases[0].private.frames.length, 1);
"""
    completed = _node(script)
    assert completed.returncode == 0, completed.stderr


def test_main_finally_requires_cleanup_and_cleanup_failure_exits_nonzero() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "native-surface-playwright-qa.json" in source
    assert "finally {" in source
    assert "await qaAuth.cleanup()" in source
    assert "cleanupFailure" in source
    assert "!summary.cleanupOk" in source
    assert "privateRun.summary = summary" in source
    for field in (
        "selectedCaseCount",
        "resultCount",
        "completedCount",
        "failedCount",
        "semanticJudgedCount",
        "semanticPassedCount",
        "semanticFailedCount",
    ):
        assert field in source
    assert "await qaAuth.close()" not in source
