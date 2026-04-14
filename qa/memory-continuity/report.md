# Memory Continuity QA Report

## Date

- 2026-04-08
- 2026-04-09
- 2026-04-14

## Build Under Test

- Parent repo working tree on 2026-04-09
- Nested LibreChat working tree on 2026-04-09
- Public-safe analysis of generated runtime config, launcher/runtime behavior, live saved-memory
  state, and targeted test suites
- Remote follow-up on 2026-04-14 against the supported upgrade path plus local runtime-bundle
  verification

## Verification Gate Claimed

- `Local development implementation gate`
- Meaning:
  - root cause was traced with code and runtime evidence
  - the owned runtime/compiler fixes are now implemented
  - owning automated suites for the affected continuity surfaces pass
  - remaining work is explicitly narrowed to broader acceptance/release gates
- Not yet claimed:
  - `cross-surface landing gate`
  - `public release gate`

## Steps Executed

1. Reviewed the owning docs:
   - `docs/requirements_and_learnings/01_Key_Principles.md`
   - `docs/requirements_and_learnings/20_Memory_System.md`
   - `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`
   - `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
   - `docs/02_ARCHITECTURE_OVERVIEW.md`
   - `docs/03_SYSTEMS_MAP.md`
2. Implemented the owned fixes:
   - shared runtime provider normalization for compiler-emitted memory providers
   - compiler-owned retrieval embeddings env contract
   - install/start honesty for Ollama-backed recall
   - bounded older-user-context input for long memory writes
   - explicit partial-forgetting contract for the saved-memory writer
   - repeated-separator corruption cleanup at shared memory write/maintenance boundaries
   - deterministic staleness maintenance for expired temporal keys and long-idle active drafts
   - draft-archive preservation across later maintenance passes
   - dedicated recall-availability test coverage
3. Re-checked the live local failure evidence for the scheduled stale-output incident using public-safe
   log and database inspection.
4. Restarted the local runtime onto the generated configuration with:
   - `bin/viventium start --restart --modern-playground`
5. Verified after restart that:
   - generated runtime memory config now points at `anthropic / claude-sonnet-4-6`
   - recent helper logs no longer show `Provider openai not supported`
   - the saved-memory product path removed the stale forgotten references from the affected keys
     without manual Mongo edits
6. Updated the owning requirements and QA artifacts to match the implemented product truth.
7. Ran targeted automated tests.
8. Attempted the required review-only Claude second-opinion pass.
   - Result: no usable review output in this environment
   - Detail: one file-reading review call hung without returning, one constrained summary-only
     review hit a hard timeout, and an earlier no-tools fallback failed immediately with local-auth
     state (`Not logged in`)
9. On 2026-04-14, reran the remote connected-account browser QA after the supported upgrade path.
10. Captured the live memory-writer request/response shape on the upgraded remote machine.
11. Compared the owning source file against the local compiled `packages/api/dist` bundle that
    runtime actually imports.
12. Added bundle-alignment regression coverage so the public release path checks the rebuild
    contract and built bundle path, not only the source file.
13. On 2026-04-14, traced a deeper connected-account failure where the memory run returned
    `status: "completed"` but `output: []` on the bridged non-stream Codex response.
14. Verified with remote direct-processor evidence that the missing durable write was caused before
    Mongo storage, even when the upstream request succeeded.
15. Implemented the owning fix in the OpenAI Codex SSE-to-JSON adapter so streamed
    `response.output_item.*` function-call events are reconstructed into non-stream `output`.
16. Rebuilt the nested `packages/api/dist` bundle, deployed it to the remote runtime, restarted the
    stack, and reran the direct and browser QA flow.
17. Reran the supported remote `bin/viventium upgrade --restart` path after publish.
18. Verified that the remote install still carried a dirty nested LibreChat checkout from an earlier
    local hotfix, which blocked the pinned nested ref from landing even though parent upgrade
    succeeded.
19. Hardened the public upgrade path so dirty selected managed components now fail closed instead of
    silently compiling and restarting on stale nested code.
20. Hardened `doctor.sh` so it reports tolerated dirty/vendored checkout validation honestly
    instead of always claiming the selected components are on pinned refs.

## Automated Checks Executed

### Release / installer / compiler surfaces

- `python3 -m pytest tests/release/test_config_compiler.py tests/release/test_wizard.py tests/release/test_preflight.py tests/release/test_doctor_sh.py tests/release/test_install_summary.py tests/release/test_librechat_client_defaults.py -q`
  - Result: `105 passed`

### Shared data-provider + runtime resolver surfaces

- `cd viventium_v0_4/LibreChat/packages/data-provider && npx jest --runInBand specs/utils.spec.ts --no-cache`
  - Result: `21 passed, 1 skipped`
- `cd viventium_v0_4/LibreChat/packages/data-provider && npm run build`
  - Result: passed
- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/endpoints/config.spec.ts src/agents/__tests__/conversationRecallAvailability.test.ts src/agents/__tests__/memory.test.ts --no-cache`
  - Result: `33 passed`
- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/endpoints/openai/config.spec.ts src/endpoints/openai/config.dist.spec.ts src/agents/__tests__/memory.test.ts --no-cache`
  - Result: `114 passed`
- `cd viventium_v0_4/LibreChat/packages/api && npx jest --runInBand src/memory/policy.spec.ts src/agents/__tests__/memory.test.ts src/agents/memory.spec.ts --no-cache`
  - Result: `48 passed`
- `cd viventium_v0_4/LibreChat/packages/api && npx jest --config jest.config.mjs --runInBand src/endpoints/openai/config.spec.ts src/agents/memory.spec.ts src/agents/__tests__/memory.test.ts --no-cache`
  - Result: `134 passed`

### Backend/runtime continuity surfaces

- `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/controllers/agents/client.test.js server/services/viventium/__tests__/conversationRecallRuntimeContext.spec.js server/services/viventium/__tests__/conversationRecallService.spec.js test/app/clients/tools/util/modelFacingToolOutput.test.js --no-cache`
  - Result: `124 passed`
- `cd viventium_v0_4/LibreChat/api && npx jest --runInBand server/controllers/agents/client.test.js server/routes/__tests__/memories.write.spec.js --no-cache`
  - Result: `78 passed`
- `bash -n scripts/viventium/doctor.sh && bash -n viventium_v0_4/viventium-librechat-start.sh`
  - Result: passed
- `python3 - <<'PY' ... yaml.safe_load('viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml') ... PY`
  - Result: `YAML_OK`
- `bin/viventium start --restart --modern-playground`
  - Result: local stack restarted onto the current generated runtime

### Broader release smoke

- `python3 -m pytest tests/release/ -q`
  - Result: `216 passed, 6 failed`
  - Result detail: current failures are outside the memory/recall surfaces changed in this pass
    and block a broader release-gate claim.

### Unrelated suite note

- Running the full `packages/api/src/agents/__tests__/initialize.test.ts` file also surfaced two
  unrelated `maxContextTokens` assertion failures.
- These are outside the continuity issue under investigation and were not used to judge the
  recall/memory findings.
- The broader release suite still has unrelated failures in:
  - `tests/release/test_background_agent_governance_contract.py`
  - `tests/release/test_local_web_search_compose.py`
  - `tests/release/test_native_stack_helpers.py`
  - `tests/release/test_voice_playground_dispatch_contract.py`

## Edge-Case Matrix Reviewed

1. Saved memory enabled, recall stale.
   - Expected: no false confidence from vector recall; degraded lexical recall should recover recent
     corrections when possible.
2. Saved memory disabled, recall healthy.
   - Expected: recent/historical continuity can still work without silently creating durable notes.
3. Saved memory writer init fails before the prompt runs.
   - Expected: treat as runtime failure; do not blame the memory prompt for not updating.
4. New correction occurs early in a long conversation.
   - Expected: bounded older-user-context recovery preserves it without expanding the current chat
     window into a giant raw prompt.
5. Short post-message indexing lag.
   - Expected: freshness gate refuses stale vector corpus; degraded lexical recall covers the gap.
6. Repeated transient upload failures pause proactive sync.
   - Expected: logs and QA classify this as indexing outage, not absence of user history.
7. Scheduler/task tools available during catch-up prompts.
   - Expected: schedule summaries stay useful without leaking stale generated prose into continuity.
8. Cross-surface request path differences.
   - Expected: Telegram, Scheduler, Web UI, and Voice all respect the same provider/runtime
     contracts for memory and recall.

## Findings

### 1. The scheduled stale-output incident was primarily explained by stale saved memory

- The scheduled Telegram run on April 9, 2026 surfaced explicitly forgotten references from saved
  memory.
- Public-safe log inspection showed the same run also had degraded file/recall retrieval, but the
  stale `context` / `drafts` memory keys alone were enough to explain the bad output.
- Public-safe database inspection confirmed that stale forgotten references still existed in the
  saved-memory store at the time of the scheduled run.

### 2. The saved-memory writer had a separate live failure before restart, and restart onto the fixed runtime resolved that init contract bug

- The same log set shows repeated:
  - `Error initializing memory writer Provider openai not supported`
- Before restart, the generated runtime used by the live helper emitted:
  - `memory.agent.provider: openai`
  - `memory.agent.model: gpt-5.4`
- Shared runtime provider normalization is now implemented so compiler-emitted canonical aliases are
  accepted at initialization instead of requiring a different runtime-only token.
- Therefore the live failure was a provider-normalization/runtime-init contract bug, not evidence
  that the memory prompt itself chose not to update memory.
- After local restart onto the fixed generated runtime, public-safe inspection confirmed:
  - `memory.agent.provider: anthropic`
  - `memory.agent.model: claude-sonnet-4-6`
  - no fresh unsupported-provider init failures in the recent helper log window

### 2.1 OpenAI Codex connected-account memory runs also needed request-shape normalization

- A later remote-machine repro showed a different saved-memory failure class from the earlier
  provider-init issue:
  - connected-account lookup succeeded
  - the memory run still failed with live `400` responses from the Codex-backed Responses route
- Public-safe request/response inspection isolated the contract mismatch:
  - first repro without the Codex adapter failed with `Instructions are required`
  - the actual memory path then showed `System messages are not allowed`
- The implemented product fix keeps Codex instruction text in top-level `instructions` and strips
  `system` / `developer` messages out of Responses `input` for that route.
- Therefore connected-account memory acceptance must prove both:
  - writer initialization/auth succeeds
  - the live Responses request shape is accepted by the connected-account backend

### 2.2 A source-only Codex fix did not repair the supported upgrade path

- The April 14, 2026 remote follow-up showed that the supported upgrade path alone still did not
  repair durable memory on the test machine:
  - chat login succeeded
  - a memory-worthy prompt got an in-thread acknowledgement
  - the `Memories` panel stayed empty
  - the saved-memory store remained at `0` entries for that user
- Live remote debug then proved the deeper release bug:
  - the request reached the Codex Responses route
  - the Codex adapter was active and normalized `store`, `user`, `stream`, and top-level
    `instructions`
  - the provider still rejected the request with `400 "System messages are not allowed"`
- Comparing the owning source file against the local runtime bundle isolated the reason:
  - `packages/api/src/endpoints/openai/config.ts` contained the new system/developer stripping
    logic
  - `packages/api/dist/index.js`, which the runtime actually imports, still carried the older
    adapter without that stripping logic
- Therefore the prior release fix was incomplete as a product delivery:
  - source/tests were updated
  - the supported upgrade/start path could still leave the older local compiled runtime artifact in
    place
- The corrected release contract now requires:
  - launcher/upgrade rebuild detection that compares package source trees against local `dist`
    markers instead of watching only `package.json` / `package-lock.json`
  - regression coverage that exercises the built bundle directly
  - a public release check from the parent repo side that verifies the launcher rebuild contract,
    plus nested repo regression coverage that exercises the built bundle path directly

### 2.3 Non-stream Codex adaptation was still dropping streamed tool calls after successful runs

- After the shipped bundle alignment fix, the remote machine still showed a deeper saved-memory
  failure class:
  - the memory-writer request could return HTTP `200`
  - the response status could be `completed`
  - the bridged non-stream JSON still exposed `output: []`
  - the memory processor then returned no tool artifacts and wrote nothing durable
- Direct remote processor invocation proved this was not a chat-controller or Mongo bug:
  - invoking the same memory processor against the live DB still returned no memory rows when
    `output` was empty
- The owning root cause was in the Codex bridge:
  - non-stream callers are adapted from streamed SSE
  - the old adapter returned only the sparse `response.completed` payload
  - the actual `function_call` item lived in streamed `response.output_item.*` and
    `response.function_call_arguments.*` events
- Therefore the fix belongs in `packages/api/src/endpoints/openai/config.ts`, not in memory
  policy, Mongo storage, or user-level prompts.

### 2.4 Remote connected-account memory now works end to end after the SSE output reconstruction fix

- After rebuilding and deploying the corrected bundle to the remote runtime:
  - direct debug showed the bridged non-stream Codex response now preserved a completed
    `function_call` item for `apply_memory_changes`
  - direct processor invocation against the live DB wrote a durable memory row for the user
  - the real browser flow created a visible entry in the `Memories` panel
  - database inspection showed `count: 1` with the stored lucky-number memory
  - a brand-new conversation then recovered the stored value and answered `227`
- One retrieval attempt hit a transient upstream model error before succeeding on regenerate.
- This remaining transient was a provider/runtime availability issue on the main response path, not
  a saved-memory write-path failure:
  - the saved memory had already been written and was visible in both UI and DB
  - the successful regenerate recovered the stored value from the next conversation

### 3. Forgetting is now explicitly defined as a cross-key rewrite contract

- Saved-memory instructions now explicitly define partial forgetting as:
  - scan all keys,
  - rewrite every affected key with `set_memory`,
  - remove only the requested detail,
  - preserve unrelated history and signals.
- Shared default instructions and tool descriptions now also state that `delete_memory` is for
  whole-key removal only.
- This closes the prior ambiguity where forgetting could be misread as a whole-key delete shortcut.

### 4. Repeated semicolon corruption is now cleaned at shared memory boundaries

- Public-safe inspection of the saved-memory store found repeated semicolon-run corruption across
  multiple keys.
- The best-supported explanation is repeated model rewrite/compaction cycles around semicolon-style
  list separators; this was inferred from the compaction path and observed store state rather than
  from a raw-message replay trace.
- The product fix is therefore placed at the shared memory boundaries:
  - fresh writes collapse repeated semicolon runs before storage
  - deterministic maintenance also cleans existing corruption already in the store
- Public-safe post-restart inspection showed the affected saved-memory keys no longer contained
  repeated semicolon runs (`max run = 1`).
- Focused policy tests now cover this behavior.

### 5. Temporal memory now self-heals without waiting for token pressure

- Before this pass, expired `context`, stale `working`, and long-idle active `drafts` only got
  rewritten if some other maintenance trigger happened to fire.
- Maintenance now triggers on temporal staleness itself, refreshes `context` / `working` markers to
  current dates, archives long-idle active draft threads, and preserves previously archived draft
  history across later compaction runs.

### 6. Automated coverage now directly covers the implemented continuity fixes

- Recall health/freshness and degraded lexical fallback have targeted coverage.
- Compiler-emitted memory provider alias acceptance now has direct test coverage.
- Memory writer older-user-context behavior now has direct controller coverage.
- The built `packages/api/dist` bundle now has direct regression coverage for the Codex
  instruction-normalization path instead of relying only on the source-file test path.
- Memory forgetting/integrity behavior now has direct policy coverage for:
  - separator cleanup on write
  - expired temporal key refresh
  - long-idle draft archiving with archive preservation
- Release/installer surfaces now have targeted coverage for retrieval embeddings defaults and
  prerequisite reporting.

### 7. The live saved-memory store is now clean on the verified keys after the product path ran

- Public-safe database inspection before restart showed stale forgotten references still present in
  the affected saved-memory keys.
- Public-safe database inspection after restart showed those stale forgotten references no longer
  present in the same keys.
- This cleanup happened through the product maintenance/write path after restart, not through manual
  database edits.

### 8. There was also a real recall indexing / retrieval issue, and it remains distinct from saved memory

- Conversation recall proactive sync was failing repeatedly on April 7, April 8, and April 9, 2026
  while the local RAG API was unavailable or degraded.
- The logs show repeated upload retry loops, cooldown entry, and proactive-sync pause rather than a
  healthy corpus-refresh path.
- This means recent messages could exist in Mongo while the vector corpus remained stale.
- That remains a separate continuity surface from saved-memory correctness.

### 9. Groq is not a drop-in embeddings backend for this feature today

- The current conversation-recall embeddings path is explicitly OpenAI-auth-based.
- Live Groq probing did not reveal an embedding-capable model in the visible account inventory.
- Therefore switching recall embeddings to Groq is not a configuration fix. It would be a future
  product change requiring new provider support plus comparative quality evaluation.

## Public-Safe Evidence Summary

- Generated runtime memory writer before restart:
  - `provider: openai`
  - `model: gpt-5.4`
- Generated runtime memory writer after restart:
  - `provider: anthropic`
  - `model: claude-sonnet-4-6`
- Source-of-truth memory writer window:
  - `messageWindowSize: 15`
- Source-of-truth older-user-context bounds:
  - `historyContextMessageScanLimit: 40`
  - `historyContextUserTurnLimit: 4`
  - `historyContextCharLimit: 1200`
- Log evidence pattern:
  - scheduled run surfaced stale saved-memory context while file/recall retrieval also showed
    degradation
  - recall upload retries
  - recall cooldown / proactive-sync pauses
  - saved-memory init failure with `Provider openai not supported`
- Saved-memory store evidence pattern:
  - before restart, stale forgotten references remained in saved-memory keys
  - before restart, repeated semicolon-run corruption existed across multiple saved-memory keys
  - after restart/product-path verification, stale forgotten references were absent from the
    affected keys
  - after restart/product-path verification, repeated semicolon-run corruption was reduced to
    single separators in the affected keys
- Alternate-provider feasibility pattern:
  - Groq `/models` reachable with the configured runtime key
  - Groq `/embeddings` rejected all visible model IDs

## Follow-Ups

1. Run the `cross-surface landing gate` across Telegram, LibreChat web UI, scheduler-triggered
   flows, and any relevant voice smoke path.
2. Clear the current unrelated release-suite blockers, then run the `public release gate` from
   supported public entrypoints with a clean install story.
3. Keep the supported package-rebuild path under explicit release scrutiny for future
   Codex-connected memory changes; source-only fixes do not pass this gate.
4. Decide separately whether conversation recall needs an explicit, auditable forgetting/exclusion
   feature; that is not the same feature as saved-memory forgetting.
5. Add broader public-safe synthetic QA/evals for contradiction replacement and durable-memory
   update scenarios beyond the controller-level older-context coverage now in place.
