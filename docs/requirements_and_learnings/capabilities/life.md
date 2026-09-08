# Life

## User promise

Life is an optional owner-controlled place for durable context and explicit connection intent. It
does not scan or ingest the user's files merely because setup named them.

## Setup

- **ONB-007:** Life has one owner-only enabled/path contract with legacy migration and safe
  bootstrap. The Mac helper exposes Setup, Open Life Folder, Choose Life Folders, and a plain-language
  explanation through that boundary without hardcoded or logged paths.

## Connect intent

- **ONB-008:** Connect Your Life is optional and skippable. Version 1 records explicit source intent
  and native folder choices without scanning, reading, uploading, indexing, ingesting, or falsely
  reporting a connection. It preserves user-authored text and tells remote users that folder choice
  occurs on the Mac.

## State and actions

- The Mac helper opens Life from its menu. It provides a native folder picker, an optional note,
  Save, Not now, Clear saved intent, and an enabled switch.
- `life_enabled` and `life_dir` in the existing provider configuration own setup state.
  A saved intent is one managed block in `Sources/WHAT_TO_CONNECT.md`; manual text remains intact.
- Clear removes intent. Disable also turns setup off and keeps the folder and personal content.
  Selecting source folders records intent only and does not change worker workspace authority.
- The owner-only API delegates to the same CLI owner. Remote callers can edit the note or state,
  but folder selection happens on the Mac.

## Boundaries

- A recorded intention is not a live connector, imported corpus, or authorization receipt.
- Paths are validated and owner-scoped and do not enter public docs, logs, process arguments, or
  provider prompts.
- Future ingestion requires its own explicit authorization, typed connection state, failure and
  recovery behavior, and real user QA.

## Owners and QA

- Template and bootstrap: `templates/life-v0.01/` and `scripts/viventium/life_bootstrap.py`
- Installer/helper configuration: `scripts/viventium/`
- Current cases: `qa/installer-resilience/cases.md`, especially the Life setup and intent journeys

Legacy implementation detail remains readable in
`39_Installer_and_Config_Compiler.md` until its archive and redirect gates pass.

## Detailed contracts

- [Installer and Config Compiler](../39_Installer_and_Config_Compiler.md)
