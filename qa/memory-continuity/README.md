# Memory Continuity QA

## Scope

Verify that Viventium preserves continuity across two distinct product surfaces without conflating
them:

1. saved memories for durable explicit notes
2. conversation recall for recent and historical chat continuity

## Requirements Under Test

- The generated runtime memory writer must initialize successfully with the compiler-emitted
  provider/model contract.
- OpenAI connected-account memory runs on the Codex Responses bridge must lift instruction messages
  into top-level `instructions`; `system` / `developer` messages must not remain inside Responses
  `input`.
- When the Codex bridge adapts streamed Responses SSE back into JSON for a non-stream memory run,
  the adapted payload must preserve streamed `response.output_item.*` tool calls instead of
  returning `output: []`.
- The locally built `packages/api/dist` bundle used by runtime must carry that same Codex
  normalization logic; a source-only fix does not pass QA if the supported rebuild path still
  leaves stale compiled code in place.
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
- Chat-time saved-memory reads must stay bounded by `memory.readProfile`, dedupe duplicate keys,
  and avoid writer initialization/maintenance before the main answer starts.
- Memory writer work must run after the main response and must not be awaited during finalization.
- On installs with OpenAI auth available, the visible main/conscious chat route and the memory writer
  must both use the OpenAI-first compiler/source-of-truth policy; otherwise a stale Anthropic main
  agent can fail before the memory writer path is exercised.
- Provider auth failures in the memory writer must surface as a degraded/reconnect state and be
  health-gated instead of retried on every chat.
- Local retrieval tail timeouts and post-stream finalization failures that happen after meaningful
  assistant text must not append a red provider-error card to the same completed message;
  unrelated generic errors before stream completion must still surface instead of being silently
  swallowed.

## Environments

- Public repo checkout on macOS shell tooling
- Nested LibreChat repo test suites
- Public-safe inspection of generated runtime config, local logs, and live saved-memory state
- Local restart onto the generated runtime without manual App Support or Mongo edits
- Synthetic examples only for QA documentation and future evals

## Test Cases

1. Compiler/runtime contract
   - generated `librechat.yaml` emits a valid `memory.agent.provider` and runtime accepts it
   - generated `viventium.consciousAgent` and the live built-in main agent use the expected
     OpenAI-first provider/model when OpenAI auth is available
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
   - the saved-memory writer must survive the Codex-connected Responses request shape rather than
     failing with backend request-contract errors
   - the locally built runtime bundle used by the product must be verified after the supported
     rebuild path runs, not just the source test path
   - QA must therefore verify:
     - chat success
     - saved-memory artifact presence
     - cross-conversation recovery
     - recall-runtime health
     - compiled-bundle alignment for the owning Codex normalization path
9. Use memory latency / writer detach
   - source config contains `memory.readProfile`
   - read path test proves bounded, deduped memory context without writer maintenance
   - agent-client test proves writer initialization is lazy and detached
   - real browser QA compares visible response timing with deep timing log phases
   - `bin/viventium memory-dedupe --dry-run --json` reports counts without private identifiers

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
- Bounded read-profile coverage proves normal memory-enabled chat does not inject the full saved
  memory store or wait on writer work before returning the main answer.
- Dedupe/index coverage proves duplicate saved-memory/provider-key rows can be inspected safely
  before unique indexes are applied.
- The built runtime bundle used by the supported install/upgrade path must match the reviewed
  Codex memory normalization source path.
- If unrelated legacy test failures exist elsewhere, the report must call them out explicitly
  instead of mixing them into the memory-continuity verdict.
