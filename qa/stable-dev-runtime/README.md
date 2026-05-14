# Stable Dev Runtime QA

## Scope

Owns QA for side-by-side Viventium developer runtimes, developer checkout activation, and helper
update-check UX.

## Owning Docs

- `docs/requirements_and_learnings/50_Stable_Dev_Runtime.md`
- `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`
- `docs/requirements_and_learnings/01_Key_Principles.md`

## Quality Bar

Acceptance must prove that local development can run without destabilizing the installed runtime,
and that heavy singleton services are not duplicated by default.

Public QA reports must use placeholders such as `/path/to/viventium` and
`~/Library/Application Support/...`; do not include raw logs or local absolute paths.
