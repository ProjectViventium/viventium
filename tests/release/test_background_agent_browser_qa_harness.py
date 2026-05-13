from __future__ import annotations

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
