# Memory Continuity QA

## Scope

Verify that Viventium preserves continuity across two distinct product surfaces without conflating
them:

1. saved memories for durable explicit notes
2. conversation recall for recent and historical chat continuity

## Requirements Under Test

- The generated runtime memory writer must initialize successfully with the compiler-emitted
  provider/model contract.
- Saved-memory behavior must remain additive, contradiction-aware, and token-efficient.
- Forgetting must correctly rewrite only the affected detail across all impacted keys without
  dropping unrelated history, tracking, or signals.
- Fresh writes must not preserve repeated punctuation corruption such as semicolon runs, and
  deterministic maintenance must clean any existing corruption already in the store.
- Expired temporal keys and long-idle active drafts must self-heal without requiring token pressure
  or unrelated scheduler noise to trigger maintenance.
- Recent user corrections must remain recoverable even when they were never promoted into durable
  memory.
- Short vector-indexing lag or vector-runtime outage must degrade to honest lexical recall rather
  than stale or misleading vector evidence.
- Scheduler/task tooling must not leak stale generated prose into normal continuity surfaces.

## Environments

- Public repo checkout on macOS shell tooling
- Nested LibreChat repo test suites
- Public-safe inspection of generated runtime config, local logs, and live saved-memory state
- Local restart onto the generated runtime without manual App Support or Mongo edits
- Synthetic examples only for QA documentation and future evals

## Test Cases

1. Compiler/runtime contract
   - generated `librechat.yaml` emits a valid `memory.agent.provider` and runtime accepts it
   - after local restart, helper logs no longer show the prior unsupported-provider init failure
2. Durable memory writer behavior
   - memory policy and memory agent tests pass for additive updates, overwrite handling, and noise
     rejection
   - a real browser pass on a connected account proves that an explicit memory-worthy prompt creates
     a visible entry in the `Memories` panel; an in-thread success reply alone does not pass
3. Forgetting + integrity behavior
   - partial forgetting is defined as a cross-key `set_memory` rewrite contract, not a whole-key
     delete shortcut
   - repeated punctuation corruption is cleaned on new writes and by deterministic maintenance
   - long-idle active drafts archive compactly without dropping prior archived history
   - expired `context` / stale `working` refresh even when the memory store is under budget
   - stale forgotten references can be removed through the product maintenance/write path without
     manual database edits
4. Recall attachment correctness
   - stale or unreachable vector recall is not attached as live evidence
5. Recall degraded-mode correctness
   - broad catch-up prompts still retrieve recent conversational corrections through lexical fallback
6. Indexing-health correctness
   - repeated transient vector-upload failures are visible and understood as an indexing outage, not
     as “no history exists”
7. Long-conversation correction coverage
   - important corrections do not disappear purely because they fell outside a tiny memory writer
     window
8. Connected-account live continuity check
   - real connected-account chat can succeed while saved memory or conversation recall still fail
   - QA must therefore verify:
     - chat success
     - saved-memory artifact presence
     - cross-conversation recovery
     - recall-runtime health

## Expected Results

- Targeted recall, memory, and compiler tests pass for the owned surfaces under review.
- Local restart onto the compiled runtime proves the saved-memory writer initializes under the
  generated provider/model contract.
- Public-safe live verification proves the stale forgotten references and repeated semicolon-run
  corruption are no longer present in the affected saved-memory keys after the product path runs.
- Public-safe QA evidence clearly separates:
  - recall indexing/retrieval failures
  - saved-memory writer initialization failures
  - forgetting-contract / integrity failures inside saved memory
  - implemented structural fixes
  - remaining broader landing/release-gate work
- Bounded older-user-context coverage proves long-conversation corrections are not lost purely
  because they fell outside the current chat window.
- If unrelated legacy test failures exist elsewhere, the report must call them out explicitly
  instead of mixing them into the memory-continuity verdict.
