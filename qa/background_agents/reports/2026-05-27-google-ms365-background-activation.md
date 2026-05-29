# Google/MS365 Background Activation QA

## Scope

Validate the May 27, 2026 fix for generic plural inbox requests routed through Viv main with Google
and MS365 as background productivity cortices.

This report is public-safe: it uses synthetic prompt wording, aggregate provider reachability, and
conversation IDs only. It intentionally omits account names, sender names, message subjects, message
snippets, secrets, local user paths, and private runtime values.

## Requirements

- Keep Google/MS365 MCPs off Viv main unless source-of-truth explicitly connects them there.
- Preserve live user-managed Google/MS365 specialist agent MCP tool arrays; do not broad-push stale
  source over the live agents.
- Activation semantics stay in source activation prompts/evals, not runtime keyword matching.
- Groq remains the Phase A primary activation provider. Provider failures must be classified from
  evidence instead of changing the configured fast path.
- Phase B provider-stage failures must preserve activation/tool metadata and retry the configured
  fallback once when the failure happens before tool execution.
- A productivity cortex with zero current-run live tool calls must not be treated as a successful
  inbox/workspace check.

## RCA Evidence

- `a2ad68cd` introduced the MS365/direct-action drift surface on May 6, 2026: Phase B failures could
  lose configured-tool metadata and land as generic `background_agent_error`, so the configured
  fallback did not run.
- `3967b2ea` on May 17, 2026 intentionally moved Google away from Viv main MCP ownership. That
  intent is preserved: Google remains a background agent, not a main-agent MCP surface.
- The original generic prompt failed activation because the Google/MS365 activation prompts did not
  explicitly treat unrestricted plural/all-inbox requests as provider-scoped work for both
  productivity cortices.
- The inspected direct-model conversation used a non-Viv model route and failed with a model-provider
  completion error; that was not evidence of Groq activation failure.
- Runtime logs for the fixed browser run showed Groq Phase A succeeding with `2/11 activated`.
  The failing provider in Phase B was `openAI / gpt-5.4`; it was retried through the configured
  fallback without changing Groq.

## Live Drift Review

`viventium-sync-agents.js compare --env=local --yaml` still reports protected live-vs-source drift:

- Google specialist live tools: 85; source tools: 12.
- MS365 specialist live tools: 94; source tools: 10.
- Viv main has 11 background cortices and does not acquire Google/MS365 MCP tools as part of this
  fix.
- The only live sync applied for this incident was activation-prompt-only for the Google and MS365
  entries on Viv main after dry-run review. Broad source push remains inappropriate until the
  protected live agent state is intentionally reconciled.

## Fixes Under Test

- Google/MS365 activation prompts now cover unrestricted plural/all-inbox requests and preserve
  single-provider negative controls.
- Phase B execution preserves `activation_scope`, `configured_tools`, and `completed_tool_calls`
  on provider-stage failures.
- Generic pre-tool stream/create-run provider failures become `recoverable_provider_error` only when
  there are no tool/MCP/auth error signals.
- Configured Phase B fallback retries once for recoverable provider-stage failures.
- Productivity cortices that finish with zero live tool calls return a `no_live_tool_execution`
  terminal error instead of silent success.
- Follow-up synthesis receives sanitized background limitations so the visible answer can say a
  provider is unverified instead of claiming the provider is outside scope.
- Direct-action source wording was narrowed to describe same-scope behavior only when the provider
  MCP is actually connected to the main agent.

## User-Grade QA

### Authenticated Chrome Browser - Final Post-Restart Smoke

Prompt:

```text
Check my inboxes across Gmail and Outlook. For QA, only report whether each provider was reachable; do not quote sender names, subjects, or message contents.
```

Conversation: `f8553187-434b-458d-af45-84ea44420542`

Visible result:

- Google and MS365 background rows were visible.
- The final answer reported Gmail reachable.
- The final answer reported Outlook reachable.
- The final answer did not include sender names, subjects, snippets, or message details.

Mongo evidence for the same conversation:

- MS365 cortex part:
  - `status: complete`
  - `activation_scope: productivity_ms365`
  - `configured_tools: 95`
  - `completed_tool_calls: 1`
  - public-safe insight: `Outlook: reachable`
- Google cortex part:
  - `status: complete`
  - `activation_scope: productivity_google_workspace`
  - `configured_tools: 86`
  - `completed_tool_calls: 1`
  - public-safe insight: `Gmail: reachable`

Log evidence for the same run:

- Groq Phase A activation completed with `2/11 activated`.
- MS365 and Google both emitted activating/brewing events.
- `openAI / gpt-5.4` Phase B failed before insight for both productivity cortices and was retried
  through `xai / grok-4.3`.
