# WHOOP degraded-access recovery and Health Context isolation QA — 2026-08-18

## Summary

The installed local runtime again has authorized WHOOP access across all six official read families,
an active daily correction job, and a complete bounded Health Context snapshot. The downstream
Workbench failure was separately repaired: built-in Periphery runs now recover from GlassHive's
parallel-isolation rejection without weakening that policy, then return a validated private artifact
pair through the signed callback path.

## Root cause

| Layer | Evidence-backed cause | Resolution | Result |
| --- | --- | --- | --- |
| WHOOP acquisition | The prior provider grant had degraded; helper redirect/startup drift also made owner recovery less reliable. | Official owner consent was completed; the helper now uses the installed health callback, one supervised instance, and the registered custom-scheme redirect. | PASS |
| Health evidence | This was healthy before the later Workbench failure: the private snapshot reported complete provider evidence with no missing prerequisite. | No inference or archive workaround was added. The existing exact archive and rolling correction lane remain the source of truth. | PASS |
| Workbench execution | The saved definition requested host execution with a private host workspace, while GlassHive now requires untrusted parallel missions to run in isolation. The nested structured failure was flattened to a generic conflict. | Scheduling Cortex preserves the structured class, retries in Docker, rebases the declared output root, and records a required return contract. | PASS |
| Artifact return | An isolated worker cannot write directly into the host private folder; an early callback or briefly unavailable pair could otherwise become terminal. | The worker is bound before assignment; the signed callback claims the ledger, authenticates the artifact API request, validates the complete Workbench schema, imports only the recognized current-run pair, and retries transient return failures. | PASS |
| Worker restart | A live post-restart acceptance run exposed a Chromium Unix socket beneath the bind-mounted worker home. Recursive ownership repair attempted to change that socket on Docker Desktop and failed before inference. | Sandbox preparation now repairs regular paths without following links or changing socket ownership; the writable parent lets the worker replace stale endpoints. The exact live socket and a reusable regression both pass. | PASS |
| Telegram blast radius | The Telegram bot was running after restart, and recent bot evidence did not contain the WHOOP or parallel-isolation failure. The incident originated in the Workbench/GlassHive lane. | No Telegram-specific routing or prompt heuristic was added. Shared scheduler callback regressions remained green. | PASS |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: ongoing WHOOP acquisition and private Health Context correlation.
- Requirement: owner-scoped complete official coverage, daily corrections, isolated inference, and
  a validated private artifact return without prompt- or user-specific routing.
- Use case: an owner connects once, lets correction acquisition continue, and manually or
  automatically runs Health Context from Workbench.
- QA case: `PERI-010`, `PERI-019`, `PERI-021`, and `PERI-022`.
- Expected result: WHOOP stays connected; all six official families remain readable; a rejected host
  mission recovers in Docker; Workbench visibly shows a completed, readable, persisted artifact.
- Actual evidence: installed browser, public health CLI, scheduler and GlassHive ledgers, callback
  state, private permission metadata, automated regressions, and independent review agree.
- Remaining gap: a second real WHOOP owner, a real export ZIP, live revoke, public component-pin
  delivery, and a fresh-clone install were not run.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Requirement and use case | Owning Periphery requirements plus `PERI-010`, `PERI-019`, `PERI-021`, and `PERI-022` were reviewed. |
