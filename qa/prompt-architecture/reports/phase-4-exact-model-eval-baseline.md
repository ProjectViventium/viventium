# Prompt Registry Slice: Exact-Model Completion Baseline

<!-- qa-evidence-exempt: Machine-generated blocked exact-model baseline; no real user-path QA execution occurred. -->

Generated: 2026-08-03T15:58:47.271Z

## Status

- Status: blocked
- Live run requested: no
- Blocked reason: live_eval_disabled_set_VIVENTIUM_RUN_EXACT_MODEL_EVALS_or_pass_--run-live
- Prompt families: 19
- Prompt cases: 139
- Agent hash: ed61775c0d925dba
- Runner hash: d171fa0f40eb67fa
- Runnable cases for this runner: 139
- Selected case limit: all (139)
- Post-case observation window ms: 20000
- Async follow-up grace after cortex completion ms: 30000
- Result count: 0
- Completed: 0
- Failed/blocked: 0
- Retried main turns: 0
- Total main-turn attempts: 0
- Behavioral grading: disabled
- Semantic judged: 0
- Semantic passed: 0
- Semantic failed: 0
- Semantic judge unavailable: 0
- Semantic judge blocked reason: none
- Judge model hash: not used
- Duplicate response hashes: 0
- Duplicate response quality failures: 0
- Unresolved async quality failures: 0
- Surfaces in bank: listen_only, memory_hardening, scheduler, telegram, transcript_ingest, voice, web, wing
- Surface metadata exercised: none

## Runtime Gate

- API base hash: 49e73564e9d328ef
- Runtime identity: pass
- Runtime reasons: none
- App title: Viventium
- Connected-account mode: enabled
- Prompt debug-local gate: disabled
- QA auth mode: not attempted

## Source Hashes

- Agent source hash: b1bc9bc084ffbfb3
- LibreChat source hash: 9a50a97ded91fb68
- Compiled LibreChat hash: missing

## Results

| Case | Family | Surface | Status | Attempts | Semantic | Duration ms | Response hash | Error |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- |

## Quality Gate Failures

- Duplicate non-silent response groups: none
- Unresolved async holds: none

## Notes

- Raw eval JSON and response previews are private-only.
- Public output stores hashes, counts, statuses, and sanitized errors only.
- When semantic judging is enabled, the runner uses a structured JSON judge and validates the returned shape locally. The `openai-direct` judge route uses provider-enforced JSON Schema; local account routes use prompt-constrained JSON plus local schema validation.
- Duplicate response hashes are informational for intentional silence/suppression cases and resolved runtime holds, but fail the run when unrelated non-silent final answers collapse into the same visible answer.
- Runtime-hold responses fail the run when cortex/tool work remains only pending after the observation window and no delayed or insight evidence arrived.
- Semantic judge prompts and raw results are private-only; this public report stores only pass/fail counts, scores, hashes, and sanitized failure modes.
- The harness fails closed on wrong runtime identity before model calls.
- Source YAML and compiled YAML hashes are reported separately and are expected to differ when promptRefs render into plain LibreChat strings.
- Treat prompt-bundle and runtime-config drift checks, not source-vs-compiled YAML hash equality, as the live prompt-registry drift gate.
- `partial_baseline` and `partial_semantic_passed` mean the run completed only the selected subset, not the full prompt bank.
- This completion-baseline runner uses the main chat endpoint with surface metadata; true voice, Telegram, scheduler, Wing, and Listen-Only surface runners remain separate gates.
