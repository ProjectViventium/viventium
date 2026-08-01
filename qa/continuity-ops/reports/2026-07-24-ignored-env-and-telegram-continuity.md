# Ignored Environment And Telegram Upgrade Continuity

<!-- qa-evidence-exempt: Synthetic private-state migration evidence; installed/browser proof remains explicitly pending. -->

**Date:** 2026-07-24
**Result:** PASS-ISOLATED / PARTIAL-INSTALLED

## Requirement

A source upgrade must not rotate LibreChat encryption/login secrets, discard unknown owner
customizations or helper preferences, or lose local Telegram preferences/pairings. Candidate
validation occurs before the outer commit, so it must not write the ignored LibreChat environment.
Rollback must restore exact prior files or prior absence.

## What Ran

`tests/release/test_librechat_env_upgrade_continuity.py`: `31 passed`.

`tests/release/test_macos_helper_install.py::test_install_honors_explicit_active_developer_checkout_in_documents`:
`1 passed`.

Broader affected regression evidence:

- full release suite: `1963 passed, 33 skipped`;
- final frozen affected owner-env, activation, launcher, Git/Native public-boundary,
  stable-runtime, and continuity matrix: `233 passed`;
- independent frozen fresh-clone/focused gate: `228 passed`;
- Python compilation, launcher/helper shell syntax, and `git diff --check`: pass.

The RED-to-GREEN suite uses temporary repositories and synthetic values only. It proves:

- exact ignored `LibreChat/.env` bytes and mode restore on rollback;
- an absent predecessor `.env` becomes absent again after rollback;
- symlink and ownership ambiguity fail before transaction registration/checkpoint;
- existing `CREDS_KEY`, `CREDS_IV`, `JWT_SECRET`, and `JWT_REFRESH_SECRET` field digests remain exact;
- Groq, XAI, Google, Microsoft 365, Foundry, Firecrawl, and adjacent owner credential digests remain
  exact even when those names also participate in generated runtime configuration; removal and
  rotation both fail commit;
- valid whitespace around `=`, `export`, quoted multiline values, and duplicate assignments are
  parsed into private digests, while malformed/unparsed lines fail closed instead of disappearing
  from the manifest;
- every launcher-unknown owner field remains exact while declared managed ports/database fields may
  advance;
- an established checkout promotion requires and prefers the previous active owner environment,
  rejects candidate conflicts, and permits explicit/private/candidate precedence only for a proven
  fresh activation; canonical config, runtime, helper, DB/schedule state, or continuity receipts
  without a trustworthy owner pointer fail closed rather than becoming “fresh”;
- activation checkpoints exact candidate bytes/mode/absence before mutation, reads the selected
  source once, revision-binds and digest-manifests it, and rejects concurrent changes. An absent
  target is created only after a transaction-owned file is complete and fsynced; an existing target
  must already be byte-exact and is never overwritten. The retained transaction link makes a
  partial-write crash recoverable before compile/doctor/start. The nested revision is rechecked
  through commit, and rollback restores exact candidate state across rollback/crash;
- publication requires the materialization artifact and candidate `.env` to share the exact planned
  inode, while post-start commit validates the artifact independently and semantically accepts the
  current target. Same-content atomic saves and declared managed-only changes may therefore commit;
  protected, provider, empty-assignment, and unknown-owner drift still fails closed. The original
  artifact is claimed with no replacement into a transaction-unique `0700` same-filesystem
  directory and revalidated by its own receipt. Terminal disposal validates through an open
  descriptor, zeroes only a detached single-link inode, and moves the source into bounded
  per-checkout retirement slots. Their canonical names are fixed across checkout moves and their
  terminal state is zero-byte and single-link. Digest-suffixed predecessor slots remain exact on
  failed activation/rollback, migrate only during successful post-core cleanup, and older
  in-progress journals that record those names remain recoverable. Cleanup never unlinks a possible owner-environment pathname, so a racing
  source replacement is moved and rejected rather than deleted, and an external-volume checkout
  does not require a cross-filesystem rename;
