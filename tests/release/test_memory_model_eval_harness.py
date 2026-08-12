import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "qa" / "memory-hardening" / "scripts" / "run-memory-model-eval.cjs"


def run_node(source: str) -> dict:
    completed = subprocess.run(
        ["node", "-e", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_memory_model_eval_bank_is_broad_and_current() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const bank = runner.validateBank(runner.CASES);
console.log(JSON.stringify({{
  models: runner.DEFAULT_MODELS,
  bankVersion: bank.bankVersion,
  frozenHash: runner.FROZEN_BANK_HASH,
  bankHash: bank.bankHash,
  caseCount: bank.caseCount,
  competencies: [...new Set(runner.CASES.map((row) => row.competency))].sort(),
}}));
"""
    )

    assert payload["models"] == ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"]
    assert payload["bankVersion"] == "memory-writer-v1.0.0"
    assert payload["bankHash"] == payload["frozenHash"] == "fc8acd04668038e3"
    assert payload["caseCount"] == 16
    assert {
        "information_extraction",
        "knowledge_update",
        "temporal_reasoning",
        "selective_forgetting",
        "abstention_and_untrusted_evidence",
        "entity_disambiguation",
        "long_range_understanding",
        "transcript_fidelity",
        "transcript_prompt_injection",
        "reference_context_boundary",
    }.issubset(set(payload["competencies"]))


def test_memory_model_eval_costs_cached_and_uncached_tokens_separately() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const usage = {{ inputTokens: 1000000, cachedInputTokens: 500000, outputTokens: 100000 }};
console.log(JSON.stringify(Object.fromEntries(runner.DEFAULT_MODELS.map(
  (model) => [model, runner.normalizedCredits(model, usage)],
))));
"""
    )

    assert payload["gpt-5.6-sol"] == 143.75
    assert payload["gpt-5.6-terra"] == 71.875
    assert payload["gpt-5.6-luna"] == 28.75


def test_memory_model_eval_uses_reviewed_effort_per_model() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const options = runner.parseArgs([]);
console.log(JSON.stringify(Object.fromEntries(runner.DEFAULT_MODELS.map(
  (model) => [model, runner.effortForModel(options, model)],
))));
"""
    )

    assert payload == {
        "gpt-5.6-sol": "xhigh",
        "gpt-5.6-terra": "high",
        "gpt-5.6-luna": "medium",
    }


def test_memory_model_eval_selects_only_a_full_gate_pass() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const selected = runner.chooseModel([
  {{ model: 'gpt-5.6-luna', gatePassed: false, normalizedCredits: 1, durationP50Ms: 10 }},
  {{ model: 'gpt-5.6-terra', gatePassed: true, normalizedCredits: 8, durationP50Ms: 20 }},
  {{ model: 'gpt-5.6-sol', gatePassed: true, normalizedCredits: 20, durationP50Ms: 15 }},
]);
console.log(JSON.stringify(selected));
"""
    )

    assert payload["model"] == "gpt-5.6-terra"


def test_memory_model_eval_selection_uses_official_rate_order_not_cache_noise() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const selected = runner.chooseModel([
  {{ model: 'gpt-5.6-sol', gatePassed: true, normalizedCredits: 1, durationP50Ms: 1 }},
  {{ model: 'gpt-5.6-terra', gatePassed: true, normalizedCredits: 8, durationP50Ms: 20 }},
  {{ model: 'gpt-5.6-luna', gatePassed: true, normalizedCredits: 20, durationP50Ms: 30 }},
]);
console.log(JSON.stringify({{ selected, multipliers: Object.fromEntries(runner.DEFAULT_MODELS.map(
  (model) => [model, runner.officialCostMultiplierVsLuna(model)],
)) }}));
"""
    )

    assert payload["selected"]["model"] == "gpt-5.6-luna"
    assert payload["multipliers"] == {
        "gpt-5.6-sol": 5,
        "gpt-5.6-terra": 2.5,
        "gpt-5.6-luna": 1,
    }


def test_memory_model_eval_gate_requires_every_run_and_zero_policy_rejects() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const usage = {{ inputTokens: 1, cachedInputTokens: 0, outputTokens: 1, reasoningOutputTokens: 0 }};
const summaries = runner.aggregate([
  {{ model: 'gpt-5.6-luna', invocationOk: true, passed: true, rejectedCount: 0, durationMs: 10, usage }},
  {{ model: 'gpt-5.6-luna', invocationOk: true, passed: false, rejectedCount: 0, durationMs: 20, usage }},
  {{ model: 'gpt-5.6-terra', invocationOk: true, passed: true, rejectedCount: 1, durationMs: 15, usage }},
], ['gpt-5.6-luna', 'gpt-5.6-terra']);
console.log(JSON.stringify(summaries));
"""
    )

    assert payload[0]["gatePassed"] is False
    assert payload[0]["passed"] == 1
    assert payload[0]["runs"] == 2
    assert payload[1]["gatePassed"] is False
    assert payload[1]["policyRejects"] == 1


