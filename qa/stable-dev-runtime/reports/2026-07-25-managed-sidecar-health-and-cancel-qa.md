# Managed Sidecar Health And CLI Cancellation QA - 2026-07-25

## Summary

- Result: `PARTIAL`
- Build/source under test: local universal-upgrade hardening candidate
- Runtime/artifact under test: compiled local-prod runtime and real managed sidecars
- Environment: local macOS runtime with protected user state
- Tester: Codex plus focused automated harnesses
- Related change: managed-sidecar health contracts and terminating CLI signal traps

The live activation exposed two related false-health paths. Scheduling Cortex and GlassHive were
healthy but the activation gate required RAG's literal `status: UP` instead of their documented
`status: ok`. The stricter follow-up also proved that Scheduler readiness must derive the launcher's
default ledger from runtime state root when no explicit DB variable is generated, while GlassHive
must probe the local runtime API rather than its user-facing operator URL, which may be public.
During the first wait, `SIGINT` and `SIGTERM` released the CLI lock but returned to the polling loop.
These contracts are repaired and regression-covered; post-fix browser and continuity acceptance
remain pending in this report.

The next healthy retry exposed a third fail-closed logic defect at the final owner-environment
boundary: successful predecessor `verify-source` was accidentally used as the rollback condition.
The transaction restored every protected baseline exactly. The predicate is now explicitly
negated, so unchanged authoritative state proceeds while actual source drift still fails closed.

That retry then exposed an activation-owned helper conflict: the restart branch restored
`desiredState=running` before the transaction committed even though quiescence still required
`stopped`. Commit correctly rejected the write. Candidate restart now leaves the helper quiesced;
the existing commit path restores the owner's prior supervision values after acceptance.

The following live retry proved a separate cross-version variant: the already-installed older
helper retained its pre-activation supervision in memory and could rewrite the quiesced fields
during candidate restart. The visible managed view later converged back to `stopped`, so weakening
the receipt check would have hidden a real race. Activation now journals and pauses only the exact
Viventium helper bundle process, rejects resurrection at publication and commit, restores a
previously running helper on every rollback/recovery path, and refreshes the new helper after core
commit. Follow-up adversarial review additionally closed PID reuse before signalling, made the
receipt mandatory for macOS schema-v2 activations, records the exact predecessor bundle path,
and retains a retryable rolled-back journal until exact relaunch is proven. Synthetic process QA
passes. The first real retry with that design proved the helper process stayed paused but exposed
the actual remaining writer: the detached candidate `start` child recorded ordinary user
`running` intent. The transaction rolled all protected baselines and the exact predecessor helper
process back successfully. Internal candidate/recovery starts now carry an explicit preserve-intent
flag while ordinary starts retain their existing behavior; another real activation remains the
acceptance gate.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `SCHED-018` | `PASS-AUTOMATED/PARTIAL` | Focused CLI regression and real pre-fix endpoint probe | Post-fix browser proof pending |
| `SDR-012` interruption/recovery lane | `PASS` | Real interrupted activation journal recovered to predecessor | Canonical user data was not edited |
| CLI signal cleanup | `PASS` | Synthetic process exited `143` and removed its owned lock | Signal status is explicit |
| Owner source commit boundary | `PASS-AUTOMATED/PARTIAL` | Failure-first predicate regression and exact live rollback hashes | Post-fix activation rerun pending |
| Helper quiescence through restart | `PASS-AUTOMATED/PARTIAL` | Failure-first source regression and exact live rollback hashes | Post-fix activation rerun pending |
| Legacy helper process quiescence | `PASS-AUTOMATED/PARTIAL` | Exact-executable/start-identity termination, PID-reuse, resurrection, and durable exact-restoration regressions plus exact live rollback hashes | Real post-fix activation rerun pending |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `STABLEDEV-UC-006` | Promote a local checkout with validation and restart | Real `bin/viventium dev-runtime activate-current` CLI | `PARTIAL` | Core surfaces started; progress falsely remained on sidecar readiness before the fix | Real health responses and durable activation state identified the mismatch | Rerun post-fix to completion |
| `SCHED-UC-004` | Open Scheduling Cortex after local runtime restart | Browser plus Scheduler endpoint | `PARTIAL` | Pre-fix browser showed unavailable; post-fix browser not yet run | Endpoint returned the documented identity-bearing healthy payload | Post-fix visible and refresh evidence |
| Managed cancellation | Interrupt a long-running activation | Real CLI process and recovery command | `PASS` | First attempt reproduced ignored signals; the next post-fix activation exited `143` on `SIGTERM` | Both durable journals recovered and active binding converged to the predecessor | None for cancellation/recovery |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: stable local-prod promotion and managed-sidecar readiness
- Requirement: service-specific semantic health, exact Scheduler ownership, interruptible CLI
- Use case: activate the latest checkout, observe Scheduling Cortex, or cancel safely
- QA case: `SCHED-018` and the interruption/recovery lane of `SDR-012`
- Expected result: healthy services satisfy readiness; foreign state does not; signals exit non-zero
- Actual evidence: pre-fix real failure reproduced, focused regressions pass, durable recovery passed
- Remaining gap or fix: complete post-fix activation, browser refresh, and continuity comparison

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Stable-runtime service readiness and cancellation; `SCHED-018`, `SDR-012` |
| Code owning path | Which code path owns the behavior? | Public CLI JSON health functions, activation wait loop, and signal traps |
| Docs and nested docs/repos | Which docs or nested repo docs define the expected behavior? | Stable runtime requirements, Scheduler README, Scheduler QA cases |
| Scripts or harnesses | Which scripts, fixtures, QA harnesses, or automated suites exercised it? | Focused CLI upgrade tests and shell signal harness |
| Local/external prerequisite state | Which required local service was proven healthy or degraded? | Local Scheduler, GlassHive operator/UI, core API/web/playground, and voice endpoints responded |
| Logs | Which sanitized logs confirm or contradict the result? | Startup log showed candidate processes; no raw log content is retained here |
| DB/state/persistence | Which sanitized state or DB identity confirms it? | Identity-bearing Scheduler health and durable activation journal recovery |
| Generated/shipped artifact | Which generated config or installed artifact was inspected? | Generated runtime flags, derived Scheduler ledger, local GlassHive ports, public operator origin role, and owner manifest |
| Real user path | Which browser, CLI, scheduler, or GlassHive path was used like a user? | Real CLI activation/cancellation and pre-fix browser Scheduler state |
| Visual/UX comparison | Does the visible UI/UX match the expected behavior? | `PARTIAL`: pre-fix unavailable state matched the bug; post-fix browser pending |
| Not run / blocked | Which required surface was not run? | Post-fix browser detail/refresh and final continuity comparison |

