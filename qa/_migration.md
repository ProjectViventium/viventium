# QA Legacy Migration Backlog

This backlog exists so the new QA folder standard is not paper-only. Legacy folders can keep their
current links, but the next meaningful change to a feature must migrate or explicitly update the
entry here.

Target shape:

- `qa/<feature>/README.md`
- `qa/<feature>/cases.md`
- `qa/<feature>/reports/YYYY-MM-DD-<topic>.md` for new dated reports

## Current Structural Gaps

As of the 2026-05-17 QA-system repair pass, every top-level feature QA folder has the standard
`README.md`, `cases.md`, and `reports/` home. New feature QA folders must keep that shape from the
first commit.

If a future audit finds a missing standard file, add a row here with the feature name, exact missing
file, and migration trigger. Do not bury structural gaps inside dated reports.

## Reports-Folder Cleanup

These folders already have the standard README/cases source-of-truth shape, or otherwise have enough
source-of-truth structure for current work, but still have legacy flat dated evidence. Keep old links
working; put new dated runs under `reports/` and retire or supersede the flat report during the next
related QA cleanup.

| Feature | Current Gap | Migration Trigger |
| --- | --- | --- |
| `background_agents` | Has standard folder shape; dated evidence is still mostly flat files | Next background-agent report cleanup |
| `meeting-transcript-memory` | Has `README.md`, `cases.md`, `reports/`, and evals, but a flat dated review remains | Next transcript-memory QA cleanup |
| `modern-playground-voice` | Has `README.md`, `cases.md`, and `reports/`, but legacy `report.md` remains | Next playground voice QA cleanup |
| `release-readiness` | Has standard folder shape; the dated public-push checklist is still flat | Next release-readiness QA cleanup |
