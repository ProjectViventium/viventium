# Source recovery publication — 2026-10-25

## Summary

QA: blast-radius. Source and build checks passed; installed-runtime acceptance was not run. This records the reviewed source and helper build, not activation of an
existing installation. The [runtime contract](../../../docs/requirements_and_learnings/capabilities/runtime-install-release.md)
and [xPerfect capability](../../../docs/requirements_and_learnings/capabilities/glasshive.md)
own the behavior and upgrade boundary.

## Scope Run

| Outcome | Evidence | Result |
| --- | --- | --- |
| Keep available services running during a dependency outage | Helper/CLI recovery, exact ownership and supervisor restoration cases; compiled Swift decisions and real Redis TCP, Unix-socket and verified TLS command checks | 305 affected cases passed; one existing host-process inspection case skipped |
| Preserve saved intent through upgrade and recovery | Exact prior-version shell, original and later helper formats, interrupted/failed upgrades, explicit Start, newer Stop, ownership and checkpoint cases | 387 distinct source checks passed across owning and causal repair runs |
| Ship the helper that matches its source | Existing fallback builder produced both macOS CPU slices; source and binary hashes, artifact checks and private-path scan | PASS |
| Select the reviewed worker source | Actual pinned-component bootstrap and strict validation; component selection, original-checkout preservation and native manifest/staging regressions | 81 checks passed |
| Keep release checks discoverable | Existing QA owner mappings and release-selection/public-safety regressions | 107 checks passed |
| Explain retained Telegram input without requesting duplicate work | [Telegram ingress report](../../telegram-channels/reports/2026-10-25-telegram-ingress-recovery.md) covers bot checks and its earlier source-matched user-path evidence | Scoped evidence retained |

Counts above describe separate, overlapping banks and must not be added. The 387-case result
reconciles the owning run with targeted repairs of stale test locators and binding checks;
failed earlier raw receipts remain private. Required native CI for the exact public candidate
is recorded on [the publication PR](https://github.com/ProjectViventium/viventium/pull/154).

## Automated Evidence

The helper checks cover recovery success, refusal, uncertain supervisor stop, failed activation,
rollback, intentional Stop, foreign ownership and escaped credentials. The Redis probe reports
command readiness; each write must still prove acceptance. Managed Core projects local Redis TCP
or its private native socket. This publication does not add an external Redis or custom-CA setup.
Review also caught an omitted process owner in the new no-group launch path. The enabled local
Google Workspace MCP now uses the existing stopped-owner repair decision, with the same checkout
and process-group checks. Thirteen causal cases cover missing, healthy, disabled and foreign
ownership; Docker-owned services keep their separate existing recovery.

Upgrade review found that an old controller could call the successor's ordinary Stop and
accidentally change saved intent. The existing verified handoff now preserves intent for that
internal operation. Explicit Start records its choice once before committed recovery; later
Stop is not reset by finalization. The original helper format remains valid without newer
intent fields. Both binding paths must be explicit absolute strings, so a missing field cannot
inherit the process working directory. Optional helper-state inspection during finalization
cannot become a new post-commit rejection for an ordinary legacy or path-alias configuration;
transaction, source and checkpoint checks remain required. Exact old-shell, rollback, interruption, foreign or
stale proof, and unchanged revision/counter checks cover these boundaries.

## Findings

The qualified intent paths are internal stops, protected validation and committed finalization.
A pre-existing rollback restoration can still write Running over a later Stop; that separate
recovery path was not rewritten or claimed fixed by this publication batch.

The source update does not install or restart a user's services. Installed helper UI, login,
reboot, permissions, notarization and a rebuilt Native payload were not tested by this publication
task. Standalone xPerfect package and provider evidence retains its own scope. Private source
snapshots, raw requests, logs, screenshots and machine details are excluded from this report.

## Traceability

`SDR-018` in the [stable runtime cases](../../stable-dev-runtime/cases.md) owns recovery,
intent and ownership. This source report proves its affected deterministic controls and built
helper identity; it does not mark the full installed journey passed. `CONT-010` and `CONT-012`
in the [continuity cases](../../continuity-ops/cases.md) own the exact predecessor handoff and
environment/helper preservation. This report adds isolated source proof for those controls;
their installed acceptance gates remain open.

## Full-View Evidence Checklist

The owning runtime and component docs are linked above. Source, test receipts, prebuilt hashes
and isolated configuration preservation were checked. User databases and active services were
not changed. New installed-helper browser/computer evidence and a new Native payload were not
part of this publication. The earlier Telegram path retains the linked report's exact scope.

## User-Grade Evidence

- Surface exercised: Isolated exact prior-version CLI processes, Start/Stop and recovery fixtures, compiled helper decisions and artifact inspection; no new installed helper UI run.
- Real user path: New menu-bar helper activation and recovery were not run in this source-publication task.
- Visible outcome: The rebuilt helper is qualified by its source and binary hashes; no new visible installed result is claimed.
- Expanded/detail state: Installed menu and detail views were not exercised for this publication.
- Persistence/reload result: Isolated configuration and selector bytes were preserved; user runtime reload was not run.
- Backend/log/DB confirmation: Isolated upgrade cases check preserved configuration, uploads, data and rollback state; private receipts record recovery/refusal. Live user databases were left intact.
- Final model/runtime wording check: Source selection and helper build are distinct from installed delivery, channel parity and provider readiness.
- Substitution check: Source tests, compiled decisions and review do not replace required installed UI, persistence or wording evidence.

## Public-Safety Review

Only sanitized behavior, test counts and limits are published. Raw prompts, credentials, personal
or client data, machine paths, runtime IDs, screenshots and raw logs remain private. The exact
public diff and helper binary were scanned before publication.
