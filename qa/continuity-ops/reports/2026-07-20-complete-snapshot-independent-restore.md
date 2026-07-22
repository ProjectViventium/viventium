# Complete Snapshot and Independent Restore QA — 2026-07-20

## Summary

- Result: `PARTIAL` for the complete continuity release case; `PASS` for live snapshot, independent
  restore, browser recovery, canonical-state persistence, schedule recovery, and hostile isolation.
- Build/source under test: isolated public source-install release worktree transferred without
  credentials into a disposable Apple Silicon macOS VM.
- Runtime/artifact under test: real source-install services, distinct loopback Mongo targets, and a
  real Chromium browser using reserved synthetic data only.
- Private evidence: commands, logs, database names, account values, and screenshots stayed in an
  owner-only directory outside the public repo.
- Related change: complete logical snapshot capture, independent-target transactional restore, and
  restart-safe restored-runtime binding.

The supported CLI captured a complete bundle in about three seconds, restored it to a distinct empty
checkout/App Support/Mongo data path, compiled and started that target, recovered browser access by
the supported one-time password-reset flow, and preserved the visible answer and canonical state
through a full stop/start. The actual Recall rebuild remains blocked because the optional local RAG
service was unavailable. Provider/channel reconnect was deliberately not exercised in this isolated
continuity lane, so the complete release case remains `PARTIAL` rather than overstating acceptance.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CONT-001` | `PARTIAL` | Live CLI, Mongo, browser, schedule, and restart acceptance passed | Recall rebuild and provider/channel reconnect remain open here. |
| `CONT-004` | `PASS` | 49 focused tests plus live hostile-target and post-import fault runs | Existing, corrupt, symlink, nonempty, unclaimed, and misclaimed state failed closed. |
| `CONT-006` | `PASS` | Secret-exclusion automation plus real old-password refusal and supported reset | Recall stayed explicitly rebuild-required. |
| `CONT-005` | `PARTIAL` | 74 adjacent upgrade transaction tests passed in the prior focused run | Physical power-loss during an upgrade transaction and headed Docker restart remain separate gaps. |

## Natural User Use Case Checklist Run

| Natural user action | Real surface used | Result | Visible result | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Create a complete snapshot. | Supported source-install CLI against a running synthetic runtime | `PASS` | Command reported a complete, restore-eligible bundle. | Typed artifacts, hashes, logical collection counts, schedule integrity, and upload bytes agreed. | None for this path. |
| Restore without overwriting the source or another target. | Supported restore CLI to absent App Support/checkout and empty loopback Mongo | `PASS` | Restore reported explicit password/reconnect/Recall follow-up. | Independent database/data path, target-only files, runtime-selection ledger, and source backup hashes agreed. | None for target isolation. |
| Regain browser access and confirm recovered content. | Real Chromium login and supported one-time password-reset link | `PASS` | Old password was refused; reset succeeded; recovered history and the synthetic answer were visible. | DB queries confirmed the conversation, answer, saved memory, agent, file metadata, and new session. | Provider/channel reconnect was not run. |
| Restart and continue using recovered state. | Supported stop/start plus a fresh browser context | `PASS` | Login, history, and the same answer remained visible after restart. | Generated config matched the restore ledger; target Mongo identity/data path, upload hash, and database counts persisted. | None for canonical-state restart. |
| Resume schedules and Recall. | Live schedule health plus restored ledgers | `PARTIAL` | Schedule service reported healthy on the restored schedule database; Recall remained explicitly unavailable. | Seven synthetic tasks were present and the service database hash matched the restored target. Recall rebuild marker was present. | Actual Recall rebuild blocked by unavailable local RAG. |
| Reject unsafe or damaged recovery inputs. | Live CLI and real Mongo fault matrix | `PASS` | Unsafe inputs failed before activation or rolled back transaction-owned state. | Sentinels, target absence, database counts, claims, and rollback journals matched the expected outcome. | None for cases run. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: complete continuity snapshot and independent-target restore.
- Requirement: installer continuity contract in
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- Use case: capture durable canonical state, restore without overwriting existing state, recover
  browser access, restart, and resume against the restored target.
- QA cases: `CONT-001`, `CONT-004`, and `CONT-006` in `qa/continuity-ops/cases.md`.
- Expected result: canonical state is integrity-checked and restored transactionally; secret state
  is excluded; generated runtime binds to independent persistence; unsafe targets remain untouched.
- Actual evidence: 49 continuity tests, 141 compiler tests, a live source snapshot, live independent
  restore, browser recovery, full stop/start, schedule health, and nine live hostile/fault outcomes.
- Remaining gap: complete an actual Recall rebuild when the optional RAG service is available and
  exercise provider/channel reconnect in its owning synthetic lifecycle QA.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized evidence |
| --- | --- |
| Requirement and use case | Requirement doc 39; `CONT-001`, `CONT-004`, `CONT-006`; natural user checklist above. |
| Code owning path | `continuity_bundle.py`, `continuity_mongo.cjs`, `restore.sh`, `config_compiler.py`, snapshot wrapper, and public CLI dispatch. |
| Scripts and automation | Continuity bundle/audit, compiler, and adjacent upgrade transaction release suites. |
| Source safety | Original synthetic config hash and source revision were captured before mutation and reverified after an external VM interruption. |
| Snapshot | Complete owner-only bundle; four declared artifacts; config/Mongo/files/schedules captured; Recall and auth/channel recovery declared. |
| Generated runtime | Compiler selected the restored database, loopback port, independent data path, and fresh target-local internal secret from a strict owner-only ledger. |
| Browser/visual UX | Private screenshots were visually inspected for old-password refusal, password-reset success, recovered history/answer, and post-restart persistence. No screenshots entered the repo. |
| DB/state/persistence | Conversation/answer, saved memory, agent, file metadata, session recovery, upload hash, and seven schedule tasks matched after restart. |
| Schedule runtime | Healthy service reported the isolated profile and a database-path hash matching the restored schedule database. |
| Recall | Rebuild-required ledger present; actual rebuild `BLOCKED` because local RAG was unavailable. |
| Generated/shipped artifact | Source-install delivery path only; this report makes no signed, notarized, immutable-payload, or packaged-helper claim. |

## User-Grade Evidence

- Surface exercised: supported source snapshot/restore CLI, distinct local Mongo persistence,
  runtime compiler/start/stop, schedule service, and real Chromium browser.
- Real user path: capture a complete snapshot, restore it to an independent target, start, attempt
  the old browser password, use the supported one-time local reset, sign in, inspect recovered chat,
  stop/start, and sign in again from a fresh browser context.
- Visible outcome: the snapshot was reported restore-eligible; restore reported its mandatory
  recovery work; old credentials failed; reset succeeded; the same synthetic history and answer
  were visible before and after restart.
- Expanded/detail state: manifest domains/artifacts, restore ledger, generated persistence binding,
  reauthentication/Recall ledgers, schedule health, and target/source process identities were
  inspected. Metadata-only fallback remained a distinct non-restoreable result.
- Persistence/reload result: the full supported stop closed the target web/Mongo services without
  stopping source Mongo. Restart plus a new browser context preserved login recovery, history,
  answer, saved memory, agent, file metadata/upload hash, and seven schedule tasks.
- Local/external prerequisite state: target-local recovery installed the pinned Mongo runtime inside
  target App Support without Homebrew/system mutation. Optional local RAG was unavailable.
- Evidence retrieval classification, if applicable: local prerequisite unavailable for the actual
  Recall rebuild; schedule and canonical-state results were successful and nonempty.
- Fallback path, if applicable: Recall remained fail-closed behind its rebuild-required marker; no
  browser/computer fallback can replace the unavailable derived-index service.
- Backend/log/DB confirmation: generated config matched the strict restore ledger; database queries,
  upload hash, schedule database hash/task count, service health, and rollback sentinels agreed with
  the visible results.
- Final model/runtime wording check: no output claimed that passwords, provider/channel credentials,
  sessions, or Recall indexes migrated; the CLI required recovery, reconnect, and rebuild.
- Substitution check: browser-visible password recovery, history, answer, and post-restart state were
  run directly. Logs, DB rows, API responses, source inspection, and unit tests supported but did not
  replace those user-path results; they also do not replace the blocked Recall rebuild.

## Hostile And Failure Matrix

| Scenario | Result | Isolation evidence |
| --- | --- | --- |
| Payload tampered after capture | `PASS` refusal | Validation returned failure; target was never created. |
| Existing target with sentinel | `PASS` refusal | Sentinel hash remained unchanged. |
| Target App Support symlink | `PASS` refusal | Symlink destination remained empty. |
| Nonempty target database | `PASS` refusal | Existing sentinel document remained. |
| Drop requested without claim | `PASS` refusal | Database remained and adapter reported no drop. |
| Drop requested with mismatched claim | `PASS` refusal | Foreign claim and sentinel remained. |
| Fault after live Mongo import | `PASS` rollback | Target files, uploads, transaction stages, and claimed database were removed. |
| Real `SIGTERM` during active synthetic import | `PASS` automation | Transaction-owned state rolled back while unrelated state remained. |
| External VM interruption before final restore | `PASS` recovery | Owner-only QA root, original backup hash/revision, and private evidence persisted after reboot. |

## Automated Evidence

```bash
uv run --no-project --with pytest --with pyyaml python -m pytest \
  tests/release/test_continuity_bundle.py tests/release/test_continuity_audit.py -q
