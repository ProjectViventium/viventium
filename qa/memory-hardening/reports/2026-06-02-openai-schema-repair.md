<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-06-02 OpenAI/Codex Memory-Hardening Schema Repair

Overall status: **PASS for the repaired OpenAI/Codex schema path and nightly Workbench delivery
contract**.

This report covers the escaped `model_schema_error` from the nightly memory-hardening audit. It uses
public-safe synthetic prompts plus one real configured-account dry-run summarized only as redacted
counts/statuses. No real memories, conversations, transcript text, account identifiers, tokens,
local paths, provider request ids, or runtime dumps are included here.

## Root Cause

The memory hardener passed the same internal JSON Schema to every structured model route. That schema
was valid for local runtime validation, but it was not compatible with the Codex/OpenAI structured
output subset used by `codex exec --output-schema`.

Synthetic reproduction showed:

- A tiny probe schema passed on GPT-5.5.
- The real proposal schema failed before generation with `invalid_json_schema`.
- After making all object properties required, the next failure was unsupported `oneOf` in evidence
  items.

That explains the nightly symptom: the probe passed, the real OpenAI proposal failed with
`model_schema_error`, and Anthropic fallback completed the run.

## Fix

The hardener now normalizes schemas only at the Codex/OpenAI output-schema boundary:

- every declared object property is required in the provider-facing schema;
- `oneOf` is converted to `anyOf`;
- the internal proposal schema and runtime memory/evidence validator remain the source of truth after
  model output returns.

This is a transport compatibility fix, not a semantic workflow guardrail. The runtime still gives the
model the real hardening goal and evidence rules, lets the model reason over the corpus, and then
validates the returned proposal. The provider-facing schema only keeps the JSON channel parseable for
Codex/OpenAI.

The hardener prompt source of truth was updated so every operation includes a string `value` field,
using an empty string for `noop` or `delete` operations.

The full scheduled-shaped apply proof also exposed that the previous 15-minute model-call timeout
was too small for occasional large overnight workpacks: the first no-run-id `apply --scheduled`
timed out on OpenAI and fell back. The hardener default model timeout is now 30 minutes, which keeps
the same high-level AI task intact while allowing the configured model enough runtime to finish.

Additional QA found two adjacent issues that could keep the overnight review noisy:

- GlassHive MCP server instructions had drifted from the prompt registry source; the registry prompt
  and release assertion now match the runtime instruction text.
- Active user-level scheduler rows included orphaned owner IDs. Scheduler now treats structured
  `scheduler/chat user_not_found` as permanent owner orphaning: it preserves the failed ledger,
  records `orphaned_user_not_found`, deactivates the task, and does not retry it forever. Provider
  reconnect failures remain active/action-required because the user can repair account auth. A
  Claude review caught an early string-matching version of this gate; the final implementation uses
  structured HTTP error metadata (`path`, `status`, and `reason` / `failure_class`) instead.

## Evidence

| Check | Result |
| --- | --- |
| Current raw proposal schema against GPT-5.5 | Reproduced `invalid_json_schema` before the fix |
| Normalized proposal schema against GPT-5.5 | Passed; returned empty operations and summaries |
| Normalized transcript-summary schema against GPT-5.5 | Passed; returned required summary fields |
| Hardener `invokeModelWithFallback` synthetic GPT-5.5 call | Passed with one OpenAI attempt, no fallback |
| Hardener `invokeTranscriptSummaryModelWithFallback` synthetic GPT-5.5 call | Passed with one OpenAI attempt, no fallback |
| Real configured-account hardener dry-run | Passed on active runtime with OpenAI/GPT-5.5 at xhigh, one model attempt, zero attempt failures, zero fallback, three public-safe changed-key names, zero rejected operations, no transcript vector errors |
| Guarded apply of the repaired proposal | Passed; one user applied, three set operations by key name, maintenance applied, transcript-vector upload/delete counts zero, no fallback or vector error |
| Rollback of the guarded apply | Passed; one user restored, rollback snapshot present, summary records `rolled_back_at` / restored count, redacted log records `rollback_run` without raw memory values |
| First full scheduled-shaped apply under old timeout | Exposed `model_call_timeout` after one OpenAI attempt and fell back to Anthropic; apply was immediately rolled back |
| Timeout regression | Default hardener model timeout raised to 30 minutes and locked by `test_memory_hardening_model_timeout_matches_large_overnight_workload` |
| Full scheduled-shaped apply after timeout fix | Passed through fresh model generation and apply in one operation: OpenAI/GPT-5.5 selected, one attempt, zero failures, zero fallback, three set operations, no vector errors |
| Rollback of full scheduled-shaped apply | Passed; one user restored and `memory-harden status --json` exposes applied/rollback timestamps and restored count |
| Memory hardening status surface | Latest run reports apply success, OpenAI/GPT-5.5, applied timestamp, rollback timestamp, rollback summary filename, restored count, and user count |
| Active runtime checkout alignment | The active helper/live/runtime checkout resolves to the current repo checkout |
| Runtime restart | Local runtime restarted through the documented dev-runtime path; Scheduler health returned `ok` with the isolated runtime profile |
| Prompt Workbench browser proof | Real browser loaded Workbench, selected `Subconscious Deep Thought`, and showed the latest Jun 2 run completed plus the next Jun 3 run scheduled |
| Scheduler orphan cleanup | Three pre-fix active `viventium_agent` orphan rows with prior `user_not_found` failure were retired to inactive `orphaned_user_not_found`; active scheduler rows dropped from 11 to 8 and the built-in Workbench row stayed active/clean |
| Focused memory hardening regression | `43 passed` |
| Focused release regression | `174 passed` |
| Scheduled GlassHive contract regression | `12 passed`, `5 skipped` |
| Scheduler orphan regression | `18 passed` |
| Transcript eval bank | `12 passed`, `0 failed` |
| Claude review-only second opinion | Confirmed schema normalizer is the right minimal transport adapter; flagged apply/rollback as the remaining proof gap; guarded apply/rollback then closed that gap |

