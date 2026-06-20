<!-- qa-evidence-exempt: legacy sanitized RCA/QA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->

# 2026-06-10 Connected Accounts Handoff Calendar Boundary, Read, And Fallback QA

Status: **PASS** for the quick-read handoff path, calendar mutation boundary, and
Anthropic-to-`gpt-5.4` fallback recovery. A real confirmed calendar create/delete smoke was **not
run** because it would mutate a connected calendar.

## Scope

Finish the Connected Accounts handoff re-enable after provider rate limiting, and fix the escaped
calendar issue where a calendar write request was routed through the read-only handoff.

The intended split is:

- Connected Accounts: immediate read-only connected-account checks and quick updates.
- Confirmed write path: connected-account mutations such as calendar create/update/delete and
  email send/reply/draft, with explicit user confirmation and an available write-capable path.
- GlassHive: document generation, reports, deep research, browser/computer work, multi-step
  co-work, long-running audits, autonomous worker tasks, and confirmed connected-account writes
  when the broker is the available write-capable path.

## Root Cause And Fix

Sanitized DB/log inspection of the failing calendar turn showed a calendar mutation request
transferred to Connected Accounts and no calendar write tool calls. The visible result complained
about read-only calendar access because the handoff edge was too broad for write requests.

Fixes applied:

- Main prompt avoids Connected Accounts for connected-account mutations and requires explicit
  confirmation before any connected-account write.
- Main prompt names a concrete write-capable path: GlassHive host-signed broker path when available,
  or an available direct provider tool; if neither exists, fail closed and say so plainly.
- Connected Accounts instructions and edge prompt explicitly reject create/update/delete,
  move/archive/send/reply/draft/mark-as-read, and other connected-account mutations.
- Provisioner refreshes existing Connected Accounts instructions, preserves unrelated main-agent
  edges, and provisions `openAI / gpt-5.4` fallback for the Connected Accounts agent.
- Runtime OpenAI initialization now lets fallback LLM materialization use the platform OpenAI key
  when a stale user OpenAI OAuth refresh fails, but only under the fallback-recovery request flag;
  ordinary OpenAI connected-account use still surfaces reconnect guidance.
- Source-owned Anthropic agents now carry `openAI / gpt-5.4` fallback.

## Live Config Evidence

Sanitized live DB audit after prompt sync, provisioning, and fallback updates:

```json
{
  "mainHasExplicitConfirmation": true,
  "mainHasWriteCapablePath": true,
  "mainNamesGlassHiveHostSignedBroker": true,
  "mainFailsClosedWhenNoWritePath": true,
  "edgeExcludesAnyMutation": true,
  "connectedInstructionsHasMutationBoundary": true,
  "connectedReadToolCount": 22,
  "connectedWriteLikeToolCount": 0,
  "mainDirectProviderToolCount": 0,
  "sourceOwnedAnthropicMissingFallback": 0,
  "liveSourceOwnedAnthropicMissingFallback": 0,
  "liveSourceOwnedAnthropicAgentCount": 8
}
```

Two untracked user-created Anthropic agents in the live DB did not have fallback configured. They are
outside the source-owned Viventium bundle and were not changed in this run.

## Browser QA

Surface: local LibreChat web UI with a short-lived local JWT for the configured Viventium runtime
test account. Evidence is public-safe: hashes/counts/route flags only.

### Neutral Calendar Mutation Boundary

Synthetic browser prompt: neutral calendar-create request with no explicit "do not create" wording.

Result: **PASS**.

- Visible answer before reload: PASS.
- Visible answer after reload: PASS.
- Visible output: asked for confirmation and whether to use Google or Outlook calendar.
- DB conversation hash: `38e27e89f328`.
- Persisted parts: `text` only.
- Connected Accounts transfer tool present: no.
- GlassHive route present: no.
- Known calendar write tool present: no.
- Read-only complaint text present: no.
- Rate-limit / provider-failure bubble present: no.
- Email-like text in assistant content: no.

The run did not create or modify a calendar event.

### Quick Read Handoff

Synthetic browser prompt: check whether connected email inboxes are reachable; no account
identifiers, message subjects, or private details.

Result: **PASS**.

- Visible answer before reload: PASS.
- Visible answer after reload: PASS.
- Visible output: both connected inbox providers reachable; no account identifiers or message
  details.
- DB conversation hash: `f1f7b4756a63`.
- Persisted parts: `tool_call`, `text`, `text`, `text`.
- Connected Accounts transfer tool present: yes.
- GlassHive route present: no.
- Known calendar/email write tool present: no.
- Rate-limit / provider-failure bubble present: no.
- Worker plumbing text present: no.
- Email-like text in assistant content: no.

Note: provider sub-agent read-tool calls are not persisted in the parent message record; browser and
parent DB evidence prove the handoff transfer plus visible provider-status result.

## Fallback Evidence

- Before the runtime fix, the same local day had Anthropic `provider_rate_limited` errors followed
  by fallback initialization failure: `OpenAI connected account needs reconnect`.
- After rebuilding `@librechat/api` and restarting the API process, the built-dist initializer probe
  hit a stale OpenAI OAuth refresh failure and still returned a usable `gpt-5.4` config with an API
  key under the fallback-recovery flag.
- Post-fix browser calendar/read prompts produced visible answers and no rate-limit bubble.
- Live product-owned Anthropic agents with `openAI / gpt-5.4` fallback: Main, Connected Accounts,
  Background Analysis, Confirmation Bias, Pattern Recognition, Emotional Resonance, Strategic
  Planning, and User Help.
- Structured source audit: 7 YAML-owned Anthropic agents, 0 missing fallback.
- Structured live DB audit: 8 source/provisioner-owned Anthropic agents including Connected
  Accounts, 0 missing fallback.

## Second Opinion

ClaudeViv/Fable review was attempted before the final fallback rerun, but the local helper hit
provider credit/rate limits. Its partial review flagged two issues that were addressed here:

- The write path needed to name an actual confirmed write-capable route, not just "not Connected
  Accounts".
- The quick-read result should be described as parent-message handoff/visible-result evidence,
  because provider sub-agent calls are not persisted on the parent message.

No final Claude rerun was possible while the helper was credit-blocked.

## Automated Checks

PASS:

- `node --check viventium_v0_4/LibreChat/scripts/viventium-provision-connected-accounts-agent.js`
- `node --check viventium_v0_4/LibreChat/api/server/services/Endpoints/agents/initialize.js`
- `npm exec --workspace @librechat/api -- jest src/endpoints/openai/initialize.spec.ts --runInBand --coverage=false`
  - Result: 12 passed.
- `uv run --with pytest --with PyYAML==6.0.2 python -m pytest tests/release/test_qa_results_public_safety.py tests/release/test_productivity_activation_source_of_truth.py tests/release/test_prompt_registry.py -q`
  - Result: 48 passed.

## Result

- `CA-HANDOFF-001`: PASS.
- `CA-HANDOFF-004`: PASS for read-only tool scope and no pre-confirmation mutation.
- `CA-HANDOFF-010`: PASS for surgical provisioner behavior.
- `CA-HANDOFF-011`: PASS for the escaped calendar mutation routing bug.
- `CA-HANDOFF-012`: PASS for Anthropic-to-`gpt-5.4` fallback recovery.

Remaining gap: a confirmed create/delete calendar smoke should only be run with explicit permission
to mutate a connected calendar. The current run proves the problematic read-only route no longer
happens and prevents silent mutation before confirmation.
