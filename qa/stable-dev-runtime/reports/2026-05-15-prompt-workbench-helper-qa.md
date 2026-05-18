<!-- qa-evidence-exempt: legacy or audit-style report; supersede with the standard run-report template on next rerun. -->
# Prompt Workbench Helper QA

Date: 2026-05-15

Environment: local development checkout with installed macOS helper refreshed from the shipped
prebuilt fallback.

## Scope

Verified the helper `Advanced > Prompt Workbench` submenu and the scoped Prompt Workbench lifecycle
commands. This report is public-safe and omits raw local paths, prompt text, private logs, and
machine identifiers.

## Results

Passed:

- `bin/viventium prompt-workbench start --json` started the standalone workbench on the reported
  loopback URL.
- `GET /api/health` returned `{"status":"ok"}`.
- `bin/viventium prompt-workbench stop --json` stopped the workbench listener and cleared the
  workbench status state.
- The main Viventium web listener stayed up after workbench stop, proving the workbench stop path
  did not invoke the main runtime stop path.
- The installed helper executable contains `Advanced`, `Prompt Workbench`,
  `helper-prompt-workbench.log`, and `prompt-workbench`.
- System Events menu enumeration showed top-level `Advanced`, then
  `Advanced > Prompt Workbench`, then submenu entries `Open`, `Start`, and `Stop`.
- A real helper submenu click on `Prompt Workbench > Stop` stopped the workbench only.
- A real helper submenu click on `Prompt Workbench > Start` restarted the workbench and showed the
  success dialog.
- A real helper submenu click on `Prompt Workbench > Open` from a stopped state started the
  workbench and opened the loopback URL.

## Automated Checks

Passed:

- `swiftc -parse-as-library -typecheck apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift`
- `python3 -m py_compile scripts/viventium/prompt_workbench.py`
- `npm run build` in `viventium_v0_4/prompt-workbench`
- `uv run --with pytest --with pyyaml python -m pytest tests/release/test_macos_helper_install.py tests/release/test_prompt_workbench.py tests/release/test_stable_dev_runtime_workflows.py -q`
  - Result: 54 passed.
- Focused compiler/stable-runtime regression:
  `uv run --with pytest --with pyyaml python -m pytest tests/release/test_stable_dev_runtime_workflows.py tests/release/test_config_compiler.py -q`
  - Result: 112 passed.

## Browser QA

Passed with Playwright:

- Opened `http://127.0.0.1:8781`.
- Verified title `Viventium Prompt Workbench`.
- Switched to the Prompt tab and confirmed rendered prompt detail loaded.
- Verified the primary dock shows one real visible tab row: Flow, Prompt, Live Drift, Drafts,
  Evals, and Frames.
- Verified no browser console warnings/errors.
- Verified workbench API requests returned `200`.

## Public-Safety Notes

The lifecycle state stores only PID, port, URL, start time, and repo binding metadata under local
App Support state. No raw prompt text, eval result bodies, private logs, local absolute paths, or
credentials are added to this report.
