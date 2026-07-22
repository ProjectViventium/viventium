# Native Snapshot And Restore Transaction QA — 2026-07-20

## Summary

- Result: `PARTIAL` for release acceptance; `PASS` for the adversarial source transaction,
  activation/rollback process-loss matrix, shared bundle privacy integration, signed-Bootstrap
  pending-journal guard, and helper source/prebuilt alignment.
- Scope: immutable Native same-profile backup and restore only. Native in-place upgrade and
  source/Docker cross-profile migration remain unsupported.
- Data: synthetic, non-personal file and database sentinels only. No account credentials, private
  messages, raw logs, machine paths, or screenshots are included here.
- Delivery state: tracked source and a reproducible universal prebuilt helper are aligned; the exact
  assembled/signed artifact has not yet been accepted.

The Native CLI now creates a complete logical bundle through the installed payload's pinned
validator, Node runtime, LibreChat dependencies, and exact private Mongo socket. It publishes the
last-good pointer only after semantic and owner-only validation. Restore accepts only a Native bundle,
copies it through no-follow source descriptors into a hash-verified private input, stages a separate
socket-only Mongo data directory and file adapters on the App Support filesystem, proves every live
writer/listener/socket/open-handle is quiescent, then journals activation and resumable rollback of
five exact mutable roots. The immutable release pointer, generated Native runtime, helper binding,
and machine secrets are not in the replacement set.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `CONT-007` | `PARTIAL` | 204 combined affected release tests pass; reproducible universal helper checks pass | Source, shared bundle, bootstrap, assembler, and helper delivery alignment were run; exact installed CLI/helper/browser recovery remains unrun. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: immutable Native complete snapshot and same-profile restore.
- Requirement: Native continuity contract in
  `docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md`.
- Use case: Easy Install user creates a backup, restores it without a mixed state, then performs the
  explicitly required browser-password, account, channel, and Recall recovery.
- QA case: `CONT-007` in `qa/continuity-ops/cases.md`.
- Expected result: a complete health-checked restored state or exact prior-state rollback; no
  immutable release replacement or credential migration claim.
- Actual evidence: 26 focused Native continuity tests, 46 shared bundle tests, 132 adjacent
  bootstrap/payload/assembler/helper tests, injected activation and mid-rollback process loss,
  next-run exact-service recovery, and a successful helper Swift release build.
- Remaining gap: assemble the final exact candidate, run the installed CLI/helper path with
  synthetic data, and verify browser-visible persistence/recovery.

## Full-View Evidence Checklist

| Evidence surface | Required question | Result / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement, user case, and QA case is being proven? | Installer/config compiler requirement, Easy Install backup/restore use case, and `CONT-007`. |
| Code owning path | Which code path owns the behavior? | Native runtime/CLI, shared continuity bundle and Mongo adapter, payload assembler, and macOS helper source. |
| Docs and nested docs/repos | Which docs define expected behavior? | Installer/config compiler requirement, Native payload boundary, and continuity QA contract; no nested repo changed in this lane. |
| Scripts or harnesses | What exercised it? | Native continuity, shared bundle, bootstrap UI, payload/runtime, payload assembler, and helper installer release suites. |
| Local/external prerequisite state | What prerequisite was proven? | Python 3.12 and Swift build toolchains were available; final signed candidate and installed runtime were not. |
| Logs | What logs confirm or contradict the result? | Sanitized test totals and helper build conclusions confirm source/artifact alignment; installed helper logs were not created. |
| DB/state/persistence | What state confirms it? | Synthetic file/Mongo adapter sentinels, strict phase/flag assertions, full-checkpoint prevalidation, and crash-resume assertions prove transaction behavior; no personal state was read. |
| Generated/shipped artifact | What shipped artifact was inspected? | Universal helper is byte-aligned with its recorded digest and source digest and passed architecture, deployment-target, string-safety, and 19 helper tests; it is intentionally unsigned at this prebuilt boundary, and the exact signed payload remains unassembled. |
| Real user path | Which real path was used like a user? | Native CLI/help behavior was exercised with synthetic state; installed helper menu and browser recovery remain blocked on the final candidate. |
| Visual/UX comparison | Does visible behavior match? | CLI/helper wording contracts match the documented recovery steps; headed installed UX was not run, so acceptance remains `PARTIAL`. |
| Not run / blocked | Which surface was not run? | Exact assembled/installed Native snapshot, helper restore picker, browser-visible restored state, provider reconnect, and Recall rebuild. |

