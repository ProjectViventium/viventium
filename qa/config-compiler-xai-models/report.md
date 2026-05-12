# Config Compiler xAI Model Inventory QA Report

## Date

- 2026-05-07

## Build Under Test

- Working tree included targeted changes to:
  - config compiler xAI endpoint inventory
  - LibreChat source-template xAI endpoint inventory
  - direct LibreChat dev launcher source-of-truth config sync
  - public examples and xAI-related docs
  - Telegram xAI default model/example inventory
  - release tests for generated xAI endpoint and launcher behavior

## Safety Boundary

- Compiler QA first used temporary output directories and synthetic credentials.
- Live local QA intentionally recompiled the local runtime through `bin/viventium compile-config`
  after the operator requested the fix live locally.
- After the active local provider credential was rejected, an operator-managed credential reference
  was refreshed only through canonical local config and active runtime env surfaces. The secret value
  was not copied into repo files, QA artifacts, logs, or test fixtures.
- A follow-up compile after credential refresh was blocked by the active start lock, so the
  active runtime env files were refreshed from canonical local config and only the LibreChat API was
  restarted.
- No Keychain values were read or changed.
- No Mongo records were edited directly; throwaway browser QA conversations were created by the
  normal UI send path and then deleted through the normal UI delete flow.
- Only the LibreChat API process was restarted; the frontend stayed on the existing local port.
- Compiler acceptance commands were run with a clean environment via `env -i` so ambient local
  provider keys could not leak into generated evidence.

## Steps Executed

1. Official xAI source check:
   - xAI docs show `grok-4.3` as available.
   - xAI docs recommend `grok-4.3` for Chat API use.
   - xAI's May 15, 2026 retirement guide lists old `grok-4-1-fast*`, `grok-4-fast*`,
     `grok-4-0709`, `grok-code-fast-1`, and `grok-3` IDs as retiring.
2. Review-only ClaudeViv second opinion:
   - verdict: approve with refinements
   - refinements applied:
     - use dated 4.20 `0309` IDs
     - remove stale `experimental-beta-0304` source-template IDs
     - keep xAI out of built-in OpenAI/Anthropic foundation routing
3. Targeted compiler regression suite:
   - `uvx --with pyyaml pytest tests/release/test_config_compiler.py -q`
4. Telegram regression smoke:
   - `uv run --project <telegram-bot-project> --with pytest pytest <telegram-tests> -q`
5. Syntax checks:
   - config compiler `py_compile`
   - Telegram config `py_compile`
6. Synthetic xAI-key compile into `<temp>`:
   - compiled a public-safe config with `llm.extra_provider_keys.x_ai` set to a synthetic value
   - inspected generated `librechat.yaml`, `runtime.env`, and `service-env/librechat.env`
7. Synthetic no-xAI-key compile into `<temp>`:
   - compiled a public-safe config with no xAI key
   - inspected generated `librechat.yaml`, `runtime.env`, and `service-env/librechat.env`
8. Generated-output retirement scan:
   - scanned both temporary output directories for retiring xAI IDs and stale 0304 experimental IDs
9. Live local runtime compile and API restart:
   - ran `bin/viventium compile-config`
   - synced ignored `LibreChat/librechat.yaml` from tracked source-of-truth for the currently
     running dev stack
   - restarted the LibreChat API on the existing local API port
10. Live browser QA:
   - logged into the local app with the QA login flow
   - searched the model picker for `grok-4.3`
   - selected `Grok 4.3`
   - verified the composer switched to Grok/xAI routing
  - observed the active local provider credential fail with a redacted invalid-key response
11. Credential-refresh live retest:
   - updated only local config/runtime credential references through supported local surfaces
   - restarted the LibreChat API on the existing local API port
   - sent a real Grok 4.3 browser prompt and received the expected `OK` completion
   - deleted the throwaway QA conversations

## Evidence

### Targeted Compiler Suite

