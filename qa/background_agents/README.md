# Background Agents QA

## Scope

Verify Anthropic background-cortex execution stays compatible with provider thinking defaults while
the shipped built-in bundle remains truthful for fresh installs and local restarts.

## Requirements Under Test

- Background cortices must not send `temperature` when Anthropic thinking is active.
- The guard must cover thinking that appears only after runtime initialization, not just explicit
  source-of-truth fields.
- Built-in Anthropic cortices that intentionally use `temperature` must set `thinking: false`
  explicitly in the source-of-truth bundle.
- Local LibreChat startup must continue sourcing built-in agent truth from
  `viventium/source_of_truth/local.viventium-agents.yaml` via the built-in seed path.

## Environments

- Local public repo checkout on macOS shell tooling
- Nested `viventium_v0_4/LibreChat` workspace test environment
- Public-safe synthetic inputs only

## Test Cases

1. Anthropic endpoint tests verify Sonnet 4.6 and Opus 4.6 remove `temperature` when default
   thinking becomes active.
2. Memory-agent tests verify Anthropic adaptive thinking also strips `temperature`, while disabled
   thinking does not.
3. Background-cortex service tests verify both:
   - explicit pre-initialize thinking + temperature
   - post-initialize hydrated thinking + temperature
   - post-initialize hydrated thinking for a generic user-created Anthropic cortex, not just the
     shipped built-ins
4. Source-of-truth YAML audit verifies there are zero shipped Anthropic background agents with
   `temperature` but no explicit `thinking`/`thinkingBudget`.
5. Start-script inspection verifies local startup still re-seeds built-ins from the source-of-truth
   agents bundle through `viventium-seed-agents.js`.

## Expected Results

- Targeted Jest suites pass for Anthropic endpoint, memory, and background-cortex execution.
- The source-of-truth audit reports zero remaining Anthropic built-ins with ambiguous
  `temperature`-plus-default-thinking behavior.
- Start-path inspection confirms fresh installs and restarts consume the corrected bundle instead of
  relying on live Mongo edits.
