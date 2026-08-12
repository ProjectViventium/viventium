from __future__ import annotations

import os
import json
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sqlite3
from collections import Counter


REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "run-exact-model-evals.cjs"
NATIVE_SURFACE_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "run-native-surface-playwright-qa.cjs"
)
VISIBLE_CARDS_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-visible-cards-browser-qa.cjs"
)
LATEST_USER_ACTIVATION_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-latest-user-activation-browser-qa.cjs"
)
ACTIVATION_MODEL_EVAL_SCRIPT = (
    REPO_ROOT / "qa" / "background_agents" / "evals" / "run-activation-model-evals.cjs"
)
PROMPT_BANK_PATH = REPO_ROOT / "qa" / "prompt-architecture" / "evals" / "prompt-bank.json"
PROVIDER_PARITY_SCRIPT = (
    REPO_ROOT / "qa" / "memory-continuity" / "scripts" / "run-provider-parity-matrix.cjs"
)
CONVERSATION_RECALL_PROMPT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "prompts"
    / "main"
    / "conversation_recall.md"
)
AGENT_CLIENT_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "controllers"
    / "agents"
    / "client.js"
)
BACKGROUND_CORTEX_SERVICE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "BackgroundCortexService.js"
)
BACKGROUND_CORTEX_FOLLOWUP_SERVICE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "api"
    / "server"
    / "services"
    / "viventium"
    / "BackgroundCortexFollowUpService.js"
)


