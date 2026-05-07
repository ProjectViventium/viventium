# Config Compiler xAI Model Inventory QA Report

## Date

- 2026-05-07

## Build Under Test

- Working tree included targeted changes to:
  - config compiler xAI endpoint inventory
  - LibreChat source-template xAI endpoint inventory
  - public examples and xAI-related docs
  - Telegram xAI default model/example inventory
  - release tests for generated xAI endpoint behavior

## Safety Boundary

- No App Support runtime files were edited.
- No Keychain values were read or changed.
- No Mongo data, containers, live services, or generated local runtime files were touched.
- Acceptance compiles used synthetic public-safe credentials and temporary output directories only.
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

## Evidence

### Targeted Compiler Suite

- Result: `72 passed`
- Coverage added:
  - compiler fallback xAI endpoint defaults to Grok 4.3
  - source-template xAI endpoint defaults to Grok 4.3
  - rendered `librechat.yaml` preserves Grok 4.3 after source-template merge
  - retiring xAI IDs are not used as title/summary defaults

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

## Findings

- Future generated Viventium LibreChat configs now expose xAI Grok 4.3 through the public compiler
  path.
- The source-template/custom-endpoint merge path is covered by tests, so a future template drift
  should fail release tests.
- Existing local runtime state was not mutated during QA. To make a currently installed local
  runtime pick up the new config, the operator should use the normal public compile/upgrade/restart
  path when ready.

## Residual Risks

- This pass did not call the live xAI API because no real xAI credential was used; it verified
  product wiring, model IDs from official docs, compiler output, and generated env propagation.
- Existing live local App Support output will remain whatever it was until the normal Viventium
  compile/restart path is run intentionally.
