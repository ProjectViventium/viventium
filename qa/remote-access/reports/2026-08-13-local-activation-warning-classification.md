# Local Activation Warning Classification — 2026-08-13

## Summary

- Result: PARTIAL. The escaped activation-watcher defect is reproduced, isolated, fixed, and
  covered by a red/green regression. The supported transaction restored the established runtime
  after the false failure and every required local surface recovered.
- Build/source under test: an exact clean public-main checkout plus this focused ownership slice:
  CLI warning-severity classification and its synthetic regressions.
- Runtime/artifact under test: installed local-prod runtime using the supported activation command.
- Environment: established macOS local-prod installation with optional public remote access enabled.
- Remaining gate: repeat supported activation after the reviewed fix merges, then verify exact
  running provenance and truthful degraded remote status.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `REMOTE-005` | PASS-AUTOMATED / PARTIAL-LIVE | Red/green watcher regression; real supported activation and rollback | Post-fix activation remains. |
| `INST-019` | PASS for recovery | Transaction returned to the prior clean runtime and removed its recovery directory | No manual state edit or process kill was used. |

## Traceability

`public-edge degradation must not break local startup -> REMOTE-005 -> existing-user supported
activation -> local runtime remains available while remote status stays degraded -> red/green
watcher test plus rollback/recovery evidence -> post-fix activation pending`

The launcher owns the remote-verification warning and explicitly returns success so localhost can
continue. `launch_log_indicates_startup_failure()` owns the CLI watcher's fatal classification.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What contract applies? | `REMOTE-005`: optional public-edge degradation cannot roll back a healthy local runtime. |
| Code owning path | What owns the behavior? | public-edge verification -> launcher warning -> detached-start log -> CLI activation watcher -> transaction commit or rollback. |
| Docs and cases | Where is expected behavior recorded? | Remote-access requirement and this case/report. |
| Scripts or harnesses | What exercised it? | Real `dev-runtime activate-current --validate --restart`, supported transaction recovery, shell syntax, and focused release tests. |
| Local/external prerequisite state | Were dependencies available? | Local services started; remote verification was degraded and correctly remained optional. |
| Logs | What confirms the root cause? | The watcher stopped on the exact non-fatal `Remote access verification failed` launcher warning. |
| DB/state/persistence | What persisted? | Canonical state remained intact; transaction rollback restored the prior checkout and removed the interrupted transaction. |
| Generated/shipped artifact | What was checked? | Activation validated the clean checkout, generated config, helper, and exact component pins before restart. |
| Real user path | What was used like a user? | Supported installed-runtime activation followed by CLI status and local health checks. |
| Visual/UX comparison | Did the visible result match? | Before the patch the CLI falsely reported a stopped runtime; rollback then returned all required local surfaces. |
| Not run / blocked | What remains? | Post-fix activation from merged public main; signed-in browser and channel QA are separate gates. |

## User-Grade Evidence

- Surface exercised: installed Viventium activation and status CLI against the established local-prod
  runtime.
- Real user path: promoted an exact reviewed clean checkout with validation and restart; observed the
  false CLI failure; allowed supported recovery to restore the prior clean runtime; checked health.
- Visible outcome: the activation command reported a stopped candidate even though the launcher had
  submitted and started local services; recovery subsequently returned every required local surface.
- Expanded/detail state: the transaction record identified the previous checkout, running intent,
  rollback state, and pending helper restoration before completing and removing itself.
- Persistence/reload result: the prior clean checkout, helper intent, config, runtime state, and local
  services survived rollback.
- Local/external prerequisite state: local app surfaces were healthy after recovery; optional remote
  verification remained degraded.
- Evidence retrieval classification, if applicable: successful local runtime and transaction
  evidence; remote edge unavailable/degraded.
- Fallback path, if applicable: the supported rollback path, not manual source or App Support edits.
- Backend/log/DB confirmation: the exact warning preceded the watcher failure; all required local
  ports later listened; the interrupted transaction was removed. No database content was changed by
  this patch.
- Final model/runtime wording check: the launcher wording says browser links may need a retry and is
  non-fatal; the pre-fix activation result contradicted that wording. The patch aligns classification
  with the launcher contract.
- Substitution check: tests and source inspection support the real CLI activation/recovery evidence;
  they do not substitute for the pending post-fix activation.

## Automated Evidence

- Red first: the verification warning, persisted remote error, and unrelated optional-prefetch
  warning were falsely terminal before the fix.
- Green after fix: all three remote warning forms are clean, and a later red fatal is terminal.
- `tests/release/test_cli_upgrade.py`: `129 passed`.
- Stable-runtime plus remote-access release slice: `101 passed`.
- Shell syntax check passed.
- Public-safety/QA contract checks are run before publication.

## Findings

- Root cause: the watcher inferred severity from words such as `failed`, even though the launcher
  already marks warnings and deliberately continues through optional degradation.
- Fix: remove launcher warning-severity lines before generic fatal matching. This also closes the
  neighboring persisted-error branch and other optional fallback warnings without a growing
  message allowlist.
- Functional risk: low and bounded. Later red/plain fatal launcher evidence and explicit
  required-surface skips remain in the stream and still terminate the wait.
- Recovery: supported rollback restored the previous healthy clean runtime without modifying the
  original development workspace.
- Remaining gap: merge, activate the exact new main, and repeat provenance, health, and remote-status
  checks before calling this live pass complete.

## Public-Safety Review

- [x] No secrets, credentials, private URLs, private chats, or raw database rows.
- [x] No personal identifiers, local absolute paths, hostnames, or machine names.
- [x] Synthetic URL and warning fixtures only.
- [x] Raw logs and runtime state remain outside Git.