# 49 passed

uv run --no-project --with pytest --with pyyaml python -m pytest \
  tests/release/test_config_compiler.py -q
# 141 passed

uv run --no-project --with pytest python -m pytest \
  tests/release/test_cli_upgrade.py tests/release/test_upgrade_transaction.py -q
# 74 passed (adjacent prior focused run)
```

## Findings And Fixes

- The compiler originally ignored the restored database selection and could regenerate source
  persistence. A strict restore-selection ledger now binds database, port, data path, profile,
  canonical config, and generated output.
- Recursive target creation could leave intermediate state directories at mode `0755`. Every new
  restore-owned directory is now created explicitly at `0700`; payload files remain `0600`.
- Restore selected only a database name, leaving restart unable to reproduce the independent Mongo
  data path/port and leaving a redacted internal runtime secret. The `v2` ledger now records
  independent persistence and restore generates a fresh target-local internal secret without
  migrating provider/channel credentials.
- Live hostile cases confirmed database deletion is claim-gated and rollback deletes only
  transaction-owned state.
- No regression appeared in the 49 continuity or 141 compiler tests.

## Honest Remaining Gaps

- Actual Recall/RAG rebuild is `BLOCKED` until its optional local service is available; the explicit
  rebuild-required ledger and fail-closed state passed.
- Provider/channel reconnect is not a snapshot feature and was not run in this lane. Credentials
  remain intentionally excluded and the reauthentication ledger is present.
- Portable self-encryption, signed/notarized immutable payload delivery, and physical power-loss
  during a source-upgrade transaction are not proven by this report.
- The helper backup button was not part of this VM run; its source/binary contract remains covered by
  its owning installer/helper QA.

## Public-Safety Review

- [x] No secrets, passwords, cookies, tokens, reset URLs, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or
  customer data.
- [x] No raw IDs, Mongo exports, database names, source/target absolute paths, hostnames, machine
  names, or runtime dumps.
- [x] Raw evidence stayed owner-only outside the public repo; this report contains sanitized statuses,
  counts, timing, and conclusions only.
