# Fable 5 Extra Final Remediation Review — 2026-07-18

## Boundary And Verdict

This is the public-safe reconciliation of the final review-only Fable 5 pass at Extra effort. The
reviewer received the original user request and the full audit/remediation packet, with personal
tool paths and private values redacted. It was instructed not to edit, commit, push, publish,
restart, access personal databases, connect accounts, or mutate local/cloud state.

Verdict: **FAIL.** The audit is trustworthy, but the current product is not ready for the promised
nontechnical Easy Install. The lifecycle map, new-versus-established distinction, delivery
drift, and calibrated `PASS`/`PARTIAL`/`FAIL`/`BLOCKED` evidence were independently supported.

## Independently Confirmed

- The parent history, nested LibreChat history, component pin, local working tree, generated build,
  and installed/running surfaces are materially different and must be evaluated separately.
- Snapshot attempts are now immutable and helper/CLI wording distinguishes metadata from a
  recoverable payload; the rebuilt helper fallback matches its source hash and contains both
  supported architectures.
- Headless configuration has candidate/compile/backup/atomic-apply/rollback protection, while the
  interactive wizard, Keychain writes, and derived runtime effects remain outside that transaction.
- Existing-checkout bootstrap now rejects accidental wrong-origin, tracked-dirty, and clean
  local-ahead states, but it is not hostile-repository-safe or provenance-complete.
- Playground source has an explicit loopback bind; the broader network contract and live installed
  process remain unproved.
- Express prerequisite copy is now truthful, but live provider readiness is still not proven.
- Feelings discovery is correct in source and its clean patched build, but the nested commit, parent
  pin, shipped build, installed artifact, and authenticated user path are not aligned.
- The reviewer independently reran the pre-final focused suite at `89 passed`. After resolving the
  restore finding below, Codex reran the expanded aggregate at `91 passed`.

## New Finding Resolved In This Pass

`HIGH`: `LATEST_PATH` could point to a completed metadata-only audit, and restore followed that
pointer without checking the marker. A payload-less audit could therefore become the default
restore source.

Resolution:

- `scripts/viventium/restore.sh` now rejects both default and explicitly selected metadata-only
  directories before a live audit, safety copy, recall marker, or other restore-side state.
- Two synthetic regressions prove default-pointer and explicit-path refusal, public-safe wording,
  and absence of restore-side state.
- The installer, continuity, case, plan, and QA records now narrow the claim correctly: metadata
  truth and fail-closed selection are fixed; complete payload recovery remains `PARTIAL`/blocked.

## Remaining Findings And Required Treatment

### Medium — legacy marker-less metadata attempts

The new marker makes every future metadata attempt fail closed, but attempts created before the
marker contract may be indistinguishable from payload snapshots. The pre-fix fallback could also
rewrite a real snapshot's manifest, leaving stale payload under metadata-grade continuity evidence.
Slice 1 must use manifest/payload inventory evidence to classify or refuse this state and add a
synthetic legacy regression; filename or directory-shape guessing is not acceptable.

### High — hostile existing repositories

The current origin/revision checks protect against accidental mutation, not a malicious existing
`.git` directory. Repository-local hooks, filesystem-monitor configuration, same-origin spoofing,
the local-checkout fast path, and surviving untracked files remain unsafe. Slice 3 must use a clean,
hook-safe staging area plus immutable release verification and an install journal before the public
bootstrap is considered secure.

### Medium — loopback contract scope

`INST-013` covers every user-facing service, while the implemented patch pins only the modern
Playground. The frontend fallback, pre-existing wildcard listener handling, completion-banner URL,
behavioral socket denial, and documented LiveKit exception still need closure.

### Medium — Feelings delivery and merge order

The parent release contract reads nested working-tree source. Until the nested change is committed
and repinned, a clean manifest checkout fails that contract. Required integration order is nested
LibreChat commit, parent pin, client build/artifact verification, parent commit, installed artifact,
then authenticated browser QA. No such commit or publication was authorized in this audit.

### Medium — configuration transaction boundary

The direct helper validates YAML mapping shape; full schema/compiler validation lives in the CLI
orchestration. YAML reserialization can remove hand-edited comments, the parent directory is not
fsynced after replacement, and crash recovery/cross-side-effect compensation remain open. The
helper must not be described as a complete interactive or runtime transaction.

## Evidence The Reviewer Could Not Independently Confirm

The review did not independently rerun the disposable 9,577-module client build, nested 3/3 Jest
execution, anonymous browser redirect, installed-helper match, or the then-current full `976
passed, 7 skipped, 2 failed` suite. Codex's final expanded rerun reached `978 passed, 7 skipped, 2
failed` after adding the restore regressions. Those remain Codex evidence with their existing
limitations; Fable review is not a substitute for the missing clean-Mac, authenticated,
installed-artifact, or full-restore paths.

## Post-Fix Verification

Fable reviewed the bounded restore delta again after implementation and returned `PASS` for the fix
and its claim calibration. It independently ran the expanded focused aggregate (`91 passed`),
confirmed both tests execute the real restore script, verified refusal occurs before live-audit,
safety-copy, or recall-marker work, and agreed that `INST-005` must remain `PARTIAL`. Its only new
medium finding is the legacy marker-less classification gap above. The CLI wrapper was outside the
reviewer's bounded file list; Codex separately traced `bin/viventium restore` to the same restore
script after its normal CLI lock and App Support layout preparation.

## Final Priority Order

1. Obtain a disposable supported macOS target.
2. Complete and independently prove full-payload restore.
3. Complete interactive/Keychain and cross-side-effect configuration transactions.
4. Close hostile-bootstrap and whole-product loopback/network contracts.
5. Build the minimal account-first journey and unified live readiness model.
6. Integrate Feelings through the nested-pin-build-installed chain when commits are authorized.
7. Complete Telegram, then evaluate Slack and WhatsApp as separate roadmap adapters.
