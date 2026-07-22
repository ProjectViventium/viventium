# Transactional Source-Install Upgrade Rollback QA — 2026-07-19

## Summary

`PARTIAL` for release acceptance; the implemented source-install transaction passes the complete
synthetic failure matrix in this report. A physical power-loss run and a headed real-Docker restart
failure remain separate release evidence requirements.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CONT-005` | `PARTIAL` | 9 transaction tests; 65 CLI upgrade tests | Synthetic matrix passes; physical interruption and headed Docker remain open |

## Traceability

- Feature: transactional source-install upgrade.
- Requirement: failed or interrupted upgrade returns the exact recognized stopped checkpoint.
- Use case: existing user runs `bin/viventium upgrade --restart` and a candidate phase fails.
- QA case: `CONT-005` / `CONT-UC-004`.
- Expected result: old source, config, runtime, database bytes, and running intent return.
- Actual evidence: focused transaction and CLI suites pass the matrix below.
- Remaining gap or fix: physical power-loss and real headed Docker/TCC recovery evidence.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What owns the expected result? | Requirement 39 and `CONT-005` |
| Code owning path | What owns the transaction? | public CLI and upgrade transaction helper |
| Docs and nested docs/repos | Do docs match behavior? | Requirements 39/50 and continuity QA updated; no nested code changed here |
| Scripts or harnesses | What executed it? | release transaction and CLI test harnesses |
| Local/external prerequisite state | What dependency state was proven? | synthetic bind and Docker-compatible named-volume adapters; real Docker blocked |
| Logs | What log evidence exists? | sanitized process results and ledger stages in temporary fixtures |
| DB/state/persistence | What persisted state was checked? | config/runtime/bootstrap/database bytes and volume content manifests |
| Generated/shipped artifact | What artifact was verified? | candidate runtime separation; no signed shipped artifact in this scope |
| Real user path | What user surface ran? | supported CLI orchestration in isolated fixtures; physical CLI run blocked |
| Visual/UX comparison | Does UX evidence exist? | terminal recovery wording asserted; no browser surface applies to helper logic |
| Not run / blocked | What remains? | physical kill/power-loss and headed Docker/TCC recovery |

## User-Grade Evidence

- Surface exercised: supported `bin/viventium upgrade --restart` CLI through isolated subprocess fixtures.
- Real user path: CLI invocation with running-state detection, stop, candidate failure, rollback, and recovery.
- Visible outcome: terminal says the verified previous runtime and running state were restored.
- Expanded/detail state: private transaction ledger stages and rollback status were inspected in fixtures.
- Persistence/reload result: next-invocation interruption recovery restores old bytes before new mutation.
- Backend/log/DB confirmation: Git heads, config/runtime/bootstrap files, database bytes, and volume manifest agree.
- Final model/runtime wording check: no model response applies; CLI does not call partial availability recovery a rollback.
- Substitution check: automation is supporting evidence, not a substitute for the blocked physical-Mac and headed-Docker user path.

## Findings

- Upgrade registers its journal, pins an immutable pre-pull transaction runner, and arms recovery
  before a running stack is stopped.
- Mutable product state is copied only after stop. Every copied file is hashed and the checkpoint is
  made read-only before source mutation.
- The checkpoint includes canonical config, generated runtime, runtime state, bootstrap Python,
  legacy Mongo state, native data, and App-Support-contained explicit Mongo storage.
- Bootstrap Python is the only checkpoint surface allowed to contain symlinks. Their link text is
  preserved and verified without following the link or changing the external target.
- The pre-stop runtime inventory distinguishes isolated/native bind storage from a `compat` Docker
  named volume. A named volume is archived with a cached Mongo image and compared through a
  per-entry content manifest before source mutation and after restore.
- Candidate config/runtime is compiled and checked separately, then activated only after doctor
  succeeds. Upgrade prerequisite handling is check-only; system package changes are outside the
  rollback promise.
- A known failed candidate restores parent/component revisions, exact stopped file/volume bytes,
  and prior running/stopped intent. A managed component first cloned during the failed attempt is
  moved into private transaction quarantine.
- An unrecognized new commit or tracked work makes rollback refuse before overwriting user state.
- The ledger explicitly records semantic data-migration reversal as `not_proven`; exact stopped-byte
  restoration is not misrepresented as proof for arbitrary forward-only migrations.

## Failure Matrix Actually Run

| Boundary | Injected result | Evidence |
| --- | --- | --- |
| pull | fetched target diverges; fast-forward fails | prior local commit and runtime bytes remain |
| prerequisite | candidate preflight check exits nonzero | rollback restores old config/runtime/database and restart intent |
| component bootstrap | bootstrap exits nonzero | same exact restoration |
| compile | candidate compiler exits nonzero | live runtime never activates; checkpoint returns |
| doctor | candidate doctor exits nonzero | candidate remains uncommitted; checkpoint returns |
| restart | candidate never reaches health before timeout | candidate is stopped, rollback runs, old health returns |
| interruption | active journal and mutated state exist on next invocation | next upgrade recovers first and exits `4` before new mutation |
| Docker Mongo | named-volume bytes changed and candidate-only file added | old bytes return and candidate-only file is absent |
| bootstrap venv symlink | interpreter link points outside the checkpoint surface | link text returns; external target bytes and mode remain unchanged |
| unknown local work | new clean commit appears after checkpoint | rollback refuses and leaves commit/config untouched |
| absent component | component is cloned into a path absent at begin | path becomes absent; full checkout remains in private quarantine |

## Automated Evidence

```text
python -m pytest tests/release/test_upgrade_transaction.py tests/release/test_cli_upgrade.py -q
PASS — 9 transaction tests and 65 CLI upgrade tests

python -m pytest tests/release/test_config_transaction.py -q
PASS — 10 tests

python -m pytest tests/release/test_qa_operating_contract.py -q
PASS — 23 tests

python -m py_compile scripts/viventium/upgrade_transaction.py
PASS

bash -n bin/viventium
PASS
```

No machine-level package installation, personal account access, cloud write, commit, push, or
publication occurred during this QA. All state payloads were synthetic and temporary.

## Remaining Evidence Gap

Automation proves the transaction logic and CLI orchestration, including a Docker-compatible volume
adapter. It does not substitute for forcibly terminating a real physical-Mac upgrade at every stage
or for a headed Docker Desktop/TCC run with a real Mongo volume and browser-visible post-recovery
answer. Those remain `PARTIAL`, not silently promoted to release-ready.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, personal emails, account identifiers, or customer data.
- [x] No conversation, message, session/call, Telegram, Mongo, or provider request identifiers.
- [x] No local absolute paths, hostnames, machine names, private stack traces, DB exports, or raw runtime dumps.
- [x] Private evidence is summarized only with public-safe counts, states, and conclusions.
