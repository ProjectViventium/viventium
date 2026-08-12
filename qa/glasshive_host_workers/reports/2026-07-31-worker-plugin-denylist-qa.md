# Worker Plugin Denylist QA — 2026-07-31

## Result

PASS for the approved scope. Viventium host workers disable only configured canonical plugin IDs
through native Codex/Claude settings. Other plugins remain unchanged and no denylist text enters the
worker instruction.

## Evidence

- Canonical Viventium config compiled to
  `GLASSHIVE_HOST_PLUGIN_DENYLIST=viventium-feelings@project-viventium` in an isolated output folder.
- Compiler and wizard suites: 164 passed.
- Full GlassHive `test_profile_runtime.py`: passed.
- Real host Codex worker: passed; worker-local TOML disabled the selected ID and the provider run
  completed.
- Real host Claude worker: passed with one complete prompt; native `--settings` carried the selected
  disable and the provider run completed.
- Regression test proves a second synthetic plugin remains enabled, source/global config is not
  mutated, and neither worker instruction contains the denied ID.
- Scoped `git diff --check` passed; QA public-safety regression: 1 passed.

## Not Run

- Browser QA was not applicable because this change has no browser/UI surface.
- The installed private runtime checkout was not replaced or restarted; source and canonical config
  are ready for the normal promotion/restart flow.
<!-- qa-evidence-exempt: Historical or specialized supporting artifact retained without retroactively inventing missing evidence; current release acceptance requires a fresh full-view report. -->
