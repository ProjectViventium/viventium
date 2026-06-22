<!-- qa-evidence-exempt: legacy sanitized QA/RCA note retained for historical context; current acceptance must use cases plus a fresh v2 report. -->
# GlassHive Clean Worker Browser Chrome QA - 2026-06-16

## Scope

Verify `GHWATCH-010`: the worker desktop browser opens with clean browser chrome by default, without
the Debian bookmark bar and without the unsupported `--no-sandbox` command-line warning banner.

## RCA

- The runtime previously launched worker Chromium with `--no-sandbox`.
- After removing that launch flag, live QA still showed `--no-sandbox` because the
  Selenium-derived workstation image wraps `/usr/bin/chromium` and force-adds the flag.
- Launching the real Debian Chromium launcher without that wrapper initially failed because Docker's
  default seccomp profile blocked Chromium's user-namespace sandbox.
- Root fix: launch the user-visible worker browser through `/usr/bin/chromium-base`, create Docker
  workstation containers with the configured Chromium user-namespace security option, and prepare
  the worker profile so the bookmark bar is hidden by default.

## Source Changes

- `runtime_phase1/src/workers_projects_runtime/docker_sandbox.py`
  - centralizes Chromium launch arguments
  - uses `/usr/bin/chromium-base` by default
  - removes `--no-sandbox` from idle prime and browser desktop actions
  - prepares Chromium profile preferences with `bookmark_bar.show_on_all_tabs=false`
  - creates new worker containers with `seccomp=unconfined` so Chromium's user-namespace sandbox can
    initialize
  - recreates ready/terminal old containers that are missing the required browser sandbox substrate,
    while preserving mounted home/workspace state
- `docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md` and
  `viventium_v0_4/GlassHive/docs/10_Browser_Session_Persistence_and_Login_Model.md`
  record the browser chrome requirement and the Selenium wrapper/root substrate cause.
- `qa/glasshive_watch_desktop/cases.md` adds `GHWATCH-010`.

## Tests Run

- `uv run pytest tests/test_docker_sandbox.py -q`
  - Result: `33 passed`
- Disposable Docker worker smoke:
  - noVNC view health: healthy
  - Docker security option: `seccomp=unconfined`
  - `unshare -U`: exit `0`
  - Chromium process command lines containing `--no-sandbox`: `0`
  - Chromium profile preferences: `bookmark_bar.show_on_all_tabs=false`
- Playwright noVNC browser QA:
  - media evidence is legacy/exempt and not current public acceptance evidence
  - console after refreshed run: `0 errors`, `0 warnings`

## Visible Result

The refreshed noVNC browser summary showed the worker browser rendering the synthetic QA page with
no bookmark bar and no unsupported command-line flag banner. The address bar still showed normal
Chromium page/security UI for a `data:` URL, which is expected and unrelated to the reported issue.

## Residual Risk

Actively running pre-fix worker containers are not force-recreated to avoid killing live user work.
Ready, failed, cancelled, or interrupted containers are recreated on the next readiness path if they
are missing the Chromium user-namespace security option.
