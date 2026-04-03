# Installer Wait Taglines QA

## Scope

Verify the interactive installer startup wait UI keeps honest progress visible while rendering a
rotating playful tagline line with a fast type-in effect.

## Requirements Under Test

- The installer still shows the real startup step and pending surfaces during first-run wait.
- Interactive installs can show a second rotating tagline line without replacing the truthful status.
- Taglines type in quickly, hold for roughly five seconds, then rotate to another line.
- Headless/non-interactive behavior stays on normal progress logs.

## Environments

- Local repo checkout on macOS-compatible shell tooling
- Public-safe synthetic runtime state only

## Test Cases

1. Release test contract covers the new tagline state machine and progress renderer.
2. Focused shell harness proves the typewriter output reveals text incrementally and then settles on
   the full line.
3. Focused shell harness proves inline progress rendering still includes:
   - elapsed time
   - current step
   - waiting-on surfaces
   - tagline line
4. `bash -n` validates the modified CLI remains syntactically valid.

## Expected Results

- Installer wait helpers pass release tests.
- Render output contains both the honest progress line and the playful line.
- No shell syntax regressions are introduced.