- Result: `75 passed`
- Coverage added:
  - compiler fallback xAI endpoint defaults to Grok 4.3
  - source-template xAI endpoint defaults to Grok 4.3
  - rendered `librechat.yaml` preserves Grok 4.3 after source-template merge
  - rendered `librechat.yaml` exposes Grok 4.3 in `modelSpecs`
  - retiring xAI IDs are not used as title/summary defaults
  - direct LibreChat dev starts sync ignored `librechat.yaml` from source-of-truth

### Telegram Smoke

- Result: `31 passed`

### Syntax Checks

- Config compiler `py_compile`: passed
- Telegram config `py_compile`: passed

### Synthetic xAI-Key Compile

- Generated xAI endpoint:
  - first model: `grok-4.3`
  - stable 4.20 IDs:
    - `grok-4.20-multi-agent-0309`
    - `grok-4.20-0309-reasoning`
    - `grok-4.20-0309-non-reasoning`
  - `titleModel: grok-4.3`
  - `summaryModel: grok-4.3`
  - `models.fetch: true`
  - `titleMethod: completion`
- Generated env:
  - `runtime.env` carried the synthetic xAI value
  - `service-env/librechat.env` carried the synthetic xAI value
- Built-in Viventium route remained on foundation provider:
  - conscious provider: `openai`
  - conscious model: `gpt-5.4`

### Synthetic No-xAI-Key Compile

- Generated xAI endpoint still used:
  - first model: `grok-4.3`
  - `titleModel: grok-4.3`
  - `summaryModel: grok-4.3`
- Generated env exposed browser/user-provided credential flow:
  - `runtime.env`: `XAI_API_KEY=user_provided`
  - `service-env/librechat.env`: `XAI_API_KEY=user_provided`

### Retirement Scan

- Generated temporary outputs did not contain:
  - `grok-4-1-fast-reasoning`
  - `grok-4-1-fast-non-reasoning`
  - `grok-4-fast-reasoning`
  - `grok-4-fast-non-reasoning`
  - `grok-4-0709`
  - `grok-code-fast-1`
  - `grok-3`
  - `experimental-beta-0304`

### Live Local Runtime

- Local generated runtime:
  - xAI first model: `grok-4.3`
  - xAI title model: `grok-4.3`
  - xAI summary model: `grok-4.3`
  - Grok 4.3 model spec: `name=grok-4.3`, `label=Grok 4.3`, `endpoint=xai`
- Live served API config:
  - `/api/health`: `OK`
  - `/api/config` model specs: 18
  - `/api/config` Grok 4.3 specs: 1
  - Grok 4.3 preset: `endpoint=xai`, `model=grok-4.3`
- Live browser:
  - model picker search for `grok-4.3` returned `Grok 4.3` and the raw `grok-4.3` xAI model row
  - selecting `Grok 4.3` changed the top model label to `Grok 4.3`
  - composer placeholder changed to `Message Grok`
  - test send reached xAI and returned a redacted xAI 400 invalid-key response, confirming request
    routing while also showing the active provider credential needed operator refresh before
    successful completions
  - after operator credential refresh and API restart, a real Grok 4.3 browser prompt returned `OK`
  - throwaway QA conversations were deleted through the UI

## Findings

- Future generated Viventium LibreChat configs now expose xAI Grok 4.3 through the public compiler
  path.
- The source-template/custom-endpoint/model-spec merge path is covered by tests, so a future template
  drift should fail release tests.
- Direct LibreChat dev starts now refresh ignored `librechat.yaml` from source-of-truth before model
  specs load, which prevents the stale local picker state that caused the original `No results`.
- The currently running local browser picker now finds and selects Grok 4.3.
- Live local completions through Grok 4.3 now succeed after the operator-side credential refresh.

## Residual Risks

- The credential-refresh follow-up used active runtime env refresh because
  `bin/viventium compile-config` was blocked by an active start lock. No local credential value was
  copied into this repo; the normal compile path should pick up the operator-managed credential
  reference on the next clean restart.
