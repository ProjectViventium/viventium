from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_latest_user_browser_harness_classifies_visible_environment_blocks() -> None:
    output = run_node(
        r"""
const assert = require('assert');
const qa = require('./qa/background_agents/evals/run-latest-user-activation-browser-qa.cjs');

function pageWithText(text) {
  return {
    locator() {
      return {
        async innerText() {
          return text;
        },
      };
    },
  };
}

(async () => {
  assert.strictEqual(
    await qa.readVisibleEnvironmentBlock(pageWithText('Connected account needs reconnect before continuing')),
    'model_connected_account_reconnect_required',
  );
  assert.strictEqual(
    await qa.readVisibleEnvironmentBlock(pageWithText('Unable to login with the information provided. Please check your credentials and try again.')),
    'login_rejected_by_runtime',
  );
  assert.strictEqual(
    await qa.readVisibleEnvironmentBlock(pageWithText('Something went wrong. Here is the specific error message we encountered: An error occurred while processing the request: terminated')),
    'visible_generation_error:Something went wrong. Here is the specific error message we encountered: An error occurred while processing the request: terminated',
  );

  let thrown = null;
  try {
    qa.throwEnvironmentBlock('login_rejected_by_runtime');
  } catch (error) {
    thrown = error;
  }
  assert(thrown);
  assert.strictEqual(thrown.qaBlocked, true);
  assert.strictEqual(thrown.message, 'environment_blocked:login_rejected_by_runtime');
  assert.strictEqual(qa.exitCodeForResult({ pass: true }), 0);
  assert.strictEqual(qa.exitCodeForResult({ pass: false, environmentBlocked: true }), 2);
  assert.strictEqual(qa.exitCodeForResult({ pass: false, environmentBlocked: false }), 1);
  console.log('OK');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    )

    assert output == "OK"


def test_interruption_restart_harness_classifies_active_and_recovered_cortex_state() -> None:
    harness = ROOT / "qa" / "background_agents" / "evals" / "run-interruption-restart-browser-qa.cjs"
    source = harness.read_text(encoding="utf-8")

    assert "VIVENTIUM_QA_ALLOW_RUNTIME_RESTART" in source
    assert "VIVENTIUM_QA_ALLOW_LOCAL_JWT" in source
    assert "waitForPersistedActiveCortex" in source
    assert "waitForRecoveredTerminalCortex" in source
    assert "recovery_reason" in source
    assert ".reload(" in source
    assert "waitUntil:" in source
    assert "domcontentloaded" in source
    assert "path.join(REPO_ROOT" in source
    assert "bin" in source
    assert "viventium" in source
    assert "restart" in source
    assert "startCommandError" in source
    assert "Runtime health is authoritative after the detached launcher handoff" in source
    assert "restarted.diagnostics.consoleErrors.length = 0" in source
    assert "restarted.diagnostics.failedRequests.length = 0" in source
    assert "restarted.diagnostics.httpErrors.length = 0" in source
    assert "stdio:" in source
    assert "ignore" in source
    assert "handoffAfterMs" in source

    output = run_node(
        r"""
const assert = require('assert');
const qa = require('./qa/background_agents/evals/run-interruption-restart-browser-qa.cjs');

const active = qa.summarizeCortexMessage({
  unfinished: true,
  content: [
    {
      type: 'cortex_brewing',
      cortex_name: 'Red Team',
      status: 'running',
    },
  ],
});
assert.deepStrictEqual(active.activeNames, ['Red Team']);
assert.deepStrictEqual(active.recoveredTerminalNames, []);
assert.strictEqual(active.unfinished, true);

const recovered = qa.summarizeCortexMessage({
  unfinished: false,
  content: [
    {
      type: 'cortex_brewing',
      cortex_name: 'Red Team',
      status: 'error',
      recovery_reason: 'stale_cortex_startup_recovery',
    },
  ],
});
assert.deepStrictEqual(recovered.activeNames, []);
assert.deepStrictEqual(recovered.recoveredTerminalNames, ['Red Team']);
assert.strictEqual(recovered.unfinished, false);

assert.strictEqual(qa.isExpectedNavigationAbort('net::ERR_ABORTED'), true);
assert.strictEqual(qa.isExpectedNavigationAbort('NS_BINDING_ABORTED'), true);
assert.strictEqual(qa.isExpectedNavigationAbort('net::ERR_FAILED'), false);
assert.strictEqual(
  qa.isExpectedQaAuthBootstrapDiagnostic('Failed to load resource: the server responded with a status of 401 (Unauthorized)'),
  true,
);
assert.strictEqual(
  qa.isExpectedQaAuthBootstrapDiagnostic('AxiosError: Request failed with status code 401'),
  true,
);
assert.strictEqual(qa.isExpectedQaAuthBootstrapDiagnostic('AxiosError: status code 500'), false);

assert.strictEqual(
  qa.sanitizePublicError('user@example.com Bearer abcdefghijklmnop /Users/example/private https://private.example/path'),
  '<email> Bearer <redacted> <path> <url>',
);
assert.strictEqual(qa.exitCodeForResult({ pass: true }), 0);
assert.strictEqual(qa.exitCodeForResult({ pass: false, environmentBlocked: true }), 2);
assert.strictEqual(qa.exitCodeForResult({ pass: false }), 1);
console.log('OK');
"""
    )

    assert output == "OK"


def test_background_browser_harnesses_share_fail_closed_owner_guard_and_cleanup() -> None:
    output = run_node(
        r"""
const assert = require('assert');
const {
  assertNonOwnerQaSelection,
  cleanupQaRunArtifacts,
  withQaRequestIsolation,
} = require('./qa/background_agents/evals/browser-qa-safety.cjs');

assert.throws(
  () => assertNonOwnerQaSelection({ ownerEmail: '', requestedEmail: 'qa@example.com', selectedUser: { email: 'qa@example.com' } }),
  /missing_owner_email_guard/,
);
assert.throws(
  () => assertNonOwnerQaSelection({ ownerEmail: 'owner@example.com', requestedEmail: 'OWNER@example.com', selectedUser: { email: 'owner@example.com' } }),
  /qa_email_matches_owner_refused/,
);
assert.throws(
  () => assertNonOwnerQaSelection({ ownerEmail: 'owner@example.com', requestedEmail: 'qa@example.com', selectedUser: { email: 'owner@example.com' } }),
  /selected_owner_account_refused/,
);
assert.strictEqual(
  assertNonOwnerQaSelection({ ownerEmail: 'owner@example.com', requestedEmail: 'qa@example.com', selectedUser: { email: 'qa@example.com' } }),
  true,
);
assert.deepStrictEqual(withQaRequestIsolation({ text: 'hello' }, 'qa-run-123'), {
  text: 'hello',
  viventiumQaRun: true,
  viventiumQaRunId: 'qa-run-123',
  viventiumEvalIsolation: {
    savedMemory: true,
    conversationRecall: true,
    feelings: true,
  },
});

const calls = [];
let findQuery;
const db = {
  collection(name) {
    if (name === 'messages') {
      return {
        find(query) {
          findQuery = query;
          return { async toArray() { return [{ conversationId: 'qa-conversation', messageId: 'm1' }]; } };
        },
        async deleteMany(query) { calls.push(['messages', query]); return { deletedCount: 1 }; },
      };
    }
    if (name === 'conversations') {
      return {
        async deleteMany(query) { calls.push(['conversations', query]); return { deletedCount: 1 }; },
      };
    }
    throw new Error(`unexpected collection ${name}`);
  },
};

(async () => {
  const result = await cleanupQaRunArtifacts({
    db,
    userId: 'qa-user',
    startedAt: new Date('2026-07-10T12:00:00Z'),
    trackedConversationIds: ['qa-conversation'],
    qaRunId: 'qa-run-123',
  });
  assert.deepStrictEqual(result.conversationIds, ['qa-conversation']);
  assert.strictEqual(result.messagesDeleted, 1);
  assert.strictEqual(result.conversationsDeleted, 1);
  assert.strictEqual(calls.length, 2);
  assert.strictEqual(findQuery['metadata.viventium.qaRunId'], 'qa-run-123');
  await assert.rejects(
    cleanupQaRunArtifacts({
      db,
      userId: 'qa-user',
      startedAt: new Date('2026-07-10T12:00:00Z'),
      trackedConversationIds: ['qa-conversation'],
      qaRunId: 'qa-run-123',
      meiliClient: {
        index() {
          return {
            async deleteDocuments() { return { taskUid: 1 }; },
            async waitForTask() { return { status: 'failed' }; },
          };
        },
      },
    }),
    /qa_cleanup_meili_messages_failed/,
  );
  console.log('OK');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    )
    assert output == "OK"

    harnesses = [
        ROOT / "qa" / "background_agents" / "evals" / "run-visible-cards-browser-qa.cjs",
        ROOT
        / "qa"
        / "background_agents"
        / "evals"
        / "run-latest-user-activation-browser-qa.cjs",
        ROOT
        / "qa"
        / "background_agents"
        / "evals"
        / "run-interruption-restart-browser-qa.cjs",
    ]
    for harness in harnesses:
        source = harness.read_text(encoding="utf-8")
        assert re.search(r"\bassertNonOwnerQaSelection\s*\(", source)
        assert re.search(r"\bcleanupQaRunArtifacts\s*\(", source)
        assert re.search(r"\binstallQaRequestIsolation\s*\(", source)
        assert "VIVENTIUM_QA_OWNER_EMAIL" in source
    latest_source = harnesses[1].read_text(encoding="utf-8")
    assert "waitForExpectedTextAfterReload" in latest_source
