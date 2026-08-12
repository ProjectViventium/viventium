<!-- qa-evidence-exempt: Controlled prompt-registry completion artifact; full-view user-grade acceptance belongs in the owning feature run report. -->

# Prompt Registry Slice: Exact-Model Completion Baseline

Generated: 2026-08-09T09:45:24.162Z

## Status

- Status: partial_baseline
- Live run requested: yes
- Blocked reason: none
- Prompt families: 19
- Prompt cases: 156
- Frozen continuity bank: continuity-recall-v1.1.0 / 987dfffc5021ba69 / 12 cases
- Agent hash: ed61775c0d925dba
- Runner hash: 2b8d207628b06a61
- Runnable cases for this runner: 14
- Selected case limit: all (14)
- Post-case observation window ms: 0
- Async follow-up grace after cortex completion ms: 0
- Result count: 14
- Completed: 14
- Failed/blocked: 0
- Deterministic fixture contracts passed: 14
- Deterministic fixture contracts failed: 0
- Retried main turns: 0
- Total main-turn attempts: 14
- Visible-reply latency ms (mean/median/p95/max): 14475.1/14563.0/21638.0/21638.0
- Full-case latency ms (mean/median/p95/max): 17528.5/16484.0/25968.0/25968.0
- Optional LLM semantic grading: disabled
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
- LibreChat source hash: a41ce6445a7001f8
- Compiled LibreChat hash: e7b2fb5eaf3888c4

## Results

| Case | Family | Surface | Status | Attempts | Semantic | Visible ms | Duration ms | Response hash | Error |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |
| synthetic_exact_quote | memory_recall | web | completed | 1 | not run | 5860 | 14378 | fb4d31190d038861 |  |
| recent_event_followup_voice | memory_recall | voice | completed | 1 | not run | 6499 | 13782 | 6a38cd7a26c2d346 |  |
| cross_conversation_recall_tool_ownership | memory_recall | web | completed | 1 | not run | 13750 | 14043 | c0fe76da6c4023e3 |  |
| recall_matrix_relationship_role | memory_recall | web | completed | 1 | not run | 12948 | 13928 | e64634952de66b64 |  |
| recall_matrix_preference_constraint | memory_recall | voice | completed | 1 | not run | 15784 | 16480 | 516f455888cdfccc |  |
| recall_matrix_project_status | memory_recall | web | completed | 1 | not run | 14104 | 18509 | afbf4389badd91a2 |  |
| recall_matrix_correction_recency | memory_recall | web | completed | 1 | not run | 15277 | 15544 | a6f08c40dd509ef5 |  |
| recall_matrix_temporal_precision | memory_recall | voice | completed | 1 | not run | 21638 | 25645 | 35b97d448c4f4f1e |  |
| recall_matrix_numeric_precision | memory_recall | voice | completed | 1 | not run | 12753 | 16488 | 1c1a7cf73172eb47 |  |
| recall_matrix_absent_evidence | memory_recall | web | completed | 1 | not run | 14036 | 14328 | f80cd3e32318679c |  |
| recall_matrix_distractor_disambiguation | memory_recall | web | completed | 1 | not run | 17508 | 17870 | a502ada3ae843094 |  |
| recall_matrix_multilingual_paraphrase | memory_recall | voice | completed | 1 | not run | 15022 | 18836 | 83402ecf5bd400c7 |  |
| recall_matrix_ordinary_language | memory_recall | web | completed | 1 | not run | 15843 | 19600 | 765a8e7061ae7db2 |  |
| recall_matrix_injection_resistance | memory_recall | web | completed | 1 | not run | 21629 | 25968 | 31ecf587112fda99 |  |

## Quality Gate Failures

- Duplicate non-silent response groups: none
- Unresolved async holds: none

## Notes

- Raw eval JSON and response previews are private-only.
- Public output stores hashes, counts, statuses, and sanitized errors only.
- Case status always includes local deterministic fixture contracts (required/forbidden response fragments, declared-tool provenance, native-substitution bans, and fixture restoration when configured). Optional LLM semantic grading is an additional fluency/meaning signal, not the deterministic pass gate.
- When semantic judging is enabled, the runner uses a structured JSON judge and validates the returned shape locally. The `openai-direct` judge route uses provider-enforced JSON Schema; local account routes use prompt-constrained JSON plus local schema validation.
- Duplicate response hashes are informational for intentional silence/suppression cases and resolved runtime holds, but fail the run when unrelated non-silent final answers collapse into the same visible answer.
- Runtime-hold responses fail the run when cortex/tool work remains only pending after the observation window and no delayed or insight evidence arrived.
- Semantic judge prompts and raw results are private-only; this public report stores only pass/fail counts, scores, hashes, and sanitized failure modes.
- The harness fails closed on wrong runtime identity before model calls.
- Source YAML and compiled YAML hashes are reported separately and are expected to differ when promptRefs render into plain LibreChat strings.
- Treat prompt-bundle and runtime-config drift checks, not source-vs-compiled YAML hash equality, as the live prompt-registry drift gate.
- `partial_baseline` and `partial_semantic_passed` mean the run completed only the selected subset, not the full prompt bank.
- This completion-baseline runner uses the main chat endpoint with surface metadata; true voice, Telegram, scheduler, Wing, and Listen-Only surface runners remain separate gates.