- rollback validates original-runtime/state checkpoint identity before mutation, atomically
  quarantines current candidate owner state, refuses a missing runtime backup at every publication
  phase, and preserves a concurrent post-quarantine edit. A detached materialization is retired in
  the same candidate-private directory only after its target checkpoint and receipt match, then
  atomically claimed and revalidated again before move-only retirement; rollback therefore has no
  candidate-to-App-Support rename and preserves racing replacements. Commit durably records the
  accepted owner inode/content boundary with an exact hard-linked target before its irreversible marker, and
    interrupted acceptance cannot be retried as a commit. A preserved post-acceptance owner edit is
    recorded and forces a running candidate through one more alignment restart before helper
    finalization; alignment uses the current candidate owner file as canonical and verifies the exact
    pre-restart bytes after health while allowing a safe same-content launcher inode replacement, so
    stale staged keys cannot resurrect owner deletions and an
    atomic save during restart remains pending; exact recorded inode identity safely retires
    transaction-only hard links even when their content advanced after the boundary;
- schema-v1 prepared, publishing, runtime-backed-up, and published activation receipts retain their
  bounded legacy rollback behavior; schema-v1 post-binding state remains deliberately fail-closed;
- complete `dev-runtime-activation.*` transaction roots are both ignored and rejected if force
  staged, and terminal successor-checkpoint cleanup revalidates a committed canonical
  `<App Support>/upgrade-backups/upgrade-*` ledger before deleting private files;
- persisted Meili, Google, code-interpreter, Firecrawl, protected auth, provider credentials, and
  unmanaged fields survive ambient/default conflicts while declared managed fields may advance;
- secret-capable generated env paths are independently ignored/rejected by Git staging, Native
  assembly/final verification, public continuity snapshots, and metadata audits; successful
  first-upgrade finalization removes its private successor checkpoint, preserves only known
  sanitized evidence, and retries incomplete cleanup;
- quiesced validation resolves missing/default secrets only in process memory and never calls file
  mutators;
- normal reconciliation prefers persisted protected values, including explicit empty assignments,
  over conflicting ambient/private values on repeated starts and keeps distinct LibreChat/code
  interpreter credentials distinct in the running process;
- App Support Telegram user preferences and Telegram-Codex pairings restore exactly and any
  precommit drift fails the private manifest gate;
- `helper-config.json` restores exact bytes/mode on rollback; commit allows only
  `runtimeSupervision` to advance and rejects changes to status-bar visibility, protected-folder
  permission, checkout binding, or unknown/future fields;
- the post-commit helper refresh preserves status-bar visibility, protected-folder permission,
  runtime supervision, and an unknown future field;
- the successor bridge checkpoints ignored `.env` before quiesced launch, binds its digest to the
  receipt, verifies again after a successful post-commit full start, and on proven drift stops the
  candidate and restores exact bytes without calling an unrelated runtime-health failure env drift;
- the same successor bridge checkpoints `helper-config.json` before the accepted predecessor can
  lose it, permits only `runtimeSupervision` to advance, and exact-restores status-bar,
  protected-folder, binding, and unknown/future fields on proven post-start drift.

The durable proof stores whole-file or aggregate-manifest SHA-256 plus per-protected-field digests.
It stores no secret, preference value, pairing value, or public local path.

## Not Yet Proven

- an installed established-user upgrade, browser refresh/login persistence, and a real Telegram
  preference/pairing round trip;
- legacy Telegram config fallbacks outside canonical App Support;
- external curated/private environment sources, legacy Microsoft 365 credential fallbacks, and
  Keychain references (the upgrade must not extract or rewrite Keychain secrets).

Until those user-path items pass, this evidence closes the isolated transaction and successor-bridge
behavior but does not by itself make the universal upgrade path fully finished.
