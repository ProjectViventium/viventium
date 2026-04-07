# Config Compiler Memory QA Report

## Date

- 2026-04-05

## Build Under Test

- Parent repo base commit: `dcabc27`
- Working tree included changes to:
  - config compiler memory assignment
  - Anthropic endpoint title assignment
  - release tests
  - installer/compiler and memory docs
  - QA artifacts for this compiler flow

## Steps Executed

1. Targeted compiler regression suite:
   - `python3 -m pytest tests/release/test_config_compiler.py -q`
2. Broader release suite smoke pass:
   - `python3 -m pytest tests/release/ -q`
3. Real-config temp compile:
   - `python3 scripts/viventium/config_compiler.py --config "$HOME/Library/Application Support/Viventium/config.yaml" --output-dir "$TMPDIR/..."`
4. Generated-output inspection:
   - verified the temp `librechat.yaml` memory writer
   - verified the temp `librechat.yaml` Anthropic title settings
5. Live-runtime refresh:
   - released a wedged `bin/viventium start` lock holder from an earlier run
   - `bin/viventium stop`
   - `VIVENTIUM_DETACHED_START=true bin/viventium start --modern-playground`
   - observed an unrelated remote-access failure:
     - `public_https_edge` certificate setup timed out on the configured `sslip.io` hostnames
     - the launcher shut the stack back down after that timeout
   - fallback runtime verification:
     - sourced generated `runtime.env` and `runtime.local.env`
     - started LibreChat backend directly with `CONFIG_PATH="$HOME/Library/Application Support/Viventium/runtime/librechat.yaml"`
     - started LibreChat frontend directly against the same generated runtime
6. Review-only second opinion:
   - attempted local `claude -p` review-only pass with a 180 second timeout
   - helper did not return findings before timing out

## Evidence

### Targeted Compiler Suite

- `python3 -m pytest tests/release/test_config_compiler.py -q`
  - `44 passed`

### Broader Release Suite

- `python3 -m pytest tests/release/ -q`
  - compiler-memory changes passed
  - unrelated pre-existing failures remain in:
    - `tests/release/test_background_agent_governance_contract.py`
    - `tests/release/test_detached_librechat_supervision.py`
    - `tests/release/test_local_web_search_compose.py`
    - `tests/release/test_native_stack_helpers.py`
    - `tests/release/test_voice_playground_dispatch_contract.py`

### Real-Config Temp Compile

- Temp compile output verified:
  - `memory.agent.provider = openai`
  - `memory.agent.model = gpt-5.4`
  - `endpoints.anthropic.titleEndpoint = anthropic`
  - `endpoints.anthropic.titleModel = claude-sonnet-4-6`

### Live Runtime

- Generated runtime now also matches in the actual App Support output:
  - `memory.agent.provider = openai`
  - `memory.agent.model = gpt-5.4`
  - `endpoints.anthropic.titleEndpoint = anthropic`
  - `endpoints.anthropic.titleModel = claude-sonnet-4-6`
- Backend runtime verification:
  - started LibreChat backend directly against the generated runtime env + `CONFIG_PATH`
  - `curl -sf http://localhost:3180/api/health` returned `OK`
- Frontend runtime verification:
  - started LibreChat frontend directly against the same generated runtime
  - `curl -sf http://localhost:3190/ | head -n 5` returned the Vite HTML shell

### Public Start-Path Blocker

- `VIVENTIUM_DETACHED_START=true bin/viventium start --modern-playground`
  - recompiled the runtime successfully
  - then failed for an unrelated reason:
    - `Remote access setup failed: Timed out waiting for public HTTPS certificates ...`
  - this is a separate `public_https_edge`/certificate issue, not a regression in the
    compiler-memory change itself

### Second Opinion Attempt

- Local `claude -p` review-only pass:
  - timed out after 180 seconds
  - no second-opinion findings were available to incorporate

## Findings

- The compiler now assigns the memory writer from real foundation-provider availability instead of
  leaving the source-template xAI default in generated runtime output.
- The compiler also removes the hidden xAI dependency from Anthropic title generation in generated
  `librechat.yaml`.
- The actual local runtime file now reflects the fix, and a live backend/frontend pair is running
  against that regenerated runtime.
- Full release-suite green status was not achievable in this pass because unrelated failures already
  exist outside the compiler/memory surface.

## Residual Risks

- The canonical `bin/viventium start` path is currently blocked by an unrelated
  `public_https_edge` certificate timeout, so the live runtime verification had to use the narrower
  LibreChat backend/frontend start path instead of the full launcher.
- The review-only Claude helper still did not produce usable output in time.
