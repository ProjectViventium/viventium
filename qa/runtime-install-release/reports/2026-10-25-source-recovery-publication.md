# Source recovery publication — 2026-10-25

QA: blast-radius. This records the reviewed source and helper build, not activation of an
existing installation. The [runtime contract](../../../docs/requirements_and_learnings/capabilities/runtime-install-release.md)
and [xPerfect capability](../../../docs/requirements_and_learnings/capabilities/glasshive.md)
own the behavior and upgrade boundary.

| Outcome | Evidence | Result |
| --- | --- | --- |
| Keep available services running during a dependency outage | Helper/CLI recovery, exact ownership and supervisor restoration cases; compiled Swift decisions and real Redis TCP, Unix-socket and verified TLS command checks | 305 affected cases passed; one existing host-process inspection case skipped |
| Ship the helper that matches its source | Existing fallback builder produced both macOS CPU slices; source and binary hashes, artifact checks and private-path scan | PASS |
| Select the reviewed worker source | Actual pinned-component bootstrap and strict validation; component selection, original-checkout preservation and native manifest/staging regressions | 81 checks passed |
| Keep release checks discoverable | Existing QA owner mappings and release-selection/public-safety regressions | 107 checks passed |
| Explain retained Telegram input without requesting duplicate work | [Telegram ingress report](../../telegram-channels/reports/2026-10-25-telegram-ingress-recovery.md) covers bot checks and its earlier source-matched user-path evidence | Scoped evidence retained |

The helper checks cover recovery success, refusal, uncertain supervisor stop, failed activation,
rollback, intentional Stop, foreign ownership and escaped credentials. The Redis probe reports
command readiness; each write must still prove acceptance. Managed Core projects local Redis TCP
or its private native socket. This publication does not add an external Redis or custom-CA setup.
Review also caught an omitted process owner in the new no-group launch path. The enabled local
Google Workspace MCP now uses the existing stopped-owner repair decision, with the same checkout
and process-group checks. Thirteen causal cases cover missing, healthy, disabled and foreign
ownership; Docker-owned services keep their separate existing recovery.

The source update does not install or restart a user's services. Installed helper UI, login,
reboot, permissions, notarization and a rebuilt Native payload were not tested by this publication
task. Standalone xPerfect package and provider evidence retains its own scope. Private source
snapshots, raw requests, logs, screenshots and machine details are excluded from this report.
