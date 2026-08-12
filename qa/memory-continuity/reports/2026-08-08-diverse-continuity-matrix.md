# Prompt Registry Slice: Exact-Model Completion Baseline

Generated: 2026-08-08T23:06:55.255Z

## Status

- Status: partial_baseline
- Live run requested: yes
- Blocked reason: none
- Prompt families: 19
- Prompt cases: 154
- Agent hash: ed61775c0d925dba
- Runner hash: 54f34d4cce23e991
- Runnable cases for this runner: 9
- Selected case limit: all (9)
- Post-case observation window ms: 0
- Async follow-up grace after cortex completion ms: 0
- Result count: 9
- Completed: 9
- Failed/blocked: 0
- Retried main turns: 0
- Total main-turn attempts: 9
- Visible-reply latency ms (mean/median/p95/max): 19086.4/15423.0/51243.0/51243.0
- Full-case latency ms (mean/median/p95/max): 20164.3/16007.0/51699.0/51699.0
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
- Surface metadata exercised: voice, web

## Runtime Gate

- API base hash: 49e73564e9d328ef
- Runtime identity: pass
- Runtime reasons: none
- App title: Viventium
- Connected-account mode: enabled
- Prompt debug-local gate: disabled
- QA auth mode: local_jwt_fallback

## Source Hashes

- Agent source hash: f002f630fa7a4c63
- LibreChat source hash: 973ce91155c8383c
- Compiled LibreChat hash: e7b2fb5eaf3888c4

## Results

| Case | Family | Surface | Status | Attempts | Semantic | Visible ms | Duration ms | Response hash | Error |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |
| recall_matrix_relationship_role | memory_recall | web | completed | 1 | not run | 17569 | 17706 | 555cd687a08ed380 |  |
| recall_matrix_preference_constraint | memory_recall | voice | completed | 1 | not run | 15952 | 16007 | 453d4a0d6cbe5b2e |  |
| recall_matrix_project_status | memory_recall | web | completed | 1 | not run | 13121 | 13330 | cb88924e0415b761 |  |
| recall_matrix_correction_recency | memory_recall | web | completed | 1 | not run | 51243 | 51699 | e56fa97586eb0c74 |  |
| recall_matrix_temporal_precision | memory_recall | voice | completed | 1 | not run | 18980 | 19115 | 2d1f4ac766190f81 |  |
| recall_matrix_numeric_precision | memory_recall | voice | completed | 1 | not run | 14178 | 14227 | a200b27cd5bc8438 |  |
| recall_matrix_absent_evidence | memory_recall | web | completed | 1 | not run | 13649 | 13830 | d3da33c7c6c51dd1 |  |
| recall_matrix_distractor_disambiguation | memory_recall | web | completed | 1 | not run | 11663 | 11897 | 225b9f7a03a9fea7 |  |
| recall_matrix_multilingual_paraphrase | memory_recall | voice | completed | 1 | not run | 15423 | 23668 | 6618c710e7420b0c |  |

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

