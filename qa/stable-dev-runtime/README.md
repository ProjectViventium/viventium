# Stable Dev Runtime QA

## Scope

Owns QA for side-by-side Viventium developer runtimes, developer checkout activation, helper
update-check UX, and helper utility controls that must stay separate from the main runtime.

## Owning Docs

- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`

## Quality Bar

Acceptance must prove that local development can run without destabilizing the installed runtime,
and that heavy singleton services are not duplicated by default.

Public QA reports must use placeholders such as `/path/to/viventium` and
`~/Library/Application Support/...`; do not include raw logs or local absolute paths.

## New Contributor Orientation

When testing this area, treat the installed helper/runtime as **local prod** and any `dev-env` as
an optional side-by-side developer runtime. QA must prove the app-facing surfaces can separate while
the expensive singleton services stay shared by default.

Minimum evidence for dev/prod coexistence:

- `bin/viventium dev-env status <name>` shows offset app-facing ports
- generated dev config records `runtime.dev_env.enabled`
- generated dev config records shared singleton services
- shared singleton services are not started a second time by default
- `bin/viventium dev-runtime status` shows the installed runtime checkout separately from the dev env
- `bin/viventium dev-runtime activate-current --validate --restart` uses runtime-checkout state and
  does not copy source into an install path
- helper utility actions such as `Advanced > Prompt Workbench > Stop` do not invoke or affect the
  main stack stop path