| Code owning path | OAuth/config/helper -> health archive and correction job -> Workbench snapshot -> Scheduling Cortex dispatch -> GlassHive worker -> signed callback -> artifact index. |
| Docs and nested docs | Key principles, architecture/system maps, health, Scheduling Cortex, Periphery, installer/runtime, and QA contracts were inspected. |
| Scripts or harnesses | Health, Scheduling Cortex, Prompt Workbench, API/UI, helper, release, and Docker-sandbox suites were run. |
| Local/external prerequisite state | WHOOP owner grant, all official resource families, native correction job, Docker, GlassHive, Scheduler, Workbench, Telegram, and helper were checked. |
| Logs | Sanitized runtime logs showed the socket failure, successful restart, completed inference, accepted callbacks, and Telegram recovery from an unrelated transient gateway error. |
| DB/state/persistence | Parent/child run states, worker/run binding, effective Docker mode, required two-file import, and reload persistence agree. |
| Generated/shipped artifact | Active local checkout, generated runtime, helper, health component pin, and built Workbench frontend were inspected; public nested-component delivery remains a separate gap. |
| Real user path | The installed browser was used to select Health Context, click **Run GlassHive**, wait for completion, open the accepted artifact, and reload. |
| Visual/UX comparison | Visible `completed` / `delivered`, validated/imported wording, complete snapshot, passed artifact, resolved sources, present Markdown, and **Hide** expanded state matched backend truth. |
| Not run / blocked | No second owner, live revoke, real export ZIP, public fresh clone, or public release/push was run; supporting evidence cannot replace required user-path evidence for those gaps. |

## Scope Run

| Use case | Actual evidence | Result |
| --- | --- | --- |
| Existing owner reconnects and stays connected | Installed Settings showed Connected after restart; public CLI reported authorized, no recovery required, and all six official families. | PASS |
| Ongoing correction acquisition | The native job remained configured and loaded for the documented daily time; its latest exit was successful. | PASS |
| Minimal-click onboarding for another owner | Provisioned installs retain one Connect action; unprovisioned installs retain the combined self-managed save/connect path. Client/scopes and user storage are config/identity driven. | PASS-AUTOMATED; no second real WHOOP owner was available |
| Complete supported data boundary | Official API families are cycle, recovery, sleep, workout, profile, and body measurement. Exact official export and manual screenshot lanes remain the supported hybrid for Journal and app-only evidence. | PASS-API / PARTIAL-LIVE-FILES |
| Real Health Context run | After the final runtime restart, browser **Run GlassHive** recovered from rejected host mode, completed in an isolated worker in 100.73 seconds, and showed `completed` / `delivered`. | PASS |
| Private artifact return | The exact worker and host copies matched; schema/module/current-run binding passed; both destination files were owner-only. | PASS |
| Visible readability and persistence | Workbench showed a complete snapshot, accepted `health_context` artifact, and explicit isolated-import success after reload. The execution card now labels the older field as the last *scheduled* disposition. | PASS |
| Missing/stale/unsafe return | Synthetic regressions reject wrong-run, traversal, symlink/hard-link escape, incomplete schema, missing/truncated pair, oversized content, custom-template authority, and incompatible memory modes; required import failure prevents memory/index side effects and remains retryable. | PASS |
| Owner-only boundary | The integration remains local-owner scoped; disabled or ordinary-user sessions cannot advertise or start the health tool. | PASS |

## Natural User Use Case Checklist

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `PERI-UC-001` | Open Workbench and inspect the latest private Health Context result. | Installed browser | PASS | Latest run showed completed/delivered, import success, passed artifact, readable expanded Markdown, and persisted after reload. | Scheduler and GlassHive ledgers, signed callbacks, exact pair, schema result, and owner-only modes agreed. | Public component release was not run. |
| `PERI-UC-006` | Keep a connected wearable current and run private context correlation. | Installed browser, health CLI, native scheduler, Workbench, GlassHive | PASS-ONGOING | WHOOP remained connected with daily corrections and all six official families; the fresh correlation completed. | Provider status, schedule state, bounded snapshot, Docker recovery, callback import, and artifact index agreed. | Real export, image lane, live revoke, and a second owner remain partial/not run. |

## User-Grade Evidence

- Surface exercised: installed Viventium browser, Prompt Workbench, public health CLI, native
  scheduler, GlassHive isolated worker, Telegram adjacency, and macOS helper.
- Real user path: selected Health Context, clicked **Run GlassHive**, observed completion, inspected
  the newest passed artifact with **Read**, confirmed its expanded **Hide** state, then reloaded and
  reselected the schedule.
