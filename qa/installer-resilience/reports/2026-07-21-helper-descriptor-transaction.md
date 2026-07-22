# macOS Helper Descriptor Transaction QA — 2026-07-21

## Summary

`PARTIAL` for release acceptance. `INST-025` passes the synthetic source-level filesystem boundary;
the installed headed helper, Developer ID signature, and notarized release payload remain unrun.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-025` | `PARTIAL` | 30 helper tests | Filesystem transaction passes; signed headed path remains open |

## Traceability

- Feature: source-mode macOS helper install, replacement, recovery, and uninstall.
- Requirement: Requirements 39 helper ownership and rollback boundary.
- Use case: a new or existing user installs or removes the helper without risking another app.
- QA case: `INST-025`.
- Expected result: every mutation remains bound to the captured directory, app, and content identity.
- Actual evidence: the complete 30-test helper suite passes the scenarios below.
- Remaining gap or fix: signed/notarized installed-helper and headed login-item/TCC evidence.

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | What owns the expected result? | Requirement 39 and `INST-025` |
| Code owning path | What owns mutation? | helper installer plus descriptor transaction helper |
| Docs and nested docs/repos | Do docs match behavior? | Requirement 39 and installer-resilience cases updated; no nested repo changed |
| Scripts or harnesses | What executed it? | release helper test harness |
| Local/external prerequisite state | What dependency state was proven? | synthetic owner-controlled temporary directories only |
| Logs | What log evidence exists? | sanitized process exit and stderr assertions |
| DB/state/persistence | What persisted state was checked? | owner-only activation record and restored app bytes |
| Generated/shipped artifact | What artifact was verified? | source helper path; signed shipped artifact not run |
| Real user path | What user surface ran? | supported helper install/uninstall shell entrypoint in isolated subprocesses |
| Visual/UX comparison | Does UX evidence exist? | terminal refusal/recovery wording asserted; headed menu-bar UX not run |
| Not run / blocked | What remains? | signed headed helper, login item, Keychain/TCC, notarization |

## User-Grade Evidence

- Surface exercised: supported source helper install and uninstall shell entrypoint in isolated subprocesses.
- Real user path: clean install, owned upgrade/rollback, legacy migration, refusal, and uninstall.
- Visible outcome: terminal reports refusal or restoration without exposing an external sentinel.
- Expanded/detail state: staged app, backup, content fingerprint, and persisted activation record were inspected.
- Persistence/reload result: post-child recovery reloads the private record and restores exact prior bytes.
- Backend/log/DB confirmation: filesystem identities and bytes agree; no database applies to this boundary.
- Final model/runtime wording check: no model response applies; recovery wording does not claim headed success.
- Substitution check: automation supports the result but does not replace the unrun signed headed macOS path.

## Automated Evidence

```text
python -m pytest tests/release/test_macos_helper_install.py -q
PASS — 30 tests

bash -n scripts/viventium/install_macos_helper.sh
PASS

python -B scripts/viventium/helper_bundle_transaction.py --help
PASS on stock macOS Python 3.9

git diff --check -- scripts/viventium/helper_bundle_transaction.py scripts/viventium/install_macos_helper.sh tests/release/test_macos_helper_install.py docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md qa/installer-resilience/cases.md qa/installer-resilience/reports/2026-07-21-helper-descriptor-transaction.md
PASS
```

## Findings

- Missing Applications-directory creation is relative to an owner-validated parent descriptor.
- Stage, backup, activate, rollback, commit, and uninstall reopen the exact captured directory inode.
- Recursive fingerprints bind recognized current/legacy helpers and the staged candidate through deletion.
- Changed same-inode contents stop commit or uninstall and retain the changed app or backup.
- The owner-only activation record is durable before the transaction child returns; short writes loop.
- Failure after backup or state persistence restores the prior helper and clears stale recovery state.
- Parent/candidate replacement, symlink, and unrelated-app tests preserve synthetic external sentinels.
- No personal app/config/account, Docker state, VM, cloud service, or external message was touched.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, personal emails, account identifiers, or customer data.
- [x] No local absolute paths, hostnames, machine names, private stack traces, or raw runtime dumps.
- [x] All fixtures and sentinels are synthetic and temporary.
- [x] No commit, push, publication, cloud write, Docker action, or VM action occurred.
