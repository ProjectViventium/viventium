# Config Compiler xAI Model Inventory QA

## Scope

Verify Viventium's public config compiler, LibreChat source template, direct LibreChat dev launcher,
and live local UI expose xAI Grok 4.3.

## Requirements Under Test

- Generated `librechat.yaml` must include an xAI custom endpoint with `grok-4.3` as the first model.
- xAI conversation title and summary helpers must use `grok-4.3`, not a retiring model ID.
- Current xAI 4.20 stable IDs must use the dated `0309` forms documented by xAI.
- Retiring xAI model IDs must not appear in generated xAI model defaults, title model, or summary
  model.
- Future installs must work from tracked product sources:
  - `scripts/viventium/config_compiler.py`
  - `viventium_v0_4/LibreChat/viventium/source_of_truth/local.librechat.yaml`
  - `viventium_v0_4/LibreChat/viventium-start.sh`
- Local-safe compiler QA must compile into a temporary output directory first.
- Live local QA may intentionally recompile the local runtime and restart only the LibreChat API
  when explicitly requested by the operator.

## Environments

- Local public repo checkout on macOS shell tooling.
- Synthetic public-safe config fixtures with no real credentials.
- Temporary compiler output directories under `<temp>`.

## Test Cases

1. Compiler fallback xAI endpoint defaults to:
   - `grok-4.3`
   - `grok-4.20-multi-agent-0309`
   - `grok-4.20-0309-reasoning`
   - `grok-4.20-0309-non-reasoning`
2. Source-template xAI endpoint carries the same current stable inventory.
3. Rendered `librechat.yaml` preserves Grok 4.3 after source-template/custom-endpoint merge.
4. Compile a synthetic config with an explicit xAI key into `<temp>` and verify:
   - generated xAI endpoint uses `grok-4.3`
   - `runtime.env` and `service-env/librechat.env` carry the configured xAI env value
5. Compile a synthetic config without an xAI key into `<temp>` and verify:
   - generated xAI endpoint still uses `grok-4.3`
   - `runtime.env` and `service-env/librechat.env` expose `XAI_API_KEY=user_provided`
6. Confirm no retiring xAI IDs appear in generated temporary outputs.
7. Compile the local runtime through the public `bin/viventium compile-config` path.
8. Confirm live `/api/config` exposes a `grok-4.3` model spec with preset endpoint `xai`.
9. Real-browser QA:
   - search the model picker for `grok-4.3`
   - confirm `Grok 4.3` appears instead of `No results`
   - select it and confirm the composer switches to Grok/xAI routing

## Expected Results

- Targeted release tests pass.
- Generated output supports Grok 4.3 for future users through the public compiler path.
- Direct LibreChat dev starts refresh ignored `librechat.yaml` from source-of-truth before loading
  model specs.
- Live local browser picker can find and select `Grok 4.3`.
