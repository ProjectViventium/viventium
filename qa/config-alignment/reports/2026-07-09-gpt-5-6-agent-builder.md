# GPT-5.6 Agent Builder QA — 2026-07-09
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

## Result

`CFGALIGN-004`: **PASS** for the Viventium ChatGPT connected-account path.

The first browser run exposed an auth-surface mismatch: the direct-API `gpt-5.6` alias was visible
to the connected account but that provider route rejected it. Provider probes showed that the QA
account accepted `gpt-5.6-sol` and `gpt-5.6-terra`. The generated connected-account inventory was
then narrowed to those verified slugs, with Sol first, and the full browser acceptance run passed.

## What Was Run

| Check | Result | Evidence |
| --- | --- | --- |
| Official model contract | PASS | Direct API inventory covers `gpt-5.6`, Sol, Terra, and Luna; no invented `gpt-5.6-pro` slug. |
| Generated connected-account env | PASS | `OPENAI_MODELS` and `ASSISTANTS_MODELS` begin with Sol and Terra and do not advertise the rejected alias/Luna slugs. |
| Real Agent Builder picker | PASS | Viventium QA account showed Sol and Terra; Sol selected with **Use Responses API** on. |
| Create/save/reload | PASS | Synthetic agent reloaded with `gpt-5.6-sol` and Responses enabled. |
| Real chat response | PASS | Browser received exactly `GPT56_AGENT_QA_OK`; no provider error was visible. |
| Conversation refresh | PASS | Exact response remained visible after a full page reload. |
| Persisted state | PASS | Saved agent state was `model=gpt-5.6-sol`, `useResponsesApi=true`; two persisted messages included the exact assistant marker with no assistant error. |
| Runtime logs | PASS | Runtime recorded OpenAI `gpt-5.6-sol`, stream completion, and finalization without a completion error for the passing run. |
| Cleanup | PASS | Synthetic agent, both synthetic conversations/messages, and the temporary QA browser session were removed. |

The real response completed in about 6.5 seconds from model start to finalization. The browser
reported no console errors during the passing create/run/reload flow.

## Automated Checks

- `tests/release/test_openai_model_inventory.py` plus the adjacent launcher regression suite:
  **6 passed**.
- Focused LibreChat API suites for model discovery and agent initialization: **58 passed**.
- Focused Agent Builder client helper suite: **8 passed**.
- Production LibreChat package/frontend build and post-build verification: **PASS**.
- Independent review-only second opinion: **APPROVE; no required changes**. It noted only low-risk
  follow-ups around model-parameter stickiness, duplicated catalog constants, and launcher-routing
  automation.
- Repository-wide client typecheck: **FAIL on pre-existing unrelated client errors**; the production
  build and changed-path tests passed.

## Degraded And Unrun Paths

- The QA account's separate Anthropic memory writer lacked authentication. The UI truthfully showed
  that memory-specific reconnect warning after the successful GPT-5.6 answer. It did not affect the
  GPT-5.6 response, saved agent state, or conversation persistence.
- A live direct API-key GPT-5.6 call was not run because this QA account uses the ChatGPT
  connected-account route. Direct-route coverage here is the official catalog contract, generated
  inventory, package tests, and production build—not a user-path completion.

## Public-Safety Check

No credentials, account identifiers, local absolute paths, private prompt content, raw logs, or
private screenshots are included in this report.