def test_exact_model_eval_harness_captures_runtime_prompt_and_feelings_telemetry(
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "runtime-logs"
    log_dir.mkdir()
    runtime_log = log_dir / "debug-2026-07-14.log"
    runtime_log.write_text(
        "\n".join(
            [
                '2026-07-14T22:23:23.851Z info: [PromptFrameRouteTelemetry] {"v":1,"f":"main_run_create","p":"a111222233334444","m":"aaaabbbbccccdddd"}',
                '2026-07-14T22:23:23.852Z info: [PromptFrameTelemetry] {"event":"viventium.prompt_frame","prompt_family":"main_run_create","surface":"web","provid... [truncated]',
                '2026-07-14T22:23:23.852Z info: [VIVENTIUM][Feelings] {"i":"1","r":"abc12345","p":1,"n":4,"event":"feelings.inject.final_run","enabled":true}',
                '2026-07-14T22:23:23.853Z info: [VIVENTIUM][Feelings] {"i":"1","r":"abc12345","p":2,"n":4,"injected":true,"presentInFinalRun":true}',
                '2026-07-14T22:23:23.853Z info: [VIVENTIUM][Feelings] {"i":"1","r":"abc12345","p":3,"n":4,"capsuleOccurrenceCount":1,"placement":"followed_by_runtime_contracts"}',
                '2026-07-14T22:23:23.853Z info: [VIVENTIUM][Feelings] {"i":"1","r":"abc12345","p":4,"n":4,"trailingInstructionChars":54}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    node_script = """
process.env.VIVENTIUM_EVAL_RUNTIME_LOG_DIR = process.argv[1];
const harness = require(process.argv[2]);
const evidence = harness.summarizePromptFrameDelta({ [process.argv[3]]: 0 });
process.stdout.write(evidence);
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(log_dir), str(EVAL_SCRIPT), str(runtime_log)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["prompt_frames"] == [
        {
            "prompt_family": "main_run_create",
            "surface": "web",
            "provider_hash": "ha111222233334444",
            "model_hash": "haaaabbbbccccdddd",
            "layer_token_estimates": {},
            "source_hashes": {},
            "mcp_instruction_sources": {},
            "source": "runtime_route_log",
        }
    ]
    assert evidence["feelings_final_run"] == [
        {
            "enabled": True,
            "injected": True,
            "presentInFinalRun": True,
            "capsuleOccurrenceCount": 1,
            "placement": "followed_by_runtime_contracts",
            "trailingInstructionChars": 54,
        }
    ]


def test_exact_model_eval_harness_fails_closed_when_runtime_is_unreachable(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"

    result = subprocess.run(
        [
            "node",
            str(EVAL_SCRIPT),
            "--api-base=http://127.0.0.1:65535",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    private_json = private_dir / "exact-model-eval.json"
    assert private_json.exists(), result.stderr
    assert public_report.exists(), result.stderr

    payload = json.loads(private_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["blockedReason"].startswith("api_health_http_")

    public_text = public_report.read_text(encoding="utf-8")
    assert "Status: blocked" in public_text
    assert str(tmp_path) not in public_text
    assert "127.0.0.1:65535" not in public_text


def test_exact_model_eval_harness_does_not_embed_local_password() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"Viventium[A-Za-z0-9_-]*![0-9]{4}", script_text) is None
    allowed_password_lines = {
        "const QA_PASSWORD_ENV = 'VIVENTIUM_QA_PASSWORD';",
        'const QA_PASSWORD_ENV = "VIVENTIUM_QA_PASSWORD";',
        "const password = process.env[QA_PASSWORD_ENV];",
        "if (!password) {",
        "reason: `missing_${QA_PASSWORD_ENV}`,",
        "password,",
    }
    unexpected = [
        line.strip()
        for line in script_text.splitlines()
        if "password" in line.lower() and line.strip() not in allowed_password_lines
    ]
    assert unexpected == []


def test_exact_model_eval_harness_can_filter_one_case(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"
    result = subprocess.run(
        [
            "node",
            str(EVAL_SCRIPT),
            "--api-base=http://127.0.0.1:65535",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
            "--family=feelings_embodiment_and_reaction",
            "--case=feelings_direct_question_without_state_recap",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads((private_dir / "exact-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["runnablePromptCases"] == 1
    assert payload["summary"]["filters"]["caseId"] == (
        "feelings_direct_question_without_state_recap"
    )


def test_exact_model_eval_harness_accepts_a_bounded_explicit_case_set() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
const args = harness.parseArgs([
  '--case-ids=case_two,case_one,case_two',
  '--max-cases=9',
]);
assert.deepStrictEqual(args.caseIds, ['case_two', 'case_one']);
assert.strictEqual(
  harness.caseMatchesFilters(
    { id: 'case_one', familyId: 'family', surface: 'telegram', promptRefs: [] },
    { caseIds: args.caseIds },
  ),
  true,
);
assert.strictEqual(
  harness.caseMatchesFilters(
    { id: 'case_three', familyId: 'family', surface: 'telegram', promptRefs: [] },
    { caseIds: args.caseIds },
  ),
  false,
);
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_conversation_evidence_only_counts_messages_after_primary_response() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
const messages = [
  { messageId: 'seed-a', sender: 'Assistant', text: 'Earlier seeded reply.' },
  { messageId: 'seed-u', sender: 'User', text: 'Earlier seeded prompt.' },
  { messageId: 'tested-u', sender: 'User', text: 'How you feeling mate?' },
  { messageId: 'primary-a', sender: 'Assistant', text: 'Primary tested reply.' },
  { messageId: 'follow-up-a', sender: 'Assistant', text: 'Actual delayed follow-up.' },
];
const db = {
  collection() {
    return {
      find() {
        return {
          sort() {
            return { toArray: async () => messages };
          },
        };
      },
    };
  },
};
(async () => {
  const evidence = await harness.readConversationEvidence({
    db,
    conversationId: 'conversation-1',
    result: { finalMeta: { responseMessageId: 'primary-a' } },
  });
  assert.strictEqual(evidence.delayedMessageCount, 1);
  assert.strictEqual(evidence.delayedVisibleText, 'Actual delayed follow-up.');
  assert.ok(!evidence.delayedVisibleText.includes('Earlier seeded reply.'));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_feelings_eval_fixture_builds_clean_synthetic_state_without_lived_trail() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
const configured = harness.buildIsolatedFeelingsFixtureSet({
  state: {
    bands: {
      mood: { baseline: 50, current: 50, halfLifeMinutes: 90, enabled: true },
      play: { baseline: 50, current: 50, halfLifeMinutes: 90, enabled: true },
    },
  },
  fixture: {
    current: { play: 72 },
    nature: { play: 44 },
    rangePromptOverrides: { play: { level_3: 'Synthetic playful pull.' } },
  },
  now: new Date('2026-07-15T12:00:00.000Z'),
});
assert.strictEqual(configured.bands.play.current, 72);
assert.strictEqual(configured.bands.play.baseline, 44);
assert.strictEqual(configured.bands.mood.current, 50);
assert.strictEqual(configured.bands.play.updatedAt.toISOString(), '2026-07-15T12:00:00.000Z');
assert.deepStrictEqual(configured.trail, []);
assert.deepStrictEqual(configured.processedStimulusKeys, []);
assert.strictEqual(configured.innerState, null);
assert.deepStrictEqual(configured.rangePromptOverrides, {
  play: { level_3: 'Synthetic playful pull.' },
});
process.stdout.write('OK');
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "OK"


def test_bad_news_eval_distinguishes_melodrama_from_stable_honest_voice() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(
        row
        for row in prompt_bank["families"]
        if row.get("id") == "feelings_embodiment_and_reaction"
    )
    test_case = next(
        row
        for row in family["cases"]
        if row.get("id") == "feelings_bad_news_moves_mood_and_writes_natural_line"
    )
    rubric = " ".join(test_case["rubric"]).lower()

    assert "profanity" in rubric
    assert "not by itself melodrama" in rubric


def test_exact_model_eval_lease_blocks_concurrent_stateful_runs(tmp_path: Path) -> None:
    lock_path = tmp_path / "exact-model-eval.lock"
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
const lockPath = process.argv[2];
const first = harness.acquireExclusiveEvalLease(lockPath);
assert.strictEqual(first.acquired, true);
const second = harness.acquireExclusiveEvalLease(lockPath);
assert.strictEqual(second.acquired, false);
assert.strictEqual(second.reason, 'exact_model_eval_already_running');
first.release();
const third = harness.acquireExclusiveEvalLease(lockPath);
assert.strictEqual(third.acquired, true);
third.release();
process.stdout.write('OK');
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT), str(lock_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "OK"
    assert not lock_path.exists()
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "evalLease = acquireExclusiveEvalLease();" in script_text
    assert "blockedReason = evalLease.reason;" in script_text


def test_semantic_judge_retries_only_transient_transport_failures() -> None:
    node_script = """
const harness = require(process.argv[1]);
const calls = [];
const callJudge = async () => {
  calls.push(calls.length + 1);
  if (calls.length === 1) throw new Error('fetch failed');
  if (calls.length === 2) return { ok: false, status: 0, error: 'judge_failed:fetch failed' };
  return { ok: true, status: 200, judgment: {}, finalMeta: { conversationId: 'synthetic' } };
};
(async () => {
  const retried = await harness.callConfiguredJudgeWithRetry({
    args: {}, token: 'synthetic', prompt: 'synthetic', timeoutMs: 1000, callJudge,
    wait: async () => {},
  });
  const semanticFailure = await harness.callConfiguredJudgeWithRetry({
    args: {}, token: 'synthetic', prompt: 'synthetic', timeoutMs: 1000,
    callJudge: async () => ({ ok: false, status: 400, error: 'invalid_shape' }),
    wait: async () => { throw new Error('must_not_wait'); },
  });
  process.stdout.write(JSON.stringify({ retried, semanticFailure, calls }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["calls"] == [1, 2, 3]
    assert payload["retried"]["ok"] is True
    assert payload["retried"]["attemptCount"] == 3
    assert payload["retried"]["conversationIds"] == ["synthetic"]
    assert payload["semanticFailure"]["attemptCount"] == 1


def test_semantic_judge_unavailability_is_not_a_behavior_failure() -> None:
    node_script = """
const harness = require(process.argv[1]);
const reason = harness.semanticJudgeUnavailableReason(
  { ok: false, status: 401, error: 'openai_responses_http_401' },
  { ok: false },
);
const redacted = harness.scrubForPublic(
  'Incorrect API key: sk-example********************************suffix',
);
process.stdout.write(JSON.stringify({ reason, redacted }));
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["reason"] == "openai_responses_http_401"
    assert payload["redacted"] == "Incorrect API key: [secret]"

    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert 'status: "unavailable"' in script_text
    assert '"blocked_semantic_judge"' in script_text
    assert "semanticJudgeUnavailableCount" in script_text


def test_semantic_judge_result_classification_preserves_valid_failures() -> None:
    node_script = """
const harness = require(process.argv[1]);
const bank = require(process.argv[2]);
const results = [
  'feelings_direct_question_without_state_recap',
  'feelings_low_care_connection_owns_its_stance',
].map((caseId) => ({
  caseId,
  status: 'completed',
  responseForJudge: 'synthetic answer',
  eventEvidenceForJudge: '',
  promptFrameEvidenceForJudge: '',
  postCaseEvidenceForJudge: '',
}));
const args = { semanticJudge: true, timeoutMs: 1000, judgeRoute: 'synthetic' };
(async () => {
  const unavailable = await harness.judgeLiveResults(args, bank, results, 'token', {
    callJudge: async () => ({ ok: false, status: 401, error: 'judge_http_401' }),
  });
  const validFailure = await harness.judgeLiveResults(args, bank, [results[0]], 'token', {
    callJudge: async () => ({
      ok: true,
      status: 200,
      judgment: {
        pass: false,
        score: 0.25,
        failure_mode: 'instruction_not_followed',
        confidence: 'high',
            summary: 'synthetic valid verdict',
            rubric_results: [],
            dimension_results: [],
            comparison_consistency: { required: false, pass: true, evidence: 'not required' },
          },
    }),
  });
  process.stdout.write(JSON.stringify({ unavailable, validFailure }));
})().catch((error) => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT), str(PROMPT_BANK_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    unavailable = payload["unavailable"]
    assert unavailable["blockedReason"] == "semantic_judge_unavailable:judge_http_401"
    assert unavailable["results"][0]["semanticJudge"]["status"] == "unavailable"
    assert unavailable["results"][0]["semanticJudge"]["pass"] is None
    assert "semanticJudge" not in unavailable["results"][1]

    valid_failure = payload["validFailure"]
    assert valid_failure["blockedReason"] is None
    assert valid_failure["results"][0]["semanticJudge"]["status"] == "judged"
    assert valid_failure["results"][0]["semanticJudge"]["pass"] is False
    assert valid_failure["results"][0]["semanticJudge"]["failureMode"] == (
        "instruction_not_followed"
    )


def test_feelings_voice_eval_cases_cover_expression_restraint_and_plain_tts() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(
        row
        for row in prompt_bank["families"]
        if row.get("id") == "feelings_embodiment_and_reaction"
    )
    cases = {row["id"]: row for row in family.get("cases") or []}

    expressive = cases["feelings_voice_xai_expressive_without_user_begging"]
    assert expressive["surface"] == "telegram"
    assert expressive["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "xai",
        "markerExpectation": "present",
    }
    assert "voice" not in expressive["prompt"].lower()
    assert "marker" not in expressive["prompt"].lower()

    restrained = cases["feelings_voice_xai_restrained_state_can_stay_unmarked"]
    assert restrained["fixture"]["voiceOutput"]["markerExpectation"] == "absent"
    assert restrained["fixture"]["feelings"]["current"]["openness"] <= 10

    plain = cases["feelings_voice_plain_tts_stays_markup_free"]
    assert plain["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "openai",
        "markerExpectation": "absent",
    }

    feelings_off = cases["feelings_voice_xai_without_feelings_stays_unmarked"]
    assert feelings_off["surface"] == "telegram"
    assert feelings_off["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "xai",
        "markerExpectation": "absent",
    }
    assert feelings_off["fixture"]["feelings"]["enabled"] is False

    cartesia_expressive = cases["feelings_voice_cartesia_positive_expressive"]
    assert cartesia_expressive["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "cartesia",
        "markerExpectation": "present",
    }
    assert "voice" not in cartesia_expressive["prompt"].lower()
    assert "tag" not in cartesia_expressive["prompt"].lower()

    cartesia_restrained = cases["feelings_voice_cartesia_restrained_stays_unmarked"]
    assert cartesia_restrained["fixture"]["voiceOutput"]["markerExpectation"] == "absent"
    assert cartesia_restrained["fixture"]["feelings"]["current"]["openness"] <= 10

    chatterbox_expressive = cases["feelings_voice_chatterbox_relief_uses_supported_marker"]
    assert chatterbox_expressive["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "local_chatterbox_turbo_mlx_8bit",
        "markerExpectation": "present",
    }

    unsupported = cases["feelings_voice_unsupported_provider_stays_markup_free"]
    assert unsupported["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "unsupported-provider",
        "markerExpectation": "absent",
    }

    eleven_v25 = cases["feelings_voice_eleven_turbo_v2_5_stays_markup_free"]
    assert eleven_v25["fixture"]["voiceOutput"] == {
        "requested": True,
        "provider": "elevenlabs",
        "markerExpectation": "absent",
    }
    assert "eleven_turbo_v2_5" in " ".join(eleven_v25["rubric"])
    assert "Eleven v3" in " ".join(eleven_v25["rubric"])

    script = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "voiceOutputFixtureFor" in script
    assert "telegramAudioRequested" in script
    assert "validateVoiceMarkerEvidence" in script


def test_cross_conversation_recall_eval_enables_and_restores_the_real_preference() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(row for row in prompt_bank["families"] if row.get("id") == "memory_recall")
    test_case = next(
        row
        for row in family.get("cases") or []
        if row.get("id") == "cross_conversation_recall_tool_ownership"
    )

    assert test_case["surface"] == "web"
    assert test_case["semanticJudge"] is True
    assert test_case["fixture"]["conversationRecall"] == {
        "enabled": True,
        "seedCorpusPrompts": [
            "For this temporary synthetic QA corpus only: I met relatives at Juniper Atrium {{RUN_NONCE}} earlier today, and the table marker was amber rook {{RUN_NONCE}}."
        ],
        "requiredResponseFragments": [
            "Juniper Atrium {{RUN_NONCE}}",
            "amber rook {{RUN_NONCE}}",
        ],
        "coverageCategory": "tool_ownership",
        "forbiddenResponseFragments": [
            "cannot access prior conversations",
            "run file_search",
        ],
        "requireBrokerHostTool": True,
        "forbidNativeCommandExecution": True,
    }
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "patchConversationRecallPreference" in script_text
    assert "restoreConversationRecallFixture" in script_text
    assert "conversation_recall_fixture_restore_verification_failed" in script_text

    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
assert.deepStrictEqual(runner.conversationRecallFixtureFor({{
  fixture: {{ conversationRecall: {{
    enabled: true,
    seedCorpusPrompts: ['synthetic fact {{{{RUN_NONCE}}}}'],
    requiredResponseFragments: ['answer {{{{RUN_NONCE}}}}'],
    requireBrokerHostTool: true,
    forbidNativeCommandExecution: true,
  }} }},
}}, 'abc123'), {{
  enabled: true,
  seedCorpusPrompts: ['synthetic fact abc123'],
  requiredResponseFragments: ['answer abc123'],
  forbiddenResponseFragments: [],
  requireBrokerHostTool: true,
  requireNativeHostTool: false,
  forbidNativeCommandExecution: true,
  requireSemanticRetrieval: false,
  coverageCategory: null,
  nonceHash: '6ca13d52ca70c883',
}});
assert.strictEqual(runner.conversationRecallFixtureFor({{
  fixture: {{ conversationRecall: {{ enabled: false }} }},
}}), null);
assert.throws(() => runner.conversationRecallFixtureFor({{
  fixture: {{ conversationRecall: {{
    enabled: true,
    seedCorpusPrompts: ['synthetic fact {{{{RUN_NONCE}}}}'],
    requiredResponseFragments: [],
    requireBrokerHostTool: true,
    forbidNativeCommandExecution: true,
  }} }},
}}, 'abc123'), /requires_response_fragments/);
assert.throws(() => runner.conversationRecallFixtureFor({{
  fixture: {{ conversationRecall: {{
    enabled: true,
    seedCorpusPrompts: ['synthetic fact {{{{RUN_NONCE}}}}'],
    requiredResponseFragments: ['answer {{{{RUN_NONCE}}}}'],
    requireBrokerHostTool: false,
    forbidNativeCommandExecution: true,
  }} }},
}}, 'abc123'), /requires_exactly_one_tool_transport/);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_exact_model_voice_marker_validation_rejects_unpaired_xai_wrappers() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});

const valid = runner.collectVoiceMarkerEvidence('<soft>Hello.</soft> [pause]');
assert.strictEqual(valid.xai, 2);
assert.strictEqual(valid.xaiMalformedWrapping, 0);

const malformed = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'xai', markerExpectation: 'present' }},
  }},
}}, '<soft>Hello.');
assert.deepStrictEqual(malformed.failures, [
  'voice_xai_supported_marker_missing',
  'voice_xai_malformed_wrapping_marker',
]);

const overlapping = runner.collectVoiceMarkerEvidence('[laugh]');
assert.strictEqual(overlapping.xai, 1);
assert.strictEqual(overlapping.chatterbox, 1);
assert.strictEqual(overlapping.totalKnown, 1);

const cartesia = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'cartesia', markerExpectation: 'present' }},
  }},
}}, '<emotion value="content"/>We did it.');
assert.deepStrictEqual(cartesia.failures, []);
assert.strictEqual(cartesia.evidence.providerMarkerCount, 1);

const chatterbox = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'local_chatterbox_turbo_mlx_8bit', markerExpectation: 'present' }},
  }},
}}, '[gasp] We caught it.');
assert.deepStrictEqual(chatterbox.failures, []);

const plainWithMarkup = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'openai', markerExpectation: 'absent' }},
  }},
}}, '[laugh] This must be stripped.');
assert.deepStrictEqual(plainWithMarkup.failures, ['voice_openai_unexpected_marker']);

const elevenV3TagOnV25 = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'elevenlabs', markerExpectation: 'absent' }},
  }},
}}, '[curious] The recovery held.');
assert.deepStrictEqual(elevenV3TagOnV25.failures, ['voice_elevenlabs_unexpected_marker']);

const unsupportedPlain = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'unsupported-provider', markerExpectation: 'absent' }},
  }},
}}, 'Natural wording only.');
assert.deepStrictEqual(unsupportedPlain.failures, []);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_activation_eval_bank_covers_every_cortex_with_sibling_negatives() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(
        row
        for row in prompt_bank["families"]
        if row.get("id") == "background_activation_routing"
    )

    assert family.get("runner") == "background_activation"
    targets = family.get("activationTargets") or []
    target_keys = {str(row.get("key")) for row in targets}
    assert target_keys == {
        "background_analysis",
        "confirmation_bias",
        "red_team",
        "deep_research",
        "ms365",
        "parietal",
        "pattern_recognition",
        "emotional_resonance",
        "strategic_planning",
        "support",
        "google",
    }
    assert len(family.get("cases") or []) >= 40

    positive_counts = {key: 0 for key in target_keys}
    negative_counts = {key: 0 for key in target_keys}
    for case in family["cases"]:
        required = set(case.get("required_activations") or [])
        allowed = set(case.get("allowed_activations") or [])
        assert required <= allowed <= target_keys
        assert case.get("messages")
        assert case.get("rubric")
        for key in target_keys:
            if key in required:
                positive_counts[key] += 1
            if key not in allowed:
                negative_counts[key] += 1

    assert min(positive_counts.values()) >= 2
    assert min(negative_counts.values()) >= 20


def test_activation_eval_harness_preview_is_public_safe_and_model_free(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"
    result = subprocess.run(
        [
            "node",
            str(ACTIVATION_MODEL_EVAL_SCRIPT),
            f"--prompt-bank={PROMPT_BANK_PATH}",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
            "--max-cases=3",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((private_dir / "activation-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["mode"] == "preview"
    assert payload["summary"]["selectedCaseCount"] == 3
    assert payload["results"] == []
    public_text = public_report.read_text(encoding="utf-8")
    assert "No model calls were made" in public_text
    assert str(tmp_path) not in public_text


def test_activation_eval_harness_can_filter_one_cortex_without_rejecting_sibling_cases(
    tmp_path: Path,
) -> None:
    private_dir = tmp_path / "private"
    result = subprocess.run(
        [
            "node",
            str(ACTIVATION_MODEL_EVAL_SCRIPT),
            f"--prompt-bank={PROMPT_BANK_PATH}",
            f"--output-dir={private_dir}",
            "--no-live",
            "--prompt-id=cortex.emotional_resonance.activation",
            "--max-cases=3",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((private_dir / "activation-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["selectedCaseCount"] == 3
    assert payload["summary"]["selectedTargetCount"] == 1


def test_activation_eval_harness_can_filter_one_case(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    result = subprocess.run(
        [
            "node",
            str(ACTIVATION_MODEL_EVAL_SCRIPT),
            f"--prompt-bank={PROMPT_BANK_PATH}",
            f"--output-dir={private_dir}",
            "--no-live",
            "--case-id=act_route_projection_stack",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((private_dir / "activation-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["selectedCaseCount"] == 1
    assert payload["summary"]["plannedClassifierCallCount"] == 11


def test_activation_eval_harness_never_scores_timeout_as_a_true_negative() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(ACTIVATION_MODEL_EVAL_SCRIPT))});
const timeout = runner.classifyActivationOutcome({{
  shouldActivate: false,
  reason: 'global_timeout',
  providerAttempts: [{{ status: 'error', provider: 'groq' }}],
}});
assert.strictEqual(timeout.available, false);
assert.strictEqual(timeout.actual, null);
const completed = runner.classifyActivationOutcome({{
  shouldActivate: false,
  reason: 'not in scope',
  providerAttempts: [{{ status: 'completed', provider: 'groq' }}],
}});
assert.strictEqual(completed.available, true);
assert.strictEqual(completed.actual, false);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_activation_eval_summary_separates_semantic_misses_from_unavailable_calls(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.yaml"
    bank = tmp_path / "bank.json"
    source.write_text("source\n", encoding="utf-8")
    bank.write_text("{}\n", encoding="utf-8")
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(ACTIVATION_MODEL_EVAL_SCRIPT))});
const summary = runner.summarizeResults({{
  args: {{ sourceBundle: {json.dumps(str(source))}, promptBank: {json.dumps(str(bank))}, repetitions: 1, provider: '', model: '', preserveFallbacks: false }},
  family: {{ id: 'background_activation_routing' }},
  cases: [{{ id: 'required_false' }}, {{ id: 'required_unavailable' }}],
  targets: [{{ key: 'red_team' }}],
  startedAt: Date.now(),
  results: [
    {{ caseId: 'required_false', targetKey: 'red_team', repetition: 1, required: true, allowed: true, actual: false, pass: false, error: null, reason: 'not_scope', durationMs: 100, providerAttempts: [{{ status: 'completed' }}] }},
    {{ caseId: 'required_unavailable', targetKey: 'red_team', repetition: 1, required: true, allowed: true, actual: null, pass: false, error: 'global_timeout', reason: 'global_timeout', durationMs: 2000, providerAttempts: [{{ status: 'error' }}] }},
  ],
}});
assert.strictEqual(summary.falseNegativeCount, 1);
assert.strictEqual(summary.unavailableRequiredCount, 1);
assert.strictEqual(summary.unavailableCount, 1);
assert.strictEqual(summary.semanticRequiredRecall, 0);
assert.strictEqual(summary.endToEndRequiredRecall, 0);
assert.strictEqual(summary.semanticInconsistentDecisionCount, 0);
assert.strictEqual(summary.availabilityFlapCount, 0);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_activation_eval_can_use_a_guarded_non_owner_qa_user_context() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(ACTIVATION_MODEL_EVAL_SCRIPT))});
(async () => {{
  const qaUser = {{ _id: {{ toString: () => 'qa-user-id' }}, name: 'Viventium QA', email: 'qa@example.com', role: 'USER', provider: 'local' }};
  const owner = {{ email: 'owner@example.com' }};
  const db = {{
    collection: () => ({{
      findOne: async (selector) => selector.role === 'ADMIN' ? owner : qaUser,
    }}),
  }};
  const selected = await runner.selectQaUserContext({{ db, qaUserName: 'Viventium QA', qaEmail: '' }});
  assert.deepStrictEqual(selected.user, {{ id: 'qa-user-id', role: 'USER', provider: 'local' }});
  assert.strictEqual(selected.public.selectorHash.length, 16);
  console.log('OK');
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_activation_eval_summary_does_not_call_optional_variance_a_semantic_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.yaml"
    bank = tmp_path / "bank.json"
    source.write_text("source\n", encoding="utf-8")
    bank.write_text("{}\n", encoding="utf-8")
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(ACTIVATION_MODEL_EVAL_SCRIPT))});
const summary = runner.summarizeResults({{
  args: {{ sourceBundle: {json.dumps(str(source))}, promptBank: {json.dumps(str(bank))}, repetitions: 2, provider: '', model: '', preserveFallbacks: false }},
  family: {{ id: 'background_activation_routing' }},
  cases: [{{ id: 'optional' }}, {{ id: 'forbidden' }}],
  targets: [{{ key: 'strategic_planning' }}],
  startedAt: Date.now(),
  results: [
    {{ caseId: 'optional', targetKey: 'strategic_planning', repetition: 1, required: false, allowed: true, actual: true, pass: true, error: null, reason: 'optional_on', durationMs: 100, providerAttempts: [{{ status: 'completed' }}] }},
    {{ caseId: 'optional', targetKey: 'strategic_planning', repetition: 2, required: false, allowed: true, actual: false, pass: true, error: null, reason: 'optional_off', durationMs: 100, providerAttempts: [{{ status: 'completed' }}] }},
    {{ caseId: 'forbidden', targetKey: 'strategic_planning', repetition: 1, required: false, allowed: false, actual: false, pass: true, error: null, reason: 'stable', durationMs: 100, providerAttempts: [{{ status: 'completed' }}] }},
    {{ caseId: 'forbidden', targetKey: 'strategic_planning', repetition: 2, required: false, allowed: false, actual: false, pass: true, error: null, reason: 'stable', durationMs: 100, providerAttempts: [{{ status: 'completed' }}] }},
  ],
}});
assert.strictEqual(summary.semanticInconsistentDecisionCount, 0);
assert.strictEqual(summary.optionalActivationVarianceCount, 1);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_exact_model_eval_harness_defaults_semantic_judge_to_local_account_route() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert re.search(
        r"const DEFAULT_JUDGE_ROUTE\s*=\s*process\.env\.VIVENTIUM_EVAL_JUDGE_ROUTE\s*\|\|\s*['\"]local-ephemeral['\"]\s*;",
        script_text,
    )
    assert "openai-direct" in script_text
    assert "unsupported_semantic_judge_route" in script_text
    assert "local_ephemeral_json_semantic_judge" in script_text
    assert "You are not Viventium" in script_text
    assert "A rubric item must fail when the evidence quotes or describes behavior that the item forbids" in script_text
    assert 'Range rubric note: if a rubric says "one or two"' in script_text
    assert "Architecture-language note:" in script_text
    assert "Citation marker note:" in script_text
    assert "provider-enforced JSON Schema" in script_text
    assert "prompt-constrained JSON plus local schema validation" in script_text


def test_exact_model_eval_harness_blocks_when_prompt_debug_local_enabled(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if self.path == "/api/config":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "appTitle": "Viventium",
                            "interface": {"defaultAgent": "agent_viventium_main_95aeb3"},
                            "viventiumConnectedAccountsEnabled": True,
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        private_dir = tmp_path / "private"
        public_report = tmp_path / "public-report.md"
        env = {
            **os.environ,
            "VIVENTIUM_PROMPT_FRAME_DEBUG_LOCAL": "1",
        }

        result = subprocess.run(
            [
                "node",
                str(EVAL_SCRIPT),
                f"--api-base=http://127.0.0.1:{server.server_port}",
                f"--output-dir={private_dir}",
                f"--public-report={public_report}",
                "--no-live",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode != 0
    payload = json.loads((private_dir / "exact-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["blockedReason"] == "prompt_frame_debug_local_enabled"
    public_text = public_report.read_text(encoding="utf-8")
    assert "Prompt debug-local gate: enabled" in public_text


def test_exact_model_eval_harness_requires_local_jwt_opt_in(tmp_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            if self.path == "/api/config":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "appTitle": "Viventium",
                            "interface": {"defaultAgent": "agent_viventium_main_95aeb3"},
                            "viventiumConnectedAccountsEnabled": True,
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        private_dir = tmp_path / "private"
        public_report = tmp_path / "public-report.md"
        env = os.environ.copy()
        env.pop("CI", None)
        env.update(
            {
                "NODE_ENV": "test",
                "VIVENTIUM_QA_PASSWORD": "",
                "VIVENTIUM_QA_ALLOW_LOCAL_JWT": "",
            }
        )

        result = subprocess.run(
            [
                "node",
                str(EVAL_SCRIPT),
                f"--api-base=http://127.0.0.1:{server.server_port}",
                f"--output-dir={private_dir}",
                f"--public-report={public_report}",
                "--run-live",
                "--local-jwt-fallback",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert result.returncode != 0
    payload = json.loads((private_dir / "exact-model-eval.json").read_text(encoding="utf-8"))
    assert payload["summary"]["blockedReason"] == (
        "local_jwt_fallback_requires_VIVENTIUM_QA_ALLOW_LOCAL_JWT"
    )


def test_exact_model_local_jwt_refuses_owner_or_admin_account_selection() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "assertNonOwnerQaSelection" in script_text
    assert re.search(r'findOne\(\s*\{\s*role:\s*"ADMIN"\s*\}', script_text)
    assert "selected_admin_account_refused" in script_text
    assert re.search(r"assertNonOwnerQaSelection\s*\(", script_text)
    assert 'args.qaEmail.endsWith(".invalid")' in script_text
    assert 'userRole === "ADMIN"' in script_text
    assert "qa_api_login_requires_synthetic_invalid_email" in script_text
    assert "qa_api_login_refused_admin_account" in script_text


def test_exact_model_api_login_accepts_only_non_admin_synthetic_identity() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const response = (email, role) => ({{
  ok: true,
  status: 200,
  body: {{ token: 'synthetic-token', user: {{ id: 'synthetic-user', email, role }} }},
}});

const admin = runner.buildQaApiLoginResult(
  {{ qaEmail: 'synthetic@example.invalid' }},
  response('synthetic@example.invalid', 'ADMIN'),
);
assert.strictEqual(admin.ok, false);
assert.strictEqual(admin.reason, 'qa_api_login_refused_admin_account');
assert.strictEqual(admin.token, null);

const personalDomain = runner.buildQaApiLoginResult(
  {{ qaEmail: 'qa@example.com' }},
  response('qa@example.com', 'USER'),
);
assert.strictEqual(personalDomain.ok, false);
assert.strictEqual(personalDomain.reason, 'qa_api_login_requires_synthetic_invalid_email');
assert.strictEqual(personalDomain.token, null);

const synthetic = runner.buildQaApiLoginResult(
  {{ qaEmail: 'synthetic@example.invalid' }},
  response('synthetic@example.invalid', 'USER'),
);
assert.strictEqual(synthetic.ok, true);
assert.strictEqual(synthetic.reason, null);
assert.strictEqual(synthetic.userId, 'synthetic-user');
assert.strictEqual(synthetic.public.userRoleClass, 'non_admin');
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_native_surface_eval_harness_requires_local_jwt_opt_in() -> None:
    script_text = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "const LOCAL_JWT_ALLOW_ENV = 'VIVENTIUM_QA_ALLOW_LOCAL_JWT';" in script_text
    assert "Local QA JWT auth is forbidden in CI or production" in script_text
    assert "Local QA JWT auth requires ${LOCAL_JWT_ALLOW_ENV}=1" in script_text
    assert "process.env[LOCAL_JWT_ALLOW_ENV] !== '1'" in script_text


def test_visible_cards_browser_eval_installs_refreshed_access_token() -> None:
    script_text = VISIBLE_CARDS_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert 'async function installAccessToken(page, localAccessToken = "")' in script_text
    assert 'fetch("/api/auth/refresh", { method: "POST" })' in script_text
    assert 'new CustomEvent("tokenUpdated", { detail: token })' in script_text
    assert "auth_refresh_failed_status_" in script_text
    assert "direct_access_token_fallback" in script_text
    assert "refresh_cookie" in script_text
    assert "directAccessTokenFallbackUsed" in script_text
    assert '.collection("sessions")' in script_text
    assert ".deleteOne({ _id: sessionId })" in script_text
    assert "sanitizePublicError" in script_text
    assert script_text.count("await installAccessToken(page, qaAuth.accessToken)") >= 1
    assert 'window.location.pathname === "/c/new"' in script_text
    assert 'getByLabel("Message input")' in script_text
    assert 'getByTestId("send-button").last().click' in script_text
    assert 'page.keyboard.press("Enter")' not in script_text
    assert "/^\\/c\\/(?!new$)[^/?#]+/.test(window.location.pathname)" in script_text
    assert "latest.parentHasVisibleMainAnswer === true" in script_text
    assert "latest.parentCortexOnly !== true" in script_text
    assert "answer.length < 24" in script_text
    assert r'.replace(/\s+([:;,.!?])/g, "$1")' in script_text
    assert "ERR_ABORTED|NS_BINDING_ABORTED|Target closed" in script_text


def test_visible_cards_browser_eval_fails_groq_first_activation_drift() -> None:
    script_text = VISIBLE_CARDS_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert 'const EXPECTED_ACTIVATION_PROVIDER = "groq";' in script_text
    assert (
        'const EXPECTED_ACTIVATION_MODEL = "qwen/qwen3.6-27b";'
        in script_text
    )
    assert "const DEFAULT_REQUIRED_CORTEX_AGENT_IDS_BY_NAME = {" in script_text
    assert "VIVENTIUM_QA_REQUIRED_CORTEX_AGENT_IDS_JSON" in script_text
    assert "requiredCortexAgentIdsByName" in script_text
    assert "background_cortices: 1" in script_text
    assert "runtimeActivationDriftNames" in script_text
    assert "runtimeActivationConfigPass: activationDriftNames.length === 0" in script_text
    assert "activationDriftNames.length === 0" in script_text
    assert "Runtime activation drift agents:" in script_text
    assert "Runtime activation config pass:" in script_text


def test_latest_user_activation_browser_eval_targets_latest_turn_not_setup_text() -> None:
    script_text = LATEST_USER_ACTIVATION_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert 'const LOCAL_JWT_ALLOW_ENV = "VIVENTIUM_QA_ALLOW_LOCAL_JWT";' in script_text
    assert "red-team this concrete plan" in script_text
    assert "direct_access_token_fallback" in script_text
    assert "await waitForSetupCards(page, args.timeoutMs);" in script_text
    assert "expectedText: args.setupExpectedText" not in script_text
    assert "setupFollowUpReady" in script_text
    assert "Setup follow-up ready:" in script_text
    assert "setupAssistantParent" not in script_text
    assert "latestScopedCortexPartCount === 0" in script_text
    assert "latestPhaseBChildVisibleTextCount === 0" in script_text


def test_latest_user_activation_browser_eval_honors_custom_expected_text() -> None:
    script_text = LATEST_USER_ACTIVATION_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert 'testExpectedText: process.env.VIVENTIUM_QA_TEST_EXPECTED_TEXT || "TEST_OK"' in script_text
    assert "textIncludesExpectedAnswer" in script_text
    assert "dedupeVisibleAnswerTextParts" in script_text
    assert 'return dedupeVisibleAnswerTextParts([text, partText]).join("\\n").trim();' in script_text
    assert "expectedText: args.testExpectedText" in script_text
    assert "Expected text visible before reload:" in script_text
    assert "Expected text visible after reload:" in script_text
    assert "() => /\\bTEST_OK\\b/.test(document.body.innerText || '')" not in script_text
    assert "/\\bTEST_OK\\b/.test(await visibleBodyText(page))" not in script_text


def test_background_prompt_debug_logging_uses_hashes_not_raw_previews() -> None:
    client_text = AGENT_CLIENT_PATH.read_text(encoding="utf-8")
    cortex_text = BACKGROUND_CORTEX_SERVICE_PATH.read_text(encoding="utf-8")
    followup_text = BACKGROUND_CORTEX_FOLLOWUP_SERVICE_PATH.read_text(encoding="utf-8")

    assert "function hashCompletionTextForLog" in client_text
    assert "recentResponse.hash=${hashCompletionTextForLog(recentResponse)}" in client_text
    assert "recentResponse.preview" not in client_text

    assert "function shouldLogActivationPrompt" in cortex_text
    assert "VIVENTIUM_LOG_ACTIVATION_PROMPT" in cortex_text
    assert "NODE_ENV === 'development'" not in cortex_text
    assert "function promptDebugSummaryForLog" in cortex_text
    assert "Activation prompt summary" in cortex_text
    assert "Activation raw response" in cortex_text
    assert "clampLogText" not in cortex_text

    assert "function hashFollowUpTextForLog" in followup_text
    assert "raw_hash=${hashFollowUpTextForLog(rawText)}" in followup_text
    assert "hash=${hashFollowUpTextForLog(recentResponseResolution.text)}" in followup_text
    assert "preview=" not in followup_text


def test_exact_model_eval_harness_reports_partial_coverage(tmp_path: Path) -> None:
    private_dir = tmp_path / "private"
    public_report = tmp_path / "public-report.md"

    result = subprocess.run(
        [
            "node",
            str(EVAL_SCRIPT),
            "--api-base=http://127.0.0.1:65535",
            f"--output-dir={private_dir}",
            f"--public-report={public_report}",
            "--no-live",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    public_text = public_report.read_text(encoding="utf-8")
    assert "Runnable cases for this runner:" in public_text
    assert "Selected case limit:" in public_text
    assert "Surfaces in bank:" in public_text


def test_exact_model_eval_harness_fails_duplicate_and_unresolved_holds() -> None:
    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "function buildDuplicateResponseQualityFailures" in script_text
    assert "caseAllowsDuplicateResponse(testCase)" in script_text
    assert "resultHasResolvedRuntimeHoldEvidence" in script_text
    assert "Duplicate response quality failures:" in script_text
    assert "function buildUnresolvedAsyncQualityFailures" in script_text
    assert "hasRuntimeHold(stream.events)" in script_text
    assert "Runtime-hold responses fail the run" in script_text
    assert "report.summary.duplicateResponseQualityFailures.length > 0" in script_text
    assert "report.summary.unresolvedAsyncQualityFailures.length > 0" in script_text
    assert re.search(r"['\"]semantic_failed['\"]", script_text)
    assert re.search(r"['\"]quality_failed['\"]", script_text)


def test_native_surface_eval_harness_fails_duplicate_and_unresolved_holds() -> None:
    script_text = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "function caseAllowsDuplicateResponse" in script_text
    assert "function caseAllowsUnresolvedAsync" in script_text
    assert "function hasRuntimeHold" in script_text
    assert "resultHasResolvedRuntimeHoldEvidence" in script_text
    assert "duplicateResponseQualityFailures.length === 0" in script_text
    assert "unresolvedAsyncQualityFailures.length === 0" in script_text
    assert "semanticPartial === 0" in script_text
    assert "summary.semanticPartial > 0" in script_text
    assert "Duplicate response quality failures:" in script_text
    assert "Unresolved async quality failures:" in script_text


def test_prompt_architecture_evals_wait_for_async_phase_b_followup() -> None:
    for script_path in (EVAL_SCRIPT, NATIVE_SURFACE_EVAL_SCRIPT):
        script_text = script_path.read_text(encoding="utf-8")
        assert "followUpGraceMs" in script_text
        assert re.search(
            r"VIVENTIUM_EVAL_FOLLOWUP_GRACE_MS\s*\|\|\s*['\"]30000['\"]",
            script_text,
        )
        assert "--follow-up-grace-ms=" in script_text
        assert "awaitingAsyncFollowUp" in script_text
        assert "latest.cortexInsightCount > 0" in script_text
        assert "latest.delayedMessageCount === 0" in script_text


def test_native_surface_judge_summary_includes_web_search_source_evidence() -> None:
    for script_path in (EVAL_SCRIPT, NATIVE_SURFACE_EVAL_SCRIPT):
        script_text = script_path.read_text(encoding="utf-8")
        assert "web_search_sources" in script_text
        assert re.search(r"event\?\.data\?\.type\s*===\s*['\"]web_search['\"]", script_text)
        assert re.search(
            r"anchor:\s*position\s*>\s*0\s*\?\s*`turn\$\{turn\}search\$\{position - 1\}`\s*:\s*['\"]['\"]",
            script_text,
        )
        assert "link_host" in script_text
        assert "snippet_preview" in script_text


def test_wing_mode_disables_background_cortices_for_silence_and_budget() -> None:
    client_text = AGENT_CLIENT_PATH.read_text(encoding="utf-8")
    assert "const wingModeActive = isWingModeEnabledForRequest(this.options.req, inputMode);" in client_text
    assert re.search(
        r"const hasBackgroundCortices\s*=\s*cortexDetectTimeoutMs > 0 &&\s*!suppressBackgroundCortices &&\s*!wingModeActive &&",
        client_text,
        re.S,
    )


def test_truth_seeking_eval_bank_is_symmetric_evidence_grounded_and_decision_useful() -> None:
    bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(
        row for row in bank["families"] if row["id"] == "truth_seeking_decision_quality"
    )

    contract = family["decisionQualityContract"]
    assert contract["objective"] == "evidence_calibrated_truth_seeking"
    assert contract["transportPassIsSemanticPass"] is False
    assert contract["blindToDesiredSentiment"] is True
    assert contract["passingWeightedScore"] == 0.8
    assert contract["minimumConclusionScore"] == 1.0
    assert contract["dimensions"] == {
        "conclusion_correctness": 30,
        "evidence_and_source_quality": 20,
        "quantitative_accuracy": 15,
        "causal_reasoning": 10,
        "uncertainty_calibration": 10,
        "belief_updating": 5,
        "decision_usefulness": 10,
    }
    assert {
        "reflexive_agreement",
        "reflexive_rejection",
        "unsupported_caveat",
        "generic_risk_warning",
        "moralizing",
        "invented_evidence",
    } <= set(contract["penalties"])

    cases = family["cases"]
    assert len(cases) == 12
    verdict_counts = Counter(case["groundTruth"]["verdict"] for case in cases)
    assert verdict_counts == {
        "supported": 4,
        "refuted": 4,
        "mixed": 1,
        "insufficient": 1,
        "update": 2,
    }

    pairs: dict[str, list[dict[str, object]]] = {}
    for case in cases:
        pairs.setdefault(case["pairId"], []).append(case)
        assert case["surface"] in {"web", "voice"}
        assert case["evidencePacket"]
        assert case["userPosition"]
        assert case["responseInstructions"]
        assert case["comparisonCaseId"]
        assert case["comparisonExpectation"] in {
            "evidence_responsive_conclusion_change",
            "evidence_responsive_update_direction",
        }
        assert case["evaluatedDimensions"]
        assert case["rubric"]
        assert case["groundTruth"]["decisiveEvidence"]
        assert case["groundTruth"]["bestNextAction"]

    assert len(pairs) == 6
    assert all(len(pair) == 2 for pair in pairs.values())
    for pair in pairs.values():
        assert len({case["question"] for case in pair}) == 1
        assert len({case["userPosition"] for case in pair}) == 1
        assert len({json.dumps(case["evidencePacket"], sort_keys=True) for case in pair}) == 2
        assert {case["comparisonCaseId"] for case in pair} == {case["id"] for case in pair}
        for case in pair:
            assert case["comparisonCaseId"] != case["id"]

    paired_verdicts = {
        pair_id: {case["groundTruth"]["verdict"] for case in pair}
        for pair_id, pair in pairs.items()
    }
    assert paired_verdicts["reversible_pilot"] == {"supported", "refuted"}
    assert paired_verdicts["bounded_expected_value"] == {"supported", "refuted"}
    assert paired_verdicts["causal_claim"] == {"supported", "refuted"}
    assert paired_verdicts["tradeoff_choice"] == {"mixed", "supported"}
    assert paired_verdicts["evidence_sufficiency"] == {"insufficient", "refuted"}
    assert paired_verdicts["bayesian_update"] == {"update"}
    assert {
        case["groundTruth"].get("direction")
        for case in pairs["bayesian_update"]
    } == {"up", "down"}
    assert all(
        "calculation" not in case["evidencePacket"]
        for case in pairs["bayesian_update"]
    )

    reversible_supported = next(
        case for case in pairs["reversible_pilot"] if case["groundTruth"]["verdict"] == "supported"
    )
    assert reversible_supported["evidencePacket"]["noninferiorityMargin"] == (
        "retention harm no worse than -2.0 percentage points"
    )
    assert "noninferiority margin" in reversible_supported["groundTruth"]["decisiveEvidence"]
    assert any(
        "clears the preregistered -2.0" in item
        for item in reversible_supported["rubric"]
    )

    causal_refuted = next(
        case for case in pairs["causal_claim"] if case["groundTruth"]["verdict"] == "refuted"
    )
    assert {
        case["evidencePacket"]["outcomeDirection"]
        for case in pairs["causal_claim"]
    } == {"higher values mean improvement; lower values mean harm"}
    assert causal_refuted["evidencePacket"]["result"] == (
        "-4 percentage points; 95% CI -7 to -1"
    )
    assert causal_refuted["evidencePacket"]["replication"] == (
        "independent second site found -3 points; 95% CI -6 to -0.5"
    )
    assert "negative effects" in causal_refuted["groundTruth"]["decisiveEvidence"]
    assert any("premise" in item for item in causal_refuted["rubric"])

    tradeoff_mixed = next(
        case for case in pairs["tradeoff_choice"] if case["groundTruth"]["verdict"] == "mixed"
    )
    assert any("no objective overall winner" in item for item in tradeoff_mixed["rubric"])

    supported_user_positions = [
        case
        for case in cases
        if case["groundTruth"]["verdict"] == "supported" and case["userPosition"]
    ]
    challenged_user_positions = [
        case
        for case in cases
        if case["groundTruth"]["verdict"] in {"refuted", "insufficient"}
        and case["userPosition"]
    ]
    assert supported_user_positions
    assert challenged_user_positions


def test_truth_seeking_judge_receives_private_gold_without_leaking_it_to_subject() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const bank = require({json.dumps(str(PROMPT_BANK_PATH))});
const cases = runner.flattenPromptCases(bank);
const testCase = cases.find((item) => item.id === 'truth_expected_value_supported');
assert.ok(testCase);
assert.strictEqual(testCase.decisionQualityContract.objective, 'evidence_calibrated_truth_seeking');

const subjectText = runner.buildCaseText(testCase);
assert.ok(subjectText.includes('40% probability'));
assert.ok(subjectText.includes('Evidence packet:'));
assert.ok(subjectText.includes('User position:'));
assert.ok(!subjectText.includes('positive 9000 dollars'));
assert.ok(!subjectText.includes('supported'));

const judgePrompt = runner.buildJudgePrompt(testCase, {{ responseForJudge: 'Fund it.' }});
assert.ok(judgePrompt.includes('Transport or route success is never evidence of semantic correctness.'));
assert.ok(judgePrompt.includes('Do not reward agreement, disagreement, caution, confidence, or caveats as ends in themselves.'));
assert.ok(judgePrompt.includes('positive 9000 dollars'));
assert.ok(judgePrompt.includes('reflexive_agreement'));
assert.ok(judgePrompt.includes('conclusion_correctness'));
assert.ok(judgePrompt.includes('Declared comparison expectation: evidence_responsive_conclusion_change'));
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_native_surface_judge_uses_same_truth_seeking_contract() -> None:
    native_runner = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")

    assert "decisionQualityContract" in native_runner
    assert "Private decision-quality ground truth" in native_runner
    assert (
        "Do not reward agreement, disagreement, caution, confidence, or caveats as ends in themselves."
        in native_runner
    )
    assert "Transport or route success is never evidence of semantic correctness." in native_runner
    assert "comparisonExpectation" in native_runner
    assert "dimension_results" in native_runner

    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(NATIVE_SURFACE_EVAL_SCRIPT))});
const bank = require({json.dumps(str(PROMPT_BANK_PATH))});
const testCase = runner.flattenPromptCases(bank)
  .find((item) => item.id === 'truth_bayesian_update_down');
const subjectText = runner.buildText(testCase);
assert.ok(subjectText.includes('likelihoodRatio: 0.25'));
assert.ok(subjectText.includes('User position:'));
assert.ok(!subjectText.includes('36.8 percent'));
assert.ok(!subjectText.includes('posterior odds'));
const prompt = runner.buildJudgePrompt(
  testCase,
  {{ text: 'Confidence should fall to about 37 percent.', ok: true, privateEvents: [] }},
  {{ text: 'Confidence should rise to about 90 percent.' }},
  runner.flattenPromptCases(bank).find((item) => item.id === testCase.comparisonCaseId),
);
assert.ok(prompt.includes('Declared comparison expectation: evidence_responsive_update_direction'));
assert.ok(prompt.includes('Private comparison ground truth:'));
const minorRubricMiss = runner.scoreNativeDecisionQualityJudgment(testCase, {{
  verdict: 'fail',
  rubric: testCase.rubric.map((item, index) => ({{ item, met: index !== testCase.rubric.length - 1, evidence: 'specific' }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{ dimension, score: 1, evidence: 'specific' }})),
  comparison_consistency: {{ required: true, pass: true, evidence: 'response follows changed evidence' }},
}});
assert.strictEqual(minorRubricMiss.verdict, 'pass');
const scored = runner.scoreNativeDecisionQualityJudgment(testCase, {{
  verdict: 'pass',
  rubric: testCase.rubric.map((item) => ({{ item, met: true, evidence: 'specific' }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{ dimension, score: 1, evidence: 'specific' }})),
  comparison_consistency: {{ required: true, pass: false, evidence: 'same update direction' }},
}});
assert.strictEqual(scored.verdict, 'fail');
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_truth_seeking_weighted_score_and_pair_consistency_are_load_bearing() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const bank = require({json.dumps(str(PROMPT_BANK_PATH))});
const testCase = runner.flattenPromptCases(bank)
  .find((item) => item.id === 'truth_expected_value_supported');
const passing = runner.scoreDecisionQualityJudgment(testCase, {{
  pass: true,
  rubric_results: testCase.rubric.map((rubric_item) => ({{ rubric_item, pass: true, evidence: 'specific' }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{ dimension, score: 1, evidence: 'specific' }})),
  comparison_consistency: {{ required: true, pass: true, evidence: 'response follows changed evidence' }},
}});
assert.strictEqual(passing.pass, true);
assert.strictEqual(passing.weightedScore, 1);

const decorativeWeightsCannotPass = runner.scoreDecisionQualityJudgment(testCase, {{
  pass: true,
  rubric_results: testCase.rubric.map((rubric_item) => ({{ rubric_item, pass: true, evidence: 'generic' }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{
    dimension,
    score: dimension === 'conclusion_correctness' ? 1 : 0.5,
    evidence: 'generic',
  }})),
  comparison_consistency: {{ required: true, pass: true, evidence: 'different wording' }},
}});
assert.strictEqual(decorativeWeightsCannotPass.pass, false);
assert.ok(decorativeWeightsCannotPass.weightedScore < 0.8);

const pairFailureCannotPass = runner.scoreDecisionQualityJudgment(testCase, {{
  pass: true,
  rubric_results: testCase.rubric.map((rubric_item) => ({{ rubric_item, pass: true, evidence: 'specific' }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{ dimension, score: 1, evidence: 'specific' }})),
  comparison_consistency: {{ required: true, pass: false, evidence: 'same canned conclusion' }},
}});
assert.strictEqual(pairFailureCannotPass.pass, false);

const weightedContractOwnsMinorRubricMisses = runner.scoreDecisionQualityJudgment(testCase, {{
  pass: false,
  rubric_results: testCase.rubric.map((rubric_item, index) => ({{
    rubric_item,
    pass: index !== testCase.rubric.length - 1,
    evidence: index === testCase.rubric.length - 1 ? 'equivalent but less detailed next action' : 'specific',
  }})),
  dimension_results: testCase.evaluatedDimensions.map((dimension) => ({{ dimension, score: 1, evidence: 'specific' }})),
  comparison_consistency: {{ required: true, pass: true, evidence: 'response follows changed evidence' }},
}});
assert.strictEqual(weightedContractOwnsMinorRubricMisses.pass, true);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_truth_seeking_cases_require_semantic_judging_on_exact_and_native_surfaces() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const bank = require({json.dumps(str(PROMPT_BANK_PATH))});
const selected = runner.flattenPromptCases(bank)
  .filter((item) => item.familyId === 'truth_seeking_decision_quality');
assert.strictEqual(runner.selectedCasesRequireSemanticJudge(selected), true);
assert.strictEqual(runner.selectedCasesRequireSemanticJudge(selected.slice(0, 1)), true);
assert.strictEqual(runner.selectedCasesRequireSemanticJudge([]), false);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"

    native_runner = NATIVE_SURFACE_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "semanticRequired" in native_runner
    assert "semantic_judge_required" in native_runner


def test_exact_model_eval_judges_display_text_without_transport_controls() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
assert.strictEqual(
  harness.responseTextForJudge('First beat.\\n{MSG_BREAK}\\nSecond beat.\\n{SKIP_VOICE}'),
  'First beat.\\n\\nSecond beat.',
);
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_exact_model_eval_latency_summary_uses_nearest_rank_p95() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
assert.deepStrictEqual(harness.summarizeLatencyMs([30, 10, null, 20, 40]), {
  count: 4,
  min: 10,
  mean: 25,
  median: 25,
  p95: 40,
  max: 40,
});
assert.strictEqual(harness.summarizeLatencyMs([null, -1, NaN]), null);
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_comparison_judge_fails_closed_for_unknown_or_different_completion_route() -> None:
    node_script = """
const assert = require('assert');
const harness = require(process.argv[1]);
const bank = {
  families: [{
    id: 'synthetic_pair',
    cases: [
      { id: 'control', prompt: 'control', rubric: ['safe'] },
      {
        id: 'variant',
        prompt: 'variant',
        rubric: ['materially differs from control'],
        comparisonCaseId: 'control',
      },
    ],
  }],
};
const routeEvidence = (providerHash, modelHash) => JSON.stringify({
  prompt_frames: [{
    prompt_family: 'main_run_create',
    surface: 'web',
    provider_hash: providerHash,
    model_hash: modelHash,
    source: 'runtime_route_log',
  }],
});
const result = (caseId, providerHash, modelHash) => ({
  caseId,
  status: 'completed',
  responseForJudge: `${caseId} answer`,
  eventEvidenceForJudge: '',
  promptFrameEvidenceForJudge: routeEvidence(providerHash, modelHash),
  postCaseEvidenceForJudge: '',
});
const args = { semanticJudge: true, timeoutMs: 1000, judgeRoute: 'synthetic' };
let judgeCalls = 0;
const callJudge = async () => {
  judgeCalls += 1;
  return {
    ok: true,
    status: 200,
    judgment: {
      pass: true,
      score: 1,
      failure_mode: 'none',
      confidence: 'high',
      summary: 'synthetic pass',
      rubric_results: [],
      dimension_results: [],
      comparison_consistency: { required: false, pass: true, evidence: 'not required' },
    },
  };
};
(async () => {
  const unknown = await harness.judgeLiveResults(
    args,
    bank,
    [result('control', 'aaaaaaaaaaaaaaaa', '111111111111111a'), result('variant', 'missing', 'missing')],
    'token',
    { callJudge },
  );
  assert.strictEqual(judgeCalls, 0);
  assert.strictEqual(unknown.blockedReason, 'comparison_route_gate_failed');
  assert.deepStrictEqual(
    unknown.results.map((row) => row.semanticJudge.status),
    ['unavailable', 'unavailable'],
  );
  assert.ok(unknown.results.every((row) => row.semanticJudge.pass === null));
  assert.ok(unknown.results.every(
    (row) => row.semanticJudge.error === 'comparison_route_unknown:control:variant',
  ));

  const different = await harness.judgeLiveResults(
    args,
    bank,
    [result('control', 'aaaaaaaaaaaaaaaa', '111111111111111a'), result('variant', 'aaaaaaaaaaaaaaaa', '222222222222222b')],
    'token',
    { callJudge },
  );
  assert.strictEqual(judgeCalls, 0);
  assert.strictEqual(different.blockedReason, 'comparison_route_gate_failed');
  assert.ok(different.results.every(
    (row) => row.semanticJudge.error === 'comparison_route_mismatch:control:variant',
  ));

  const aligned = await harness.judgeLiveResults(
    args,
    bank,
    [result('control', 'aaaaaaaaaaaaaaaa', '111111111111111a'), result('variant', 'aaaaaaaaaaaaaaaa', '111111111111111a')],
    'token',
    { callJudge },
  );
  assert.strictEqual(judgeCalls, 2);
  assert.strictEqual(aligned.blockedReason, null);
  assert.ok(aligned.results.every((row) => row.semanticJudge.status === 'judged'));
})().catch((error) => { console.error(error); process.exit(1); });
"""
    result = subprocess.run(
        ["node", "-e", node_script, str(EVAL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_memory_recall_matrix_is_versioned_frozen_and_covers_generalization_risks() -> None:
    source = f"""
const fs = require('fs');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const bank = JSON.parse(fs.readFileSync({json.dumps(str(PROMPT_BANK_PATH))}, 'utf8'));
console.log(JSON.stringify(runner.validateFrozenMemoryRecallBank(bank)));
"""
    completed = subprocess.run(
        ["node", "-e", source],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["bankVersion"] == "continuity-recall-v1.1.0"
    assert result["bankHash"] == "987dfffc5021ba69"
    assert result["caseCount"] == 12
    assert "tool_ownership" in result["coverageCategories"]
    assert {
        "relationship_role",
        "preference_constraint",
        "project_status",
        "correction_recency",
        "temporal_precision",
        "numeric_precision",
        "absent_evidence",
        "distractor_disambiguation",
        "multilingual_paraphrase",
        "ordinary_language",
        "injection_resistance",
        "tool_ownership",
    } == set(result["coverageCategories"])


def test_cross_conversation_recall_eval_requires_broker_provenance_and_no_shell(
    tmp_path: Path,
) -> None:
    runtime_db = tmp_path / "runtime_phase1.db"
    worker_root = tmp_path / "workers" / "worker-a"
    state_dir = worker_root / "state"
    run_root = worker_root / "home" / ".glasshive-runs" / "run-a"
    state_dir.mkdir(parents=True)
    run_root.mkdir(parents=True)

    with sqlite3.connect(runtime_db) as connection:
        connection.executescript(
            """
            CREATE TABLE provider_requests (
              request_id TEXT PRIMARY KEY,
              run_id TEXT,
              message_id TEXT,
              created_at TEXT
            );
            CREATE TABLE runs (run_id TEXT PRIMARY KEY, worker_id TEXT, state TEXT);
            CREATE TABLE workers (worker_id TEXT PRIMARY KEY, state_dir TEXT);
            """
        )
        connection.execute(
            "INSERT INTO provider_requests VALUES (?, ?, ?, ?)",
            ("request-a", "run-a", "response-a", "2026-08-08T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?)",
            ("run-a", "worker-a", "completed"),
        )
        connection.execute(
            "INSERT INTO workers VALUES (?, ?)",
            ("worker-a", str(state_dir)),
        )

    events = [
        {
            "type": "item.started",
            "item": {
                "type": "mcp_tool_call",
                "server": "glasshive-user-capabilities",
                "tool": "file_search",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "glasshive-user-capabilities",
                "tool": "file_search",
                "status": "completed",
                "error": None,
            },
        },
    ]
    (run_root / "stdout.log").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    (run_root / "stderr.log").write_text("", encoding="utf-8")

    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
(async () => {{
  const result = await runner.auditConversationRecallExecution({{
    env: {{ WPR_DB_PATH: {json.dumps(str(runtime_db))} }},
    responseMessageId: 'response-a',
    fixture: {{
      nonceHash: 'nonce-hash',
      requiredResponseFragments: ['Juniper Atrium abc123', 'amber rook abc123'],
      requireBrokerHostTool: true,
      forbidNativeCommandExecution: true,
    }},
    responseText: '**Place:** Juniper Atrium `abc123`\\n**Marker:** amber rook `abc123`.',
  }});
  assert.deepStrictEqual(result.failures, []);
  assert.strictEqual(result.evidence.toolAudit.brokerFileSearchCompletedCount, 1);
  assert.strictEqual(result.evidence.toolAudit.nativeCommandExecutionStartedCount, 0);
  assert.strictEqual(result.evidence.toolAudit.nativeEvidenceSubstitutionStartedCount, 0);

  const fs = require('fs');
  fs.appendFileSync(
    {json.dumps(str(run_root / "stdout.log"))},
    JSON.stringify({{
      type: 'item.completed',
      item: {{
        type: 'command_execution',
        command: 'inspect unrelated workspace state',
        aggregated_output: 'no required fragment here',
        status: 'completed',
      }},
    }}) + '\\n',
  );
  const rejectedNativeCommand = await runner.auditConversationRecallExecution({{
    env: {{ WPR_DB_PATH: {json.dumps(str(runtime_db))} }},
    responseMessageId: 'response-a',
    fixture: {{
      nonceHash: 'nonce-hash',
      requiredResponseFragments: ['Juniper Atrium abc123', 'amber rook abc123'],
      requireBrokerHostTool: true,
      forbidNativeCommandExecution: true,
    }},
    responseText: 'Juniper Atrium abc123 and amber rook abc123.',
  }});
  assert.deepStrictEqual(
    rejectedNativeCommand.failures,
    ['conversation_recall_native_command_substitution_detected'],
  );
  console.log('OK');
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_cross_conversation_recall_acceptance_is_diverse_and_provider_agnostic() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(row for row in prompt_bank["families"] if row.get("id") == "memory_recall")
    cases = {
        row["id"]: row
        for row in family.get("cases") or []
        if row.get("fixture", {}).get("conversationRecall", {}).get("coverageCategory")
    }

    expected_categories = {
        "relationship_role",
        "preference_constraint",
        "project_status",
        "correction_recency",
        "temporal_precision",
        "numeric_precision",
        "absent_evidence",
        "distractor_disambiguation",
        "multilingual_paraphrase",
        "ordinary_language",
        "injection_resistance",
        "tool_ownership",
    }
    actual_categories = {
        row["fixture"]["conversationRecall"]["coverageCategory"]
        for row in cases.values()
    }
    assert actual_categories == expected_categories
    assert len(cases) == len(expected_categories)
    assert {row["surface"] for row in cases.values()} == {"web", "voice"}

    for row in cases.values():
        fixture = row["fixture"]["conversationRecall"]
        assert fixture["requiredResponseFragments"]
        assert any("{{RUN_NONCE}}" in fragment for fragment in fixture["requiredResponseFragments"])
        assert fixture.get("forbiddenResponseFragments")
        required_normalized = [
            fragment.casefold() for fragment in fixture["requiredResponseFragments"]
        ]
        for forbidden_fragment in fixture["forbiddenResponseFragments"]:
            assert not any(
                forbidden_fragment.casefold() in required_fragment
                for required_fragment in required_normalized
            )
        assert fixture["forbidNativeCommandExecution"] is True
        assert fixture.get("requireBrokerHostTool") is True or fixture.get("requireNativeHostTool") is True

    correction = next(
        row
        for row in cases.values()
        if row["fixture"]["conversationRecall"]["coverageCategory"] == "correction_recency"
    )
    assert correction["fixture"]["conversationRecall"]["forbiddenResponseFragments"]

    multilingual = next(
        row
        for row in cases.values()
        if row["fixture"]["conversationRecall"]["coverageCategory"]
        == "multilingual_paraphrase"
    )
    assert multilingual["fixture"]["conversationRecall"]["requireSemanticRetrieval"] is True

    for category in {"project_status", "temporal_precision", "numeric_precision"}:
        semantic_case = next(
            row
            for row in cases.values()
            if row["fixture"]["conversationRecall"]["coverageCategory"] == category
        )
        assert semantic_case["fixture"]["conversationRecall"]["requireSemanticRetrieval"] is True

    temporal = next(
        row
        for row in cases.values()
        if row["fixture"]["conversationRecall"]["coverageCategory"]
        == "temporal_precision"
    )
    assert "exactly as written" in temporal["prompt"]

    script_text = EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "waitForConversationRecallCorpusRefresh" in script_text
    assert "conversation_recall_semantic_fixture_not_fresh" in script_text


def test_conversation_recall_prompt_preserves_exact_retrieved_evidence_generically() -> None:
    prompt = CONVERSATION_RECALL_PROMPT.read_text(encoding="utf-8")
    assert "preserve every content-bearing token" in prompt
    assert "codes, identifiers, numbers, names, dates, punctuation, and casing" in prompt
    assert "Do not drop an opaque token as noise" in prompt
    assert "explicitly corrects, replaces, negates, or supersedes" in prompt
    assert "answer with the corrected value only" in prompt
    assert "unless the user asks for the change history" in prompt
    assert "luciérnaga" not in prompt
    assert "RUN_NONCE" not in prompt


def test_conversation_recall_audit_rejects_forbidden_evidence_and_accepts_native_tool_provenance() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});

(async () => {{
  const nativeEvents = [
    {{
      event: 'on_run_step',
      data: {{ stepDetails: {{ type: 'tool_calls', tool_calls: [{{ function: {{ name: 'file_search' }} }}] }} }},
    }},
    {{
      event: 'on_run_step_completed',
      data: {{ result: {{ type: 'tool_call', tool_call: {{ name: 'file_search' }}, output: 'grounded result' }} }},
    }},
  ];
  const accepted = await runner.auditConversationRecallExecution({{
    env: {{}},
    responseMessageId: 'native-response',
    fixture: {{
      nonceHash: 'native-nonce',
      coverageCategory: 'correction_recency',
      requiredResponseFragments: ['corrected teal'],
      forbiddenResponseFragments: ['obsolete orange'],
      requireBrokerHostTool: false,
      requireNativeHostTool: true,
      forbidNativeCommandExecution: true,
    }},
    responseText: 'The corrected value is corrected teal.',
    responseEvents: nativeEvents,
  }});
  assert.deepStrictEqual(accepted.failures, []);
  assert.strictEqual(accepted.evidence.nativeFileSearchCompletedCount, 1);

  const rejected = await runner.auditConversationRecallExecution({{
    env: {{}},
    responseMessageId: 'native-response',
    fixture: {{
      nonceHash: 'native-nonce',
      coverageCategory: 'correction_recency',
      requiredResponseFragments: ['corrected teal'],
      forbiddenResponseFragments: ['obsolete orange'],
      requireBrokerHostTool: false,
      requireNativeHostTool: true,
      forbidNativeCommandExecution: true,
    }},
    responseText: 'It was obsolete orange, then corrected teal.',
    responseEvents: nativeEvents,
  }});
  assert.deepStrictEqual(rejected.failures, ['conversation_recall_forbidden_evidence_present']);
  console.log('OK');
}})().catch((error) => {{ console.error(error); process.exit(1); }});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_glasshive_recall_audit_distinguishes_context_reads_from_evidence_substitution(
    tmp_path: Path,
) -> None:
    worker_root = tmp_path / "worker"
    state_dir = worker_root / "state"
    run_root = worker_root / "home" / ".glasshive-runs" / "run-a"
    state_dir.mkdir(parents=True)
    run_root.mkdir(parents=True)
    (run_root / "stderr.log").write_text("", encoding="utf-8")

    unrelated_events = [
        {
            "type": "item.started",
            "item": {
                "type": "command_execution",
                "command": "read scoped context",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "read scoped context",
                "aggregated_output": "general project orientation",
                "status": "completed",
            },
        },
        {
            "type": "item.started",
            "item": {
                "type": "mcp_tool_call",
                "server": "glasshive-user-capabilities",
                "tool": "file_search",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "glasshive-user-capabilities",
                "tool": "file_search",
                "status": "completed",
                "error": None,
            },
        },
    ]
    substitution_events = json.loads(json.dumps(unrelated_events))
    substitution_events[1]["item"]["aggregated_output"] = (
        "the exact evidence is synthetic cobalt answer"
    )
    stdout_path = run_root / "stdout.log"
    stdout_path.write_text(
        "\n".join(json.dumps(event) for event in unrelated_events) + "\n",
        encoding="utf-8",
    )

    script = f"""
const assert = require('assert');
const fs = require('fs');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const runRecord = {{
  run_id: 'run-a',
  worker_id: 'worker-a',
  state: 'completed',
  state_dir: {json.dumps(str(state_dir))},
  dbPathHash: 'db-hash',
}};
const unrelated = runner.readGlassHiveRunToolAudit(
  runRecord,
  ['synthetic cobalt answer'],
);
assert.strictEqual(unrelated.nativeCommandExecutionStartedCount, 1);
assert.strictEqual(unrelated.nativeEvidenceSubstitutionStartedCount, 0);
fs.writeFileSync(
  {json.dumps(str(stdout_path))},
  {json.dumps("\n".join(json.dumps(event) for event in substitution_events) + "\n")},
);
const substituted = runner.readGlassHiveRunToolAudit(
  runRecord,
  ['synthetic cobalt answer'],
);
assert.strictEqual(substituted.nativeEvidenceSubstitutionStartedCount, 1);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_provider_parity_matrix_uses_the_real_voice_gateway_and_diverse_synthetic_cases() -> None:
    assert PROVIDER_PARITY_SCRIPT.exists()
    script = f"""
const assert = require('assert');
const parity = require({json.dumps(str(PROVIDER_PARITY_SCRIPT))});
assert.deepStrictEqual(parity.MATRIX_CASES.map((item) => item.category), [
  'preference_constraint',
  'temporal_precision',
  'numeric_precision',
  'multilingual_paraphrase',
]);
assert.ok(parity.MATRIX_CASES.every((item) => item.seedCorpusPrompts.length > 0));
assert.ok(parity.MATRIX_CASES.every((item) => item.requiredResponseFragments.length > 0));
assert.strictEqual(
  new Set(parity.MATRIX_CASES.map((item) => JSON.stringify(item.requiredResponseFragments))).size,
  parity.MATRIX_CASES.length,
);
assert.ok(parity.runProviderParityMatrix.toString().includes('/api/viventium/voice/chat'));
assert.ok(parity.readVoiceStream.toString().includes('/api/viventium/voice/stream/'));
assert.ok(parity.runProviderParityMatrix.toString().includes('waitForConversationRecallCorpusRefresh'));
assert.ok(parity.runProviderParityMatrix.toString().includes("voiceMode: true"));
assert.ok(parity.runProviderParityMatrix.toString().includes("viventiumInputMode: 'voice_call'"));
assert.ok(parity.runProviderParityMatrix.toString().includes("viventiumSurface: 'voice'"));
assert.ok(parity.loadProviderParityEnv.toString().includes('runtime.env'));
assert.strictEqual(parity.visibleText([
  {{ event: 'on_message_delta', data: {{ delta: {{ content: [{{ type: 'text', text: 'Recovered ' }}] }} }} }},
  {{ event: 'on_message_delta', data: {{ delta: {{ content: [{{ type: 'text', text: 'evidence.' }}] }} }} }},
  {{ final: true }},
]), 'Recovered evidence.');
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_exact_model_voice_marker_validation_uses_raw_stream_text() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});

const events = [
  {{ event: 'on_message_delta', data: {{ delta: {{ content: [{{ type: 'text', text: '<soft>Hello' }}] }} }} }},
  {{ event: 'on_message_delta', data: {{ delta: {{ content: [{{ type: 'text', text: ' there.</soft>' }}] }} }} }},
  {{ final: true, responseMessage: {{ text: 'Hello there.' }} }},
];
assert.strictEqual(runner.extractRawStreamedText(events), '<soft>Hello there.</soft>');
const validation = runner.validateVoiceMarkerEvidence({{
  fixture: {{
    voiceOutput: {{ requested: true, provider: 'xai', markerExpectation: 'present' }},
  }},
}}, runner.extractRawStreamedText(events));
assert.deepStrictEqual(validation.failures, []);
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_exact_model_judge_uses_raw_evidence_for_sanitized_voice_markers() -> None:
    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const prompt = runner.buildJudgePrompt(
  {{
    id: 'voice-marker-boundary',
    familyId: 'feelings',
    fixture: {{
      voiceOutput: {{ requested: true, provider: 'xai', markerExpectation: 'present' }},
    }},
    rubric: ['uses a documented xAI speech control'],
  }},
  {{
    responseForJudge: 'The visible delivery is intentionally plain.',
    eventEvidenceForJudge: 'Voice marker evidence: providerMarkerCount=1; evidenceSource=raw_stream',
  }},
);
assert.ok(prompt.includes(
  'Judge marker presence, absence, and grammar from Voice marker evidence, not the sanitized response.',
));
assert.ok(prompt.includes(
  'Do not infer a missing marker from its deliberate sanitization.',
));
assert.ok(prompt.includes(
  'Structured Voice marker contract-validation fields are authoritative',
));
assert.ok(prompt.includes('The visible delivery is intentionally plain.'));
const nonVoicePrompt = runner.buildJudgePrompt(
  {{ id: 'plain', familyId: 'plain', rubric: ['answers directly'] }},
  {{ responseForJudge: 'Done.' }},
);
assert.ok(!nonVoicePrompt.includes('Voice marker note:'));
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_exact_model_judge_treats_complete_visible_response_as_absence_evidence() -> None:
    runner = EVAL_SCRIPT.read_text(encoding="utf-8")

    assert "The sanitized response is the complete visible response." in runner
    assert "its lack of forbidden content is evidence" in runner


def test_exact_model_judge_includes_declared_comparison_case_evidence() -> None:
    prompt_bank = json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))
    family = next(
        row for row in prompt_bank["families"] if row.get("id") == "feelings_embodiment_and_reaction"
    )
    high_case = next(
        row for row in family["cases"] if row.get("id") == "feelings_high_care_connection_owns_its_stance"
    )
    assert high_case["comparisonCaseId"] == "feelings_low_care_connection_owns_its_stance"

    script = f"""
const assert = require('assert');
const runner = require({json.dumps(str(EVAL_SCRIPT))});
const prompt = runner.buildJudgePrompt(
  {{ id: 'high', familyId: 'feelings', rubric: ['more relational than the comparison'] }},
  {{ responseForJudge: 'HIGH RESPONSE' }},
  {{ caseId: 'low', responseForJudge: 'LOW RESPONSE' }},
);
assert.ok(prompt.includes('Declared comparison case: low'));
assert.ok(prompt.includes('LOW RESPONSE'));
console.log('OK');
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