- Visible outcome: the newest manual run showed `completed`, `delivered`, 100.73-second latency, and
  explicit validated/imported wording; the snapshot was complete and the artifact showed all source
  refs resolved with Markdown present.
- Expanded/detail state: the readable artifact added an expanded inline body and changed **Read** to
  **Hide** without exposing private content in this report.
- Persistence/reload result: after reload, the newest run, snapshot, passed artifact, source counts,
  and import wording remained visible.
- Backend/log/DB confirmation: Scheduler and GlassHive recorded completed success, exact worker/run
  binding, host-to-Docker recovery, three accepted callbacks, and a required successful two-file
  import; both files and all destination directories were owner-only.
- Final model/runtime wording check: Workbench did not claim another WHOOP logout or hide the prior
  failed attempt; it named the old sandbox failure and the new successful isolated import honestly.
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit
  tests are supporting evidence, not substitutes for any required visible-UI, detail-state,
  persistence, or wording step.

## Automated Evidence

- Real installed browser: post-restart WHOOP Settings, six-family coverage, daily-correction state,
  Prompt Workbench manual run, in-progress state, completed run detail, accepted artifact, and reload.
- Real runtime/state: component pin and nested source identity, active checkout, one helper process,
  provider status, native schedule status, GlassHive isolated worker, signed callback reconciliation,
  child and parent ledgers, exact paired-file comparison, schema binding, and private permissions.
- Automated: Scheduling Cortex `199 passed` plus `10 subtests`; Prompt Workbench/scheduled GlassHive
  `198 passed`; Viventium-Health `58 passed` with two opt-in live-provider tests skipped; focused
  health/Workbench/runtime/helper `50 passed`; connected-account/helper integration `12 passed`;
  WHOOP API routes `19 passed`; WHOOP Settings UI `11 passed`; all `133` Docker-sandbox tests and
  the GlassHive truncation regression passed. The complete `1502`-case GlassHive collection reached
  completion with two unrelated timing/concurrency cases failing once under the full load; both
  passed on immediate isolated rerun.
- Build/static checks: Prompt Workbench TypeScript and production build passed; Scheduling Cortex
  compile and relevant diff checks passed.

## Findings

- Defects: degraded provider authorization, structured isolation recovery loss, callback/import
  race exposure, and Docker Desktop socket ownership failure were identified and repaired.
- Regressions: no in-scope regression remained after the final live run and focused/full suites.
- Flakes: two unrelated GlassHive timing/concurrency tests failed once under the complete collection
  load and passed on immediate isolated rerun.
- Environment issues: `bin/viventium status` still names unrelated Memory Hardening and Conversation
  Recall action items; the WHOOP, Scheduler, GlassHive, Workbench, Telegram, and helper surfaces used
  here were running.
- Residual risks:

- Live disconnect/revoke was not run because the requested end state is ongoing access. Synthetic
  disconnect, expired-state, retry, and authorization-recovery coverage remains the safe lane.
- A second real WHOOP member was not available. Multi-user behavior is covered structurally through
  per-user credentials/state, local-owner audience gates, and synthetic role/onboarding tests.
- No real official export ZIP was supplied. The two original chat-attachment paths had expired by
  the final acceptance pass, so they were not fabricated or represented as imported evidence. The
  installed UI still exposes the private one-click screenshot lane and truthfully showed zero stored
  images; export and app-only image coverage therefore remain partial-live rather than API coverage.
- A new external fresh clone/public install was not run. This report accepts the installed local
  runtime, not a public release candidate or deployment.
- The active local checkout contains the fix and was restarted against it. Nested component changes
  remain uncommitted in a broader dirty development tree, so component-pin/public-release delivery
  is a separate gate and is not claimed here.

## Public-Safety Review

No credential, callback URL, raw health value, private prompt, chat content, account identifier,
record identifier, local absolute path, hostname, or private artifact body is recorded here.

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails,
  account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo identifiers, or
  raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports,
  App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, timestamps, and conclusions only.
