# Background Cortex Phase B Fallback QA - 2026-05-06

## Scope

Validate the fix for background cortex execution failures where optional Phase B agents activate,
then time out before producing an insight. The covered surfaces are:

- background cortex execution fallback from Anthropic to OpenAI
- activation prompt narrowing for generic support and confirmation-bias cortices
- source-of-truth model inventory hygiene
- live user-level agent sync safety

## Acceptance Criteria

- A configured background cortex retries once on `timeout`, abort, or recoverable provider failure
  before surfacing a terminal error.
- Tool/MCP failures and `no_live_tool_execution` do not trigger LLM fallback.
- Productivity activation classifiers retain explicit `activation.fallbacks` so Groq Phase A
  provider issues fall through to supported classifier backups instead of deterministic heuristics.
- Viventium User Help activates only for explicit product-usage help about Viventium.
- Confirmation Bias activates only for a concrete claim, plan, conclusion, or assumption.
- The model picker does not expose `claude-sonnet-4-7` until the provider/runtime catalog verifies
  that model.
- User-level live sync is dry-run reviewed and narrowed to the intended agents/fields.

## Evidence Log

- Backend syntax checks passed:
  - `node -c api/server/services/BackgroundCortexService.js`
  - `node -c api/server/services/viventium/agentLlmFallback.js`
- Source YAML loaded cleanly for `local.viventium-agents.yaml` and `local.librechat.yaml`.
- Focused API tests passed: 66 tests across background-cortex execution, fallback retry, and
  activation policy suites.
- Release/config tests passed: 82 tests across background-agent governance and config compiler.
- Live user-level agent backup was pulled before sync. The same surgical sync was dry-run reviewed
  before apply for the owner live bundle and the local QA-account bundle.
- Live sync applied only the affected surfaces:
  - Confirmation Bias activation prompt and `openAI / gpt-5.4` high fallback.
  - Viventium User Help activation prompt, diagnostic `{NTA}` output guard, `web_search`, and
    `openAI / gpt-5.4` high fallback.
- Runtime API health returned `OK`.
- Runtime model config exposes `claude-sonnet-4-6` and `claude-opus-4-7`; it does not expose
  `claude-sonnet-4-7`.
- Authenticated runtime `/api/models` exposes `openAI: ["gpt-5.4", ...]`, so the configured
  background fallback model is present in the live model catalog used by fallback validation.
- Real browser QA on the local QA account found an initial remaining false positive where an
  operator-diagnostic prompt still activated Viventium User Help. The activation prompt was tightened
  with negative precedence and a required user-facing product-usage gate, and User Help instructions
  were updated to return `{NTA}` for diagnostics if misactivated.
- Final browser QA with the same synthetic diagnostic prompt produced no Viventium User Help cortex,
  no Confirmation Bias cortex, and no stale brewing row in Mongo.
- Final Claude review found a real retry-predicate issue: non-retryable tool/MCP errors were being
  detected by broad error-text substrings. The predicate now relies on structured non-retryable
  error classes such as `no_live_tool_execution` / `mcp_tool_failure`, and still retries provider
  timeout/abort messages even when the provider text mentions tool-calling.
- Final ClaudeViv review found two shipping blockers after that patch:
  - the main-agent fallback path could now retry unstructured MCP/tool errors if their text also
    contained provider-error tokens such as `429` or `rate_limit`;
  - the MS365 and Google Workspace productivity activation `fallbacks` arrays had been
    unintentionally removed from source of truth.
- Follow-up fix applied after ClaudeViv:
  - main-agent fallback again refuses unstructured `tool`/`mcp` error text, while the dedicated
    background-cortex retry path still allows provider timeout/overload text that mentions
    tool-calling;
  - MS365 and Google Workspace activation classifier fallbacks were restored to
    `openai / gpt-5.4` and `anthropic / claude-haiku-4-5`;
  - governance tests now pin those productivity activation fallbacks so they cannot silently drop.
- Post-ClaudeViv live sync dry-runed and applied only `activation.fallbacks` for MS365 and Google
  Workspace on the owner and local QA-account bundles. Fresh live pulls confirmed both bundles now
  carry the restored fallback arrays.
- Final post-ClaudeViv Claude review confirmed those two blockers were closed and found one
  low-severity Phase B content-part edge: provider errors containing both `tool`/`mcp` text and
  recoverable provider tokens could skip fallback if they arrived as aggregated content parts. The
  cortex path now uses a dedicated background-cortex content-part retry gate, and the integration
  test covers `Tool call failed with status 529 overloaded` retrying to `openAI / gpt-5.4`.

## Follow-Up Notes

- The original incident's `Confirmation Bias` and `Viventium User Help` failures were Phase B
  Anthropic execution timeouts/aborts, not activation-provider failures.
- Earlier Groq activation failures caused by full-tunnel VPN egress are documented separately in
  `02_Background_Agents.md`; split tunneling remains the supported local remediation.
- Local logs still contain unrelated Scheduling Cortex MCP reinitialize noise. That issue is outside
  this fallback/activation fix and should be handled separately if it affects user-visible behavior.
