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

## Cataloged User-Grade Run Backlog

The catalogs below still contain user-grade cases that have never been run. They were explicitly
re-triaged on 2026-08-16 during the Parallel Work release audit: none is accepted as passing, none is
silently removed, and each remains due on the next owning feature run. This register expires after
90 days so old unrun work cannot remain invisible indefinitely.

| Case catalog | Last reviewed | Disposition |
| --- | --- | --- |
| `qa/agent-config-continuity/cases.md` | 2026-08-16 | Still unrun; requires protected live-vs-source sync and Agent Builder QA. |
| `qa/agent-streaming-usage/cases.md` | 2026-08-16 | Still unrun; requires browser stream, persistence, and usage evidence. |
| `qa/branding-assets/cases.md` | 2026-08-16 | Still unrun; requires installed helper and shipped-artifact QA. |
| `qa/citation-rendering/cases.md` | 2026-08-16 | Still unrun; requires headed browser citation expansion and persistence QA. |
| `qa/config-alignment/cases.md` | 2026-08-16 | Still unrun; requires source, compiled, live, and picker alignment QA. |
| `qa/config-compiler-memory/cases.md` | 2026-08-16 | Still unrun; requires compiled artifact and runtime memory QA. |
| `qa/config-compiler-xai-models/cases.md` | 2026-08-16 | Still unrun; requires compiled model inventory and runtime QA. |
| `qa/continuity-ops/cases.md` | 2026-08-16 | Still unrun; requires backup, restore, upgrade, and restart QA. |
| `qa/documentation-implementation-audit/cases.md` | 2026-08-16 | Still unrun; requires a fresh docs-to-runtime audit. |
| `qa/installer-piped-bootstrap/cases.md` | 2026-08-16 | Still unrun; requires a fresh public bootstrap install. |
| `qa/installer-resilience/cases.md` | 2026-08-16 | Still unrun; requires fresh install, preflight, doctor, and recovery QA. |
| `qa/installer-wait-taglines/cases.md` | 2026-08-16 | Still unrun; requires real installer wait-state UX QA. |
| `qa/listen-only-mode/cases.md` | 2026-08-16 | Still unrun; requires audible/visible listen-only surface QA. |
| `qa/mcp-oauth/cases.md` | 2026-08-16 | Still unrun; requires connected-account auth and stale-grant QA. |
| `qa/mcp-tooling/cases.md` | 2026-08-16 | Still unrun; requires real model-visible tool and failure-copy QA. |
| `qa/no-response/cases.md` | 2026-08-16 | Still unrun; requires Web, Telegram, and Voice silence/error QA. |
| `qa/red-team-cortex/cases.md` | 2026-08-16 | Still unrun; requires real activation, card, and final-answer QA. |
| `qa/release-readiness/cases.md` | 2026-08-16 | Still unrun; requires current candidate install and public release QA. |
| `qa/remote-access/cases.md` | 2026-08-16 | Still unrun; requires supported tunnel and disabled-state QA. |
| `qa/scheduling-cortex/cases.md` | 2026-08-16 | Still unrun; requires real schedule creation, execution, and delivery QA. |
| `qa/telegram-detached-api-stability/cases.md` | 2026-08-16 | Still unrun; requires installed detached Telegram API QA. |
| `qa/telegram-local-bot-api/cases.md` | 2026-08-16 | Still unrun; requires installed local Bot API QA. |
| `qa/telegram-media-downloads/cases.md` | 2026-08-16 | Still unrun; requires Telegram Desktop media transfer QA. |
| `qa/telegram-media-prereqs/cases.md` | 2026-08-16 | Still unrun; requires missing and restored media prerequisite QA. |
| `qa/telegram-settings-latency/cases.md` | 2026-08-16 | Still unrun; requires Telegram settings responsiveness QA. |
| `qa/telegram-voice-replies/cases.md` | 2026-08-16 | Still unrun; requires real Telegram voice reply QA. |
| `qa/voice-call-hardening/cases.md` | 2026-08-16 | Still unrun; requires audible provider-failure and recovery QA. |
| `qa/voice-streaming-first/cases.md` | 2026-08-16 | Still unrun; requires audible streaming latency and duplication QA. |
| `qa/voice-turn-taking/cases.md` | 2026-08-16 | Still unrun; requires audible interruption and turn-taking QA. |
| `qa/web-search/cases.md` | 2026-08-16 | Still unrun; requires real search, degraded provider, and fallback QA. |
| `qa/web-search-telegram/cases.md` | 2026-08-16 | Still unrun; requires real Telegram/browser search parity QA. |