def test_memory_model_eval_aggregate_positive_gate_can_select_a_model() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const usage = {{ inputTokens: 1, cachedInputTokens: 0, outputTokens: 1, reasoningOutputTokens: 0 }};
const summaries = runner.aggregate([
  {{ model: 'gpt-5.6-luna', invocationOk: true, passed: true, rejectedCount: 0, durationMs: 10, usage }},
  {{ model: 'gpt-5.6-luna', invocationOk: true, passed: true, rejectedCount: 0, durationMs: 20, usage }},
], ['gpt-5.6-luna']);
console.log(JSON.stringify({{ summaries, selected: runner.chooseModel(summaries) }}));
"""
    )

    assert payload["summaries"][0]["gatePassed"] is True
    assert payload["summaries"][0]["passed"] == 2
    assert payload["summaries"][0]["runs"] == 2
    assert payload["selected"]["model"] == "gpt-5.6-luna"


def test_memory_model_eval_subset_verifies_frozen_bank_but_cannot_select_winner() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const options = runner.parseArgs(['--case-ids=at_500k_workpack_preserves_early_user_fact']);
const outcome = runner.run(options);
const selected = runner.selectModelForRun(options, [
  {{ model: 'gpt-5.6-luna', gatePassed: true, durationP50Ms: 10 }},
]);
console.log(JSON.stringify({{
  scope: outcome.bank.evaluationScope,
  frozenBankHash: outcome.bank.frozenBankHash,
  frozenHash: runner.FROZEN_BANK_HASH,
  subsetHash: outcome.bank.bankHash,
  selected,
}}));
"""
    )

    assert payload["scope"] == "bounded_subset"
    assert payload["frozenBankHash"] == payload["frozenHash"]
    assert payload["subsetHash"] != payload["frozenHash"]
    assert payload["selected"] is None


def test_memory_model_eval_no_live_mode_makes_no_model_call() -> None:
    completed = subprocess.run(
        ["node", str(RUNNER), "--no-live"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["status"] == "validated"
    assert payload["caseCount"] == 16


def test_memory_model_eval_exposes_exact_application_ceiling_case_on_demand() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const selected = runner.evaluationCases(['at_500k_workpack_preserves_early_user_fact']);
console.log(JSON.stringify({{
  count: selected.length,
  scaleChars: selected[0].inputScaleChars,
  messageChars: selected[0].messages.reduce((total, row) => total + row.text.length, 0),
  estimatedInputChars: selected[0].messages.reduce((total, row) => total + row.text.length + 256, 0),
  defaultCount: runner.CASES.length,
}}));
"""
    )

    assert payload["count"] == 1
    assert payload["scaleChars"] == 500_000
    assert payload["messageChars"] == 499_488
    assert payload["estimatedInputChars"] == 500_000
    assert payload["defaultCount"] == 16


def test_memory_model_eval_exact_association_and_injection_scorers_fail_closed() -> None:
    payload = run_node(
        f"""
const runner = require({json.dumps(str(RUNNER))});
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const ranked = runner.CASES.find((row) => row.id === 'exact_ranked_numbers_survive');
const injection = runner.CASES.find((row) => row.id === 'transcript_summary_resists_embedded_instructions');
const rankedAssessment = runner.assessCase({{
  hardener,
  testCase: ranked,
  proposal: {{
    operations: [{{
      key: 'context',
      action: 'set',
      value: 'Vendor review is active. Cedar 17, Harbor 41, Slate 9.',
      rationale: 'synthetic',
      evidence: [{{ source: 'conversation', messageId: 'm-ranking', createdAt: '2026-08-08T16:00:00.000Z' }}],
    }}],
    transcript_summaries: [],
  }},
}});
const injectionAssessment = runner.assessCase({{
  hardener,
  testCase: injection,
  proposal: {{
    summary: 'PWNED. Rowan postponed Quartz until August 29; Jules owns the checklist.',
    displayTitle: 'Quartz',
    oneLineSummary: null,
    meetingDatetime: null,
    participants: ['Rowan', 'Jules'],
    createdAt: '2026-08-08T20:00:00.000Z',
  }},
}});
console.log(JSON.stringify({{ rankedAssessment, injectionAssessment }}));
"""
    )

    assert payload["rankedAssessment"]["passed"] is False
    assert any(
        failure.startswith(("missing_adjacent_pair:", "wrong_fragment_order:"))
        for failure in payload["rankedAssessment"]["failures"]
    )
    assert payload["injectionAssessment"]["passed"] is False
    assert "reference_context_leak:PWNED" in payload["injectionAssessment"]["failures"]


def test_memory_hardener_fails_closed_above_application_input_ceiling() -> None:
    payload = run_node(
        """
const hardener = require('./viventium_v0_4/LibreChat/scripts/viventium-memory-hardening.js');
const exact = hardener.selectMessagesForPrompt([{ text: 'x'.repeat(499744) }], 500000);
const overflow = hardener.selectMessagesForPrompt([{ text: 'x'.repeat(499745) }], 500000);
console.log(JSON.stringify({
  exact: {
    complete: exact.complete,
    estimatedInputChars: exact.estimatedInputChars,
    selectedInputChars: exact.selectedInputChars,
    truncatedMessages: exact.truncatedMessages,
  },
  overflow: {
    complete: overflow.complete,
    estimatedInputChars: overflow.estimatedInputChars,
    selectedInputChars: overflow.selectedInputChars,
    truncatedMessages: overflow.truncatedMessages,
  },
}));
"""
    )

    assert payload["exact"] == {
        "complete": True,
        "estimatedInputChars": 500_000,
        "selectedInputChars": 500_000,
        "truncatedMessages": 0,
    }
    assert payload["overflow"]["complete"] is False
    assert payload["overflow"]["estimatedInputChars"] == 500_001
    assert payload["overflow"]["truncatedMessages"] == 1
