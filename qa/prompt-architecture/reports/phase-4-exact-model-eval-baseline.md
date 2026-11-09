<!-- qa-evidence-exempt: Controlled prompt-registry completion artifact; full-view user-grade acceptance belongs in the owning feature run report. -->

# Prompt Registry Slice: Exact-Model Completion Baseline

Generated: 2026-11-05

## Status

- Status: blocked
- Live run requested: no
- Blocked reason: semantic_judge_required_but_disabled
- Prompt families: 26
- Prompt cases: 285
- Frozen continuity bank: continuity-recall-v1.1.0 / 987dfffc5021ba69 / 12 cases
- Runnable cases for this runner: 285
- Selected case limit: all (285)
- Post-case observation window ms: 20000
- Async follow-up grace after cortex completion ms: 30000
- Result count: 0
- Completed: 0
- Failed/blocked: 0
- Deterministic fixture contracts passed: 0
- Deterministic fixture contracts failed: 0
- Retried main turns: 0
- Total main-turn attempts: 0
- Visible-reply latency ms (mean/median/p95/max): not observed
- Full-case latency ms (mean/median/p95/max): not observed
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
- Surface metadata exercised: none

## Runtime Gate

- Runtime identity: pass
- Runtime reasons: none
- App title: Viventium
- Connected-account mode: enabled
- Prompt debug-local gate: disabled
- QA auth mode: not attempted

## Source Lineage

- Exact agent, runtime, API-base and source fingerprints remain private.
- Compiled LibreChat identity was not available for this blocked run.

## Results

| Case | Family | Surface | Status | Attempts | Semantic | Visible ms | Duration ms | Response hash | Error |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |

## Quality Gate Failures

- Duplicate non-silent response groups: none
- Unresolved async holds: none

## Notes

- Raw eval JSON and response previews are private-only.
- Public output stores sanitized aggregate counts, statuses and errors only. Private context and execution fingerprints remain outside the repository.
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
