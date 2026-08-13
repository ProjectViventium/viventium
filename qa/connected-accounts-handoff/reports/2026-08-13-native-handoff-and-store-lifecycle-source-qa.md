# 2026-08-13 Native Handoff And Store Lifecycle Source QA

Status: **PASS** for merged nested source and automated regression gates. **PENDING** for installed
Telegram/browser QA after the parent pins are merged and activated.

## Escaped integration failures

Post-union QA exposed two narrow integration edges:

- worker-native tool ownership removed the configured Main-to-Connected Accounts graph topology;
- operational SQLite connections and detached provider reconciliation did not share one explicit
  shutdown lifetime.

The fixes preserve the existing product design. Native providers still own their ordinary tools;
only bounded Agent Builder transfer controls cross the graph boundary. The existing Store remains
the persistence owner, now with deterministic connection closure and an explicit lifetime WAL
connection.

## Merged nested candidates

- LibreChat: `541a4c4fdac97f54333d25a79de9c34e4319db04`
- GlassHive: `987c98b399c672cc45344b69c5dcb5e9612bdf9c`

## Automated evidence

| Surface | Result | Evidence |
| --- | --- | --- |
| Native handoff graph | PASS | Focused API and package suites cover tool isolation, VIEW authorization, missing/denied bidirectional targets, Main-to-specialist-to-Main final authoring, and recursion bounds. |
| SQLite lifetime | PASS | Full GlassHive runtime suite passed; deterministic regressions prove detached reconciliation is joined and every service loop is quiescent before Store close. |
| Independent review | PASS | Fresh reviews found no P0-P1 publication blocker. Lower-priority lifecycle observations were separately triaged against the shipped topology. |
| Privacy | PASS | Diff, credential, path, identity, and gitleaks scans found no candidate leak. |
| Installed Telegram/browser | PENDING | Requires the parent pin candidate to merge and activate before real user-path evidence is valid. |

## Required post-activation acceptance

1. Compare live agent A against the merged source B and local candidate C before any managed sync.
2. Reconcile only the reviewed graph/prompt fields while preserving protected user-managed fields.
3. Run one synthetic connected-account status request in Telegram and LibreChat Web.
4. Prove a single transfer, exact OAuth/tool evidence, return to Main, concise final output,
   `unfinished=false`, and committed delivery acknowledgement.
5. Refresh and restart, then repeat the status check and confirm persisted graph/runtime identity.

No private messages, account identifiers, credentials, logs, database records, or machine-specific
paths are included in this report.
