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
| Ship the helper that matches its source | Existing fallback builder produced both macOS CPU slices; source and binary hashes, artifact checks and private-path scan | PASS |
| Select the reviewed worker source | Actual pinned-component bootstrap and strict validation; component selection, original-checkout preservation and native manifest/staging regressions | 81 checks passed |
| Keep release checks discoverable | Existing QA owner mappings and release-selection/public-safety regressions | 107 checks passed |
| Explain retained Telegram input without requesting duplicate work | [Telegram ingress report](../../telegram-channels/reports/2026-10-25-telegram-ingress-recovery.md) covers bot checks and its earlier source-matched user-path evidence | Scoped evidence retained |

## Automated Evidence

The helper checks cover recovery success, refusal, uncertain supervisor stop, failed activation,
rollback, intentional Stop, foreign ownership and escaped credentials. The Redis probe reports
command readiness; each write must still prove acceptance. Managed Core projects local Redis TCP
or its private native socket. This publication does not add an external Redis or custom-CA setup.
Review also caught an omitted process owner in the new no-group launch path. The enabled local
Google Workspace MCP now uses the existing stopped-owner repair decision, with the same checkout
and process-group checks. Thirteen causal cases cover missing, healthy, disabled and foreign
ownership; Docker-owned services keep their separate existing recovery.

## Findings

The source update does not install or restart a user's services. Installed helper UI, login,
reboot, permissions, notarization and a rebuilt Native payload were not tested by this publication
task. Standalone xPerfect package and provider evidence retains its own scope. Private source
snapshots, raw requests, logs, screenshots and machine details are excluded from this report.

## Traceability

`SDR-018` in the [stable runtime cases](../../stable-dev-runtime/cases.md) owns recovery,
intent and ownership. This source report proves its affected deterministic controls and built
helper identity; it does not mark the full installed journey passed.

## Full-View Evidence Checklist

The owning runtime and component docs are linked above. Source, test receipts, prebuilt hashes
and isolated configuration preservation were checked. User databases and active services were
not changed. New installed-helper browser/computer evidence and a new Native payload were not
part of this publication. The earlier Telegram path retains the linked report's exact scope.

## User-Grade Evidence

- Surface exercised: CLI fixtures, compiled helper decisions and artifact inspection; no new installed helper UI run.
- Real user path: New menu-bar helper activation and recovery were not run in this source-publication task.
- Visible outcome: The rebuilt helper is qualified by its source and binary hashes; no new visible installed result is claimed.
- Expanded/detail state: Installed menu and detail views were not exercised for this publication.
- Persistence/reload result: Isolated configuration and selector bytes were preserved; user runtime reload was not run.
- Backend/log/DB confirmation: Causal fixtures and private receipts record recovery and refusal; live user databases were left intact.
- Final model/runtime wording check: Source selection and helper build are distinct from installed delivery, channel parity and provider readiness.
- Substitution check: Source tests, compiled decisions and review do not replace required installed UI, persistence or wording evidence.

## Public-Safety Review

Only sanitized behavior, test counts and limits are published. Raw prompts, credentials, personal
or client data, machine paths, runtime IDs, screenshots and raw logs remain private. The exact
public diff and helper binary were scanned before publication.
