# GPT-5.6 Conscious/Subconscious Routing QA — 2026-07-09
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Result

`ACT-35` / `BACKGROUND-UC-009`: **PASS** for the GPT-5.6 primary routing, Opus 4.8 fallback
configuration/runtime wiring, Agent Builder compatibility, live Viventium QA-account chat, and
restart persistence.

The shipped and live conscious/subconscious routes use this workload map:

| Route | Primary execution |
| --- | --- |
| Viventium | GPT-5.6 Sol / medium |
| Red Team, Deep Research | GPT-5.6 Sol / xhigh |
| Strategic Planning | GPT-5.6 Sol / high |
| Background Analysis, Confirmation Bias, Parietal Cortex, Pattern Recognition | GPT-5.6 Terra / medium |
| MS365, Google, Emotional Resonance, Viventium User Help | GPT-5.6 Terra / low |

Every OpenAI bag uses the Responses API. Every text route declares Anthropic Claude Opus 4.8 as
fallback. Red Team and Deep Research preserve a 4,000-token Anthropic thinking budget on fallback;
Strategic Planning preserves 2,000. The fallback initializer strips OpenAI-only
`reasoning_effort` and `useResponsesApi` fields before an Anthropic request. Voice remains
`xai / grok-4.3 / none`; its separate latency fallback is `openAI / gpt-5.6-terra / none`.

## Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Official model choice | PASS | Sol is used for flagship reasoning; Terra for balanced/latency-sensitive work; low/medium/high/xhigh follow the documented workload guidance. |
| Source/compiler/runtime contract | PASS | Exact 12-agent model/effort/Responses/fallback contract tests pass; compiler emits the same assignments. |
| Reviewed A/B/C sync | PASS | Model-only dry runs and pushes used explicit agent IDs. Post-sync compare reports zero live-vs-source agent drift; protected prompt/tool/cortex fields were excluded. |
| Generated and live state | PASS | Generated runtime assignments and 12 live agent rows match the source map. The three high-effort live Opus bags contain the 4k/4k/2k budgets. |
| Restart/reload | PASS | Canonical config compiled; local runtime restarted/reloaded healthy; API health returned OK. |
| Agent Builder compatibility | PASS | Same-day QA-account Agent Builder acceptance saved, reloaded, and ran GPT-5.6 Sol with Responses enabled; see the linked config-alignment report. |
| Real browser chat | PASS | QA-account parent answer was visible; Red Team and Confirmation Bias cards completed, expanded with terminal/why details, and persisted after reload. |
| Runtime execution | PASS | Final browser window recorded 8 Sol and 3 Terra model occurrences; both required cortices completed; unsupported-model/provider/auth error count was zero. |
| Browser/runtime errors | PASS | Zero console, failed-request, or critical HTTP errors in the passing run. |
| Fallback mechanism | PASS | Cross-provider sanitizer suite: 17/17. Main-agent lazy retry suite: 7/7. Source/live fallback bags match. |
| Independent review | PASS | Review-only Claude pass requested changes, the parameter-leak/thinking-budget finding was fixed, and the final verdict was **APPROVE**. |

The same QA account's Agent Builder model acceptance is documented in
[`../../config-alignment/reports/2026-07-09-gpt-5-6-agent-builder.md`](../../config-alignment/reports/2026-07-09-gpt-5-6-agent-builder.md).

## Automated Checks

- Compiler, model inventory, and sync safety: **117 passed**.
- Routing governance subset: **7 passed**.
- Runtime model normalization: **17 passed**.
- GPT-5.6 API defaults: **6 passed**.
- Agent Builder model-selection helpers: **8 passed**.
- Cross-provider fallback sanitization/retry helper: **17 passed**.
- Main-agent lazy fallback behavior: **7 passed**.
- Full background-governance file: **18 passed, 3 failed on pre-existing activation/prompt drift**.

## Degraded And Unrun Paths

- One intermediate browser run completed the Sol main answer and six Sol/Terra cortices in the
  backend, but the pre-existing activation-classifier drift skipped Red Team, so the visible-card
  harness correctly failed. A narrower explicit two-cortex rerun passed. This is retained as an
  activation-reliability signal, not misclassified as a model-routing failure.
- The three full-governance failures cover pre-existing Confirmation Bias/Support prompt drift,
  missing activation-provider fallback arrays, and an inline prompt versus `promptRef` mismatch.
  This task did not edit or push those protected activation/prompt fields. They remain a separate
  release-gate issue for the owner of that in-flight work.
- A forced live Opus provider-failure turn was not run against the QA account. The configured route,
  model inventory, source/live persistence, provider-native parameter bags, auth-blocker behavior,
  and deterministic one-shot retry path were verified. No production agent was intentionally
  broken merely to force an external failure.
- No new voice call was run because Grok 4.3 voice behavior was not changed; source, live DB, and
  contract tests verify that the primary voice route stayed Grok 4.3.

## Public Safety

All browser prompts were synthetic. No credentials, account identifiers, raw conversation text,
private screenshots, local absolute paths, or secret-bearing logs are included in this report.