Supporting evidence cannot replace required user-path evidence. The installed helper/browser path is
still required before release acceptance.

## Happy And Unhappy Paths Run

| Path | Result | Public-safe evidence |
| --- | --- | --- |
| Public Native CLI advertises snapshot/restore | `PASS` | Assembled CLI contract includes both commands and still excludes source update/configure. |
| Snapshot success publication | `PASS` | Atomic owner-only pointer changes only for recoverable proof. |
| Snapshot capture failure | `PASS` | Prior pointer bytes remain unchanged. |
| Snapshot point-in-time boundary | `PASS` source automation | Proxy/API writers stop, only the owned private Mongo socket remains, and exact prior service state returns. |
| Invalid or changing snapshot | `PASS` refusal | Full private copy/hash/schema validation completes before journal creation or service stop; source inode/content change removes the stage. |
| Same-filesystem staged activation | `PASS` | Five exact mutable roots activate from the App Support filesystem. |
| Injected failure after partial activation | `PASS` | Old config, Mongo, uploads, schedules, continuity, and release-pointer bytes return. |
| Unfinished staging/activation journal | `PASS` | Next-run recovery removes only transaction-owned stage/checkpoint state and replays stopped/Mongo-only/full prior service intent. |
| Process loss during rollback | `PASS` | Durable per-root rollback state resumes when the prior root moved but its completion flag did not; final bytes match the pre-restore digest. |
| Corrupt journal/checkpoint | `PASS` refusal | Impossible phase/flag sequences and incomplete prior checkpoints fail before deleting another active root; wording does not claim untouched state after activation. |
| Missing/stale pid record | `PASS` refusal | Remaining port/socket/open-handle evidence blocks activation even without a usable pid record. |
| Schema/disk/time policy | `PASS` refusal | Incompatible data schema, insufficient disk, and bounded copy/adapter work fail closed. |
| Pending journal across signed install | `PASS` refusal | Bootstrap fails before download so a new release cannot interpret the installed release's journal. |
| Tool/provider secret exclusion | `PASS` | Python and Node remove casing/separator/acronym key variants and JSON-nested values; raw toolcall rows and tool result/argument plaintext are intentionally omitted. |
| Symlink, hardlink, unsafe mode | `PASS` refusal | Validation fails before the activation journal mutates live roots. |
| Different staging filesystem | `PASS` refusal | Activation fails before live mutation. |
| Shared Native Mongo adapter selection | `PASS` | Bundled Node and Native LibreChat package boundary are selected without a host Node dependency. |
| Helper backup/restore source | `PASS` source build | Native menu calls the same CLI and uses separate owner-local logs. |
| Helper shipped binary/source alignment | `PASS` | The universal binary contains `x86_64` and `arm64`, each targeting macOS 13.0; source/binary digests align, the private-string scan is clean, owner-only no-follow log contracts pass, and 19 helper tests pass. The prebuilt itself is not signed; signing/notarization remains a release-job gate. |
| Real installed helper and browser recovery | `BLOCKED` in this lane | Final candidate not assembled; source and helper-artifact evidence are not substituted for installed UX. |

## User-Grade Evidence

- Surface exercised: Native CLI contract and macOS helper delivery boundary with synthetic state.
- Real user path: CLI help/command behavior was exercised; the installed helper picker and browser
  recovery path were not run and remain `BLOCKED` on the exact candidate.
- Visible outcome: CLI exposes backup/restore with honest reconnect, password reset, Recall rebuild,
  and rollback wording; installed visual behavior remains unverified.
- Expanded/detail state: Restore validation and refusal details were asserted through the CLI
  transaction harness; helper dialogs were inspected in source but not headed on the installed app.
- Persistence/reload result: Synthetic next-run journal recovery and checkpoint persistence pass;
  installed stop/start and browser reload remain unrun.
- Local/external prerequisite state: Local build/test toolchains passed; exact assembled signed
  candidate, synthetic provider credentials, and Recall service were unavailable in this lane.