## Commands Run

- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_memory_hardening_contract.py -q`
- Synthetic `codex exec --model gpt-5.5 --output-schema ...` checks with public-safe prompts.
- Synthetic Node hardener checks through `invokeModelWithFallback` and
  `invokeTranscriptSummaryModelWithFallback`.
- `bin/viventium memory-harden dry-run --user-email <redacted operator email>`
- `bin/viventium memory-harden apply --run-id <redacted run id> --json`
- `bin/viventium memory-harden rollback --run-id <redacted run id> --json`
- `bin/viventium memory-harden apply --scheduled --json`
- `bin/viventium memory-harden rollback --run-id <redacted scheduled-apply run id> --json`
- `bin/viventium dev-runtime status`
- `bin/viventium memory-harden status --json`
- `bin/viventium dev-runtime activate-current --validate --restart --allow-protected-folder --allow-dirty-local-testing`
- `curl` scheduler `/health`
- `bin/viventium status`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_memory_hardening_contract.py tests/release/test_config_compiler.py tests/release/test_prompt_registry.py tests/release/test_qa_results_public_safety.py -q`
- `uv run --with pytest --with pyyaml --with croniter --with pydantic python -m pytest tests/release/test_scheduled_glasshive_prompts.py -q`
- `uv run --with pytest --with croniter --with pydantic python -m pytest viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/tests/test_scheduler.py -q`
- `node qa/meeting-transcript-memory/evals/run-evals.cjs`
- Playwright browser check against local Prompt Workbench; generated snapshots were removed after
  inspection and were not committed.

## Runtime Classification

The latest historical scheduled apply still records the pre-fix fallback, but the latest real
configured-account proof after the fix records the clean OpenAI/GPT-5.5 path on real runtime data:
one OpenAI attempt, no model failures, no fallback, no rejected operations, and no transcript vector
errors. A guarded apply of that proposal then wrote three key updates through the real memory apply
path, and rollback restored the affected private state. Persistent public-safe audit fields record
the apply count, rollback timestamp, rollback summary filename, restored-user count, and redacted
rollback log event without exposing raw memory values.

A successful scheduled run with zero eligible users is a healthy empty/skip result when the user has
intentionally disabled memory or no local users are eligible. It is not substantive memory work, but
it should not downgrade the nightly verdict unless eligibility is unknown, unexpectedly empty, or
mixed with provider/runtime/transcript/vector errors.

The final scheduled-shaped apply evidence is no longer a dry-run/run-id approximation: after the
timeout fix, `apply --scheduled` performed fresh model generation and apply in one operation and
selected OpenAI/GPT-5.5 directly with one attempt, zero failures, and zero fallback. The QA rollback
then restored the private state.

The status summary still distinguishes configured foundation-provider routing from per-user
Connected Accounts OAuth. That is intentional: route configuration is not proof that every signed-in
browser user has a valid provider token. Existing-user provider reconnect rows are account action,
not the OpenAI/Codex hardener schema failure fixed here.

The nested LibreChat fork changes are active in the restarted local runtime but remain dirty local
checkout changes until the normal nested-repo commit/pin/release process is run. That affects
durability across branch resets, not tonight's current local runtime behavior.

User-level schedules that need a connected-account reconnect remain active because they are
repairable account-action rows, not orphaned users and not the built-in nightly Workbench chain.
