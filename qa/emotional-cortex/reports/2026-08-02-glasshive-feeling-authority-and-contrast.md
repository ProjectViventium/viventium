# GlassHive Feeling Authority And Contrast QA — 2026-08-02

## Verdict

**Provider/native authority: PASS. Behavioral potency: FAIL/PARTIAL.**

GlassHive now places one exact request-declared dynamic tail after its structural capability-broker
instructions. Feelings-off sends no tail. This fixes the real piping defect, but the live
GlassHive-backed Codex Main still did not reliably embody depleted, bright/playful, or mixed state.

## Linked cause

LibreChat's existing final-placement telemetry measured only the parent agent instruction string.
The actual Codex worker appended a capability-broker developer instruction afterward. Pre-fix native
artifacts therefore did not end with the Feeling capsule even though parent telemetry reported zero
trailing characters.

The transport fix exposed a second, independent cause. Once native order was correct, responses still
converged on closing an “open loop.” The stable Viventium prompt contains `Move forward. Hate loops.`
and an `open loops` memory example. Fresh App Server developer-item and system-item probes did not
remove this attractor. Experimental neutral wording produced visibly quieter/playful/mixed choices,
but one state varied across repeats, so the wording was not shipped.

## Implemented contract

- LibreChat binds the exact final capsule only on a GlassHive provider request.
- The value is bounded, strict Base64 transport encoding; it is not described as encryption.
- GlassHive rejects a declared tail absent from system/developer authority.
- The provider removes duplicates, places the opaque tail after structural broker text, and hashes
  the effective authority snapshot for session policy.
- Runtime logic is generic: no Feeling-tag, prompt-text, agent-name, or provider-label branch.
- Codex remains on additive `developer_instructions`, personality `none`, and the exact worker-local
  plugin denylist. Native base instructions are not replaced.

## Live evidence

The authenticated exact runner used one synthetic non-admin QA account, the same one/two-sentence
prompt, reactions disabled, exact pre-case Feeling restoration, and synthetic conversation cleanup.

| State | Native placement | Duration | Semantic result | Visible behavior summary |
| --- | --- | ---: | --- | --- |
| Off | zero Feeling tags | 9.14 s | PASS 1.00 | neutral focused activity |
| Depleted / guarded | one exact final suffix | 9.50 s | FAIL 0.25 | forceful productivity rather than quiet restraint |
| Bright / playful | one exact final suffix | 8.10 s | FAIL 0.75 | initiative present; Play absent |
| Low Mood / high Play | one exact final suffix | 6.62 s | FAIL 0.75 | heaviness/shared stance present; Play absent |

All four requests completed on the first attempt. Median provider-visible turn time was 8.62 seconds.
The local-agent semantic judge graded all four; it is supporting evidence, not an independent vendor
judge. The configured OpenAI connected-account judge was unavailable because that account required
reconnection.

Post-fix native DB/config correlation showed:

- off: zero capsule occurrences;
- each enabled state: exactly one occurrence and one matching declared tail;
- each enabled worker: developer instructions ended with the exact tail;
- capability-broker text occurred before the tail;
- all provider requests completed.

## Experiments not shipped

- A generic final grounding sentence improved depleted behavior but left three of four cases failing.
  It was removed from source and the installed runtime.
- Fresh App Server developer-role injection, a separate final developer item, and an accepted raw
  system-role item did not reliably restore Play. Production remains `codex exec`.
- Neutralizing the two stable prompt attractors produced the first visible playful/mixed outputs,
  but repeated depleted behavior was inconsistent. Protected prompt defaults were not changed or
  synced.

## Automated verification

- GlassHive conversation provider: 80 passed in the installed checkout; 41 passed in tracked source.
- GlassHive native profile/runtime: 211 passed installed; 178 passed tracked source.
- LibreChat provider-tail and prompt-tail suites: 18 passed installed; 10 passed tracked source.
- Feelings kernel: 14 passed in tracked and installed source after removing the failed experiment.
- Public release Feelings contract: 20 passed.

## Remaining gate

GlassHive Feelings cannot be called accepted until an approved, prompt-neutral structural wording
change passes repeated off/depleted/bright/mixed same-prompt contrasts through the production
`codex exec` path. Correct transport, marker output, or one lucky completion is insufficient.

No private prompts, raw identifiers, credentials, local absolute paths, or user data are stored in
this report. Raw completions and runtime artifacts remain in private local QA storage.