- Backend/log/DB confirmation: Synthetic state hashes, journal phases, adapter selection, and rollback
  assertions pass; no personal DB, raw logs, or credential state was inspected.
- Final model/runtime wording check: CLI/helper strings do not claim that excluded credentials or
  Recall state migrated, and they require the supported recovery actions.
- Substitution check: logs, state assertions, source inspection, and tests support the result but do
  not replace the required installed helper, browser-visible, persistence, or recovery evidence.

## Automated Evidence

```bash
python -m pytest tests/release/test_native_continuity.py -q
# 26 passed

python -m pytest tests/release/test_continuity_bundle.py -q
# 46 passed

swift build
# ViventiumHelper source build passes

python -m pytest tests/release/test_macos_helper_install.py -q
# 19 passed

python -m pytest \
  tests/release/test_native_continuity.py \
  tests/release/test_continuity_bundle.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_native_bootstrap_ui.py \
  tests/release/test_native_payload.py \
  tests/release/test_native_payload_assembler.py -q
# 204 passed
```

The rebuilt helper passed clean-install preference, source-marker, and source-digest alignment. Its
two architecture slices each declare the documented macOS 13.0 minimum, and a public-safety string
scan found no private identifiers or machine-local paths.

## Findings

- Defects fixed in this pass: incomplete journal-state validation, checkpoint deletion before full
  rollback-source proof, non-resumable rollback renames, lost prior service intent, pid-file-only
  quiescence assumptions, validation/use races, unbounded resource work, missing schema binding,
  incomplete structured-secret variants, raw tool-result leakage, unsafe helper log opens, and
  cross-release pending-journal bootstrap.
- Regressions: None in the 204-test combined affected suite.
- Flakes: None observed; two helper rebuilds produced byte-identical output.
- Environment issues: The exact assembled/installed candidate and headed browser/helper environment
  were not available for this lane.
- Residual risks: Installed transaction behavior, visible helper recovery, provider/channel
  reconnection, Recall rebuild, signing, and notarization remain separate release gates.

## Security And Continuity Properties

- Snapshot and restore use allowlisted logical Mongo collections. Provider keys, OAuth/session
  tokens, action/MCP/plugin credentials, channel credentials, browser passwords, the raw toolcalls
  collection, and embedded tool argument/result payloads are excluded. This intentionally sacrifices
  tool-transcript fidelity because arbitrary tool plaintext cannot be proven credential-free;
  ordinary owner-only chat message text remains preserved.
- Native Mongo capture/import uses only an exact owner-checked Unix socket. The staged Mongo process
  must own that socket and have no TCP listener.
- Snapshot, stage, active roots, journal, checkpoint, and payload files reject foreign ownership,
  symlinks, hardlinks, special files, and group/world permission bits.
- Activation and rollback pending/completed flags are durable around each rename, including both
  parents and transaction directories. A local pre-restore checkpoint remains after successful
  commit; it is owner-only and not described as portable self-encryption.
- A running prior runtime is restarted and health-checked before commit. Failure triggers rollback
  and prior-state restart. An unfinished journal is recovered before a later lifecycle command.
- `native-runtime.json`, runtime environment, helper binding, machine secrets, and the immutable
  release tree never enter the replacement list.
- The helper opens logs with owner-only directories and `O_NOFOLLOW`, verifies regular-file owner,
  link count, and mode through the descriptor, and refuses unsafe targets.

## Honest Remaining Gaps

- Assemble the exact Native payload and independently verify the bundled validator/adapter, CLI,
  helper binary, and immutable release metadata match this source.
- Run a complete installed Native user path with synthetic chats/files/schedules: snapshot, mutate,
  restore, supported password reset, visible browser state, stop/start persistence, and helper alerts.
- Run actual provider/channel reconnection and Recall rebuild in their owning synthetic lifecycle QA.
- Signed/notarized release and physical interruption evidence remain separate release gates.

## Public-Safety Review

- [x] No secrets, reset links, cookies, tokens, credentials, or credential-bearing commands.
- [x] No personal data, customer data, private conversations, raw database rows, or screenshots.
- [x] No usernames, hostnames, machine names, absolute private paths, or connection details.
- [x] Findings distinguish source proof, shipped-artifact proof, and real user-visible proof.