- Google completed with one live tool call.
- MS365 completed with one live tool call.
- Execution summary reported `2/2 visible insights, 0 silent completions, 0 errors`.

### Authenticated Chrome Browser - Limitation Guard Run

Prompt:

```text
Check my inboxes across Gmail and Outlook. For QA, only report whether each provider was reachable; do not quote sender names, subjects, or message contents.
```

Conversation: `fad3f9d5-bae3-4956-9138-24e4395933f3`

Visible result:

- Google and MS365 background rows were visible.
- The final answer reported Gmail reachable.
- The final answer reported Outlook/MS365 as unverified because live reachability could not be
  confirmed in that run.
- The answer did not claim Outlook was outside scope.

Mongo evidence for the same conversation:

- MS365 cortex part:
  - `status: error`
  - `error_class: no_live_tool_execution`
  - `activation_scope: productivity_ms365`
  - `configured_tools: 95`
  - `completed_tool_calls: 0`
- Google cortex part:
  - `status: complete`
  - `activation_scope: productivity_google_workspace`
  - `configured_tools: 86`
  - `completed_tool_calls: 1`

Log evidence for the same run:

- Groq Phase A activation completed with `2/11 activated`.
- MS365 and Google both emitted activating/brewing events.
- `openAI / gpt-5.4` Phase B failed before insight for both productivity cortices and was retried
  through `xai / grok-4.3`.
- Google completed with one live tool call.
- MS365 completed with zero live tool calls and was promoted to `no_live_tool_execution`.
- Execution summary reported `1/2 visible insights, 0 silent completions, 1 errors`.

This earlier run remains useful as regression evidence for the no-live-tool-evidence limitation
guard. The final post-restart smoke above is the acceptance run for provider reachability.

### Playwright Browser Boundary

Playwright CLI opened the local app successfully, but the isolated browser landed on `/login`.
That run is `BLOCKED` for authenticated inbox QA, so the authenticated Chrome profile run above is
the user-path proof.

### Runtime Health

- `http://localhost:3190` returned OK.
- `http://localhost:3190/api/health` returned OK.

## Automated Checks

| Check | Result |
| --- | --- |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexService.test.js --runInBand` | 56 passed |
| `api npm run test:ci -- --runTestsByPath test/services/viventium/backgroundCortexFollowUpService.test.js server/services/viventium/__tests__/cortexFallbackText.spec.js --runInBand` | 86 passed |
| `uv run --with pytest --with pyyaml python -m pytest tests/release/test_productivity_activation_source_of_truth.py tests/release/test_background_agent_governance_contract.py tests/release/test_prompt_registry.py::test_phase_b_follow_up_prompts_render_with_declared_variables -q` | 38 passed |

## Second Opinion

Claude review-only confirmed the RCA and fix direction:

- Keep Google/MS365 off Viv main tools.
- Do not delete direct-action MCP declarations; clarify wording.
- Fix generic plural inbox activation in source prompts.
- Preserve Phase B metadata and classify only pre-tool provider-stage failures as recoverable.
- Do not broadly add `completion_error` to fallback classes.
- Use a narrow activation-prompt-only live sync and keep live specialist MCP tool arrays protected.
- Add ACT-25/ACT-26 coverage plus an inverse governance test that Viv main does not ship provider
  productivity MCP tools.
- A final Claude pass found no blocking issue and recommended two small cleanups; those were folded
  in before final QA: the follow-up templates now use `background_limitations` explicitly, and bare
  provider auth text maps to auth/access-denied classes instead of a recoverable provider class.

## Acceptance

| Requirement | Result |
| --- | --- |
| Generic plural inbox prompt activates both productivity cortices | PASS |
| Viv main keeps Google/MS365 MCPs off its own tool list | PASS |
| Live Google/MS365 specialist tool arrays are not overwritten | PASS |
| Groq activation is not changed or blamed without evidence | PASS |
| Phase B provider failure retries fallback and preserves metadata | PASS |
| Google live provider evidence completes in browser QA | PASS |
| MS365 live provider evidence completes in browser QA | PASS |
| Playwright authenticated browser path | BLOCKED by login; authenticated Chrome path used |
| Voice/audio path | NOT RUN; this incident changed shared background runtime and web QA, not voice-specific code |

## Residual Risk

Live-vs-source specialist tool-array drift remains protected and intentionally unresolved in this
incident. A future reconciliation should compare live Google/MS365 specialist tools against tracked
source before any broad sync, so source stops looking smaller than the verified local specialist
agents without overwriting user-managed state.
