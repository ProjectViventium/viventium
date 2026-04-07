# Config Compiler Memory QA

## Scope

Verify the installer/compiler generates `librechat.yaml` memory and Anthropic title settings from
real configured foundation providers instead of preserving hidden xAI defaults from the source
template.

## Requirements Under Test

- `memory.agent.provider` and `memory.agent.model` must be compiled from actually available
  foundation providers (`openai` / `anthropic`), including connected-account auth.
- If both OpenAI and Anthropic are available, memory must honor configured foundation-provider
  order instead of silently preferring a different provider.
- Anthropic endpoint conversation-title generation must not depend on xAI in generated
  `librechat.yaml`.
- The public refresh path must be enough to update an existing local runtime:
  - `bin/viventium compile-config`
  - `bin/viventium stop`
  - `bin/viventium start`

## Environments

- Local public repo checkout on macOS shell tooling
- Public-safe synthetic config fixtures in release tests
- Actual local `~/Library/Application Support/Viventium/config.yaml` for acceptance compilation

## Test Cases

1. OpenAI-only foundation config compiles memory to `openai / gpt-5.4`.
2. Anthropic-only connected-account config compiles memory to `anthropic / claude-sonnet-4-6`.
3. Dual-foundation configs keep existing role assignments and compile memory using configured
   foundation order.
4. Generated Anthropic endpoint config sets `titleEndpoint: anthropic` and
   `titleModel: claude-sonnet-4-6`.
5. The actual local config compiles to the expected runtime output and the live local runtime can be
   refreshed through the public stop/start path.

## Expected Results

- `tests/release/test_config_compiler.py` passes.
- The generated `librechat.yaml` no longer contains hidden xAI defaults for `memory.agent` or the
  Anthropic endpoint title path when the user did not configure xAI for those surfaces.
- An existing local install picks up the new generated values after the public compile/restart path.