Supporting evidence cannot replace required user-path evidence. The final classification stays
`PARTIAL` until the post-fix browser path is run.

## User-Grade Evidence

- Surface exercised: real local-prod CLI activation, browser Scheduling Cortex state, and live local health endpoints
- Real user path: started checkout promotion through the public CLI and interrupted the stuck operation
- Visible outcome: core startup completed, but activation and the pre-fix browser falsely reported managed-sidecar unavailability
- Expanded/detail state: endpoint detail proved Scheduler service and ledger identity while the CLI still rejected its status
- Persistence/reload result: both interrupted attempts recovered their durable journals and predecessor binding; post-fix browser refresh is pending
- Local/external prerequisite state: local managed services were reachable; no cloud mutation was used
- Evidence retrieval classification, if applicable: successful healthy responses were misclassified by the readiness predicate
- Fallback path, if applicable: direct local endpoint and state inspection isolated the mismatch after visible CLI/browser failure
- Backend/log/DB confirmation: sanitized health fields, configured ledger hash comparison, and activation status agreed
- Final model/runtime wording check: `PARTIAL`; no final success wording is allowed until post-fix user-path QA
- Substitution check: logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.

## Automated Evidence

```bash
uv run --with pytest --with pyyaml pytest tests/release/test_cli_upgrade.py -q
bash -n bin/viventium
git diff --check
```

## Findings

- Defects: literal health-status drift, missing Scheduler default derivation, wrong GlassHive health origin, non-terminating CLI signal traps, an inverted owner-source commit predicate, premature helper-intent restoration, and stale in-memory supervision from a legacy installed helper
- Regressions: failure-first tests now cover real `ok` health, Scheduler identity, signal exit, lock cleanup, exact helper-process termination, resurrection rejection, and rollback restoration wiring
- Flakes: none observed in focused tests
- Environment issues: the original activation had to be recovered before applying the source fix
- Residual risks: post-fix activation, browser refresh, and continuity comparison remain mandatory

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
