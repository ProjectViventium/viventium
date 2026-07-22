# Native Payload Production Integration QA — 2026-07-19

## Summary

- Result: **PARTIAL.** Production release remains blocked.
- Build/source under test: local Native payload verifier, deterministic compressed builder,
  relocatable assembler/runtime, bundled-Python bootstrap source, candidate producer, bootstrap
  hand-off, and protected draft-release workflow.
- Runtime/artifact under test: synthetic unsigned `local-qa` ZIP/manifest built by the real CLI,
  staged and activated into an isolated temporary install root.
- Environment: local arm64 macOS development host with synthetic public-safe files; no release
  credentials or personal runtime state.
- Tester: Codex implementation pass plus separate review-only model pass.
- Related change: immutable Native payload build/activation and fail-closed production integration.
- Decision: no public Native payload was signed, notarized, published, downloaded, or installed. A
  later provisional exact local-QA payload ran in a disposable vanilla guest and was rejected on a
  production startup failure before registration; see the July 20 addendum. This remains release
  evidence, not public-release acceptance.

## 2026-07-20 Provisional Exact-Payload Addendum

### Result

- Result: **FAIL.** The provisional payload failed and production release remains blocked.
- Candidate boundary: unsigned local-QA payload built from the provisional nested LibreChat commit
  ending `039fb75f`. That component selection was subsequently unfrozen for a separate portability
  defect, so it is not the replacement candidate.
- Isolation: a disposable vanilla macOS guest with dedicated synthetic Viventium state and a
  controlled local-QA artifact hand-off. No personal accounts, files, credentials, or cloud
  operations were used.
- Public hand-off result: PASS. With production trust intentionally unprovisioned, Native selection
  refused source fallback before any install mutation.
- Direct local-QA payload result: install completed and bundled MongoDB started; application startup
  failed before registration. No provider, first answer, persistence, browser, recovery, upgrade, or
  uninstall acceptance can be inferred from that run.
- A later headed diagnostic run continued only with synthetic, test-scoped workarounds and found
  three additional independent source defects: the Native CLI omitted local password recovery; the
  one-time first-admin page was blocked by its own CSP and omitted password confirmation; and the
  account-connection UI was disabled because capability discovery depended on provider-secret
  sentinels intentionally absent from Native. These findings invalidate that payload; the source
  corrections require a newly built exact payload and a full rerun, not an artifact patch.

| Case ID | Result | What is proven now | Remaining gate |
| --- | --- | --- | --- |
| `INST-016` | FAIL | The provisional exact payload exposed missing runtime dependency, recovery, first-admin, and account-capability behavior. Focused structural source regressions now pass. | Rebuild and run the replacement exact payload through the full pristine lifecycle. |
| `INST-027` | FAIL | The provisional payload failed; structural regressions for package ownership/prune/load plus cookie-bound first-admin recovery, confirmation, `/register` interception, replay, and retry pass. | Registration, direct-port closure, DB/default-agent, restart, Connected Accounts, and browser proof on the replacement payload. |
| `INST-028` | PARTIAL | The corrected provisional payload passed exact whole-payload public-safety scanning. | Rebuild and rescan after the newly frozen nested commit; prove installed-artifact alignment. |

### Escaped Defect And Structural RCA

The built `@librechat/api` entrypoint raised `MODULE_NOT_FOUND` for `mongodb`. The direct source owner
is `packages/api/src/cache/keyvMongo.ts`. Its Rollup build externalizes package dependencies, but
`packages/api/package.json` declared `mongodb` only as a development dependency. Production pruning
therefore removed a module that the shipped built package still required. Resolving the entrypoint
would not have caught the miss; executing it did.

The structural package-boundary correction is:

1. retain `mongodb` as the package development dependency used for build/test;
2. declare `mongodb` as an `@librechat/api` peer dependency because the built library directly
   imports and externalizes it;
3. declare `mongodb` as a production dependency of the consuming backend and update the lock; and
4. after every production prune, execute the built `@librechat/api` entrypoint and fail closed on
   any missing externalized direct import.

The Native candidate workflow now runs both the audited production dependency-tree check and this
runtime-load check immediately after pruning. The synthetic regression proves a missing external
throws `MODULE_NOT_FOUND`; its paired success case proves the entrypoint is executed when the peer is
present.

### Supporting Clean-Copy Evidence

| Stage | Result | Sanitized evidence |
| --- | --- | --- |
| Clean dependency install | PASS | Node `24.16.0`, npm `11.13.0`; 2,626 packages installed from the lock |
| Package build | PASS | All workspace packages built; only existing non-fatal TypeScript declaration warnings |
| Production prune | PASS | 1,144 development packages removed |
| Production dependency-tree guard | PASS | Audited production tree accepted |
| Runtime-load guard | PASS | Built `@librechat/api` actually loaded after prune |
| Direct runtime assertion | PASS | `require('@librechat/api')` returned its object export |
| MongoDB ownership | PASS | Consumer and peer contracts are `^6.14.2`; lock installed `6.21.0` |
| Regression tests | PASS | 5 of 5 passed after prune, including missing-external failure and successful execution |
| Production vulnerability audit | PASS | Zero npm production advisories at the time of the run |
| Producer workflow contract | PASS | 46 focused assembler/release-workflow tests passed, including both post-prune gates |

This clean-copy proof validates the dependency boundary and release guard only. It is not a substitute
for installing and using the replacement exact payload in the pristine guest.

### Required Replacement Acceptance

The next candidate must use the newly frozen nested commit, rebuild and rescan the exact payload, and
repeat the pristine lifecycle from install through registration, browser onboarding, a synthetic
provider answer, refresh/restart persistence, failure recovery, upgrade, and preserve-data uninstall.
The replacement artifact must also retain exact nested commit/pin/build/payload/installed alignment.
Until that run passes, `INST-016`, `INST-027`, and the decisive Easy Install journey remain open.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-007` | PARTIAL | Deterministic build, verify/stage/activate/health, recovery, and fail-closed bootstrap automation | Exact public artifact and live bootstrap remain blocked |
| `INST-015` | BLOCKED | Producer/bootstrap/runtime source and stable authority contracts fail closed | Protected dual-architecture producer not run; redistribution/trust/Apple authority and signed clean-Mac run absent |
| `INST-020` | BLOCKED | Workflow requires hardened signing, timestamp, notary acceptance, staple, team, and Gatekeeper checks | Protected job did not and could not run without authority |
| `PIPE-001` | PARTIAL | Native selection with empty embedded trust refuses before Git/network/source fallback | Live immutable URL and signed bootstrap absent |
| `PIPE-002` | PASS | Public-safety review below and QA contract scan | Raw/private evidence was not created |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Logs/DB/state/docs/artifact evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-008` | Build and activate an exact candidate, then retry clean activation | Installer/CLI local-QA harness | PARTIAL | Assembler installs machine-local config/secrets; compressed builder emits canonical JSON; health executable succeeds; active release remains stable | Payload tree, manifest/inventory, active pointer, sequence/journal state, ownership/PID rollback regressions | Exact dual-architecture producer run and signed artifact absent |
| `PIPE-UC-001` | Select Native distribution before production trust exists | Isolated public shell bootstrap | PARTIAL | Exact fail-closed recovery message; non-zero exit | Fake Git ledger remains absent; shell contract and source agree | Approved embedded trust and live download absent |
| `PIPE-UC-002` | Review a reproducible public-safe result | QA report and release-test surface | PASS | This report distinguishes local QA from production | Safety checklist and focused automation | None for the evidence record |
| `PIPE-UC-003` | Rerun evidence after report/artifact change | QA contract and focused suite | PASS | Final report wording remains partial/blocked | QA contract plus 60 focused tests | Full suite retains unrelated shared-worktree failures |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

| Feature | Requirement / use case | QA case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- |
| Deterministic Native package | Installer doc Native packaging boundary | `INST-007`, `INST-015` | Canonical per-architecture archive/manifest; stable cannot be unsigned | Deterministic relocatable local assembly; byte-identical deflated local-QA output; canonical inventory; real SSH signature verification; immutable output-set publication; unsafe-input rejection | Exact producer workflow has not run on either architecture |
| Durable verified activation | Signed payload -> stage -> health -> active pointer | `INST-007` | Hostile, interrupted, unhealthy, replayed, or repeated candidates cannot corrupt active/previous state | Publisher/digest/schema/architecture checks, hostile archives, durable staging, locks/journal, interruption recovery, rollback, idempotent re-activation, release-owned PID guard, helper ownership rollback, and external 0600 secrets pass | Compiled bootstrap source consumes this boundary, but no signed archive has executed it |
| Public shell hand-off | Public one-command bootstrap | `PIPE-001`, `INST-007` | Production trust is embedded; missing trust cannot trigger download or source fallback | Native mode with empty trust fails before Git; static checks cover non-overridable release/digest/team pins, stapler, and Gatekeeper | Approved trust, signed bootstrap, live URL, and fresh public run absent |
| Protected release | Developer ID/notary/staple/installed artifact | `INST-015`, `INST-020` | Only approved exact candidates receive authorities; exact assets become a verified draft | Full action-SHA pins; protected environment; exact producer provenance; payload/bootstrap signing, notarization, stapling, team/self-check; sanitized asset allowlist; dual-arch health; explicit immutable-release state; draft-only creation | License/trust authorities, administration, workflow execution, clean-Mac QA, and publication absent |

## Full-View Evidence Checklist

| Evidence surface | Required question | Evidence / sanitized pointer |
| --- | --- | --- |
| Requirement and use case | Which contract is proven? | Installer docs 39/40; `INST-007`, `INST-015`, `INST-020`, `PIPE-001`, `PIPE-002` |
| Code owning path | Which path owns behavior? | `install.sh`; Native verifier, builder, assembler, runtime/process guard, bootstrap installer/apps; candidate and protected release workflows |
| Docs and nested docs/repos | What defines expected behavior? | Requirements 39/40, release boundary README, owning QA catalogs, and the nested LibreChat package/consumer dependency boundary |
| Scripts or harnesses | What exercised it? | Builder CLI, focused pytest suites, shell/YAML/Ruff checks, and post-prune built-entrypoint execution |
| Local/external prerequisite state | What dependency was healthy/degraded? | Local shell/Python/OpenSSH healthy; production Apple/GitHub authority unavailable by design |
| Logs | What confirms the result? | Sanitized pytest counts, builder JSON, fail-closed stderr assertions, and clean-copy install/build/prune/load results |
| DB/state/persistence | What state confirms it? | Isolated active/previous pointers, highest-sequence state, journal, and installed version file |
| Generated/shipped artifact | What artifact was inspected? | Synthetic deterministic fixtures plus a provisional exact local-QA payload installed and rejected in a disposable guest; no shipped production artifact exists |
| Real user path | What was used like a user? | Local assembler install/health entrypoints, isolated shell Native selection, and provisional exact-payload install/start in the disposable guest |
| Visual/UX comparison | Does output match the contract? | Public hand-off copy failed closed accurately; exact payload startup failed before browser setup, so no browser acceptance exists |
| Not run / blocked | What remains unavailable? | Replacement exact payload, full pristine lifecycle, dual-architecture protected producer, signed bootstrap/payload, Apple/GitHub run, and public download/install |

## User-Grade Evidence

- Surface exercised: installer/CLI local-QA builder and activation harness; isolated public bootstrap
  shell in Native mode.
- Real user path: assemble a relocatable fixture, invoke its install/health entrypoints, invoke the
  builder CLI, verify the explicit local-QA artifact, stage it, activate it,
  execute `bin/viventium-native-health`, inspect installed content, retry activation, then invoke the
  public shell with Native selected and absent production trust.
- Visible outcome: canonical JSON and successful health for local QA; one accurate non-zero
  “trust policy is not provisioned” result for public Native mode, with no source fallback.
- Expanded/detail state: canonical manifest inventory, artifact hashes, local-QA marker, active and
  previous pointers, journal, and sequence state were asserted.
- Persistence/reload result: the active pointer and installed version remain correct after activation;
  clean re-activation is idempotent and does not overwrite `previous` with itself.
- Local/external prerequisite state: local build tools were available; release signer, Developer ID,
  notarization authority, protected environment configuration, and immutable-release setting were
  intentionally unavailable.
- Evidence retrieval classification, if applicable: unsupported production configuration because
  redistribution approval, approved release authority, signed artifacts, and protected execution do
  not exist.
- Fallback path, if applicable: source mode remains an explicit developer/local-QA choice; Native
  mode refuses automatic source fallback.
- Backend/log/DB confirmation: filesystem activation state and journal agree with CLI success; the
  fake Git call ledger stays absent on the unprovisioned Native failure; no DB applies.
- Final model/runtime wording check: no model path applies; CLI/runtime wording does not claim signed,
  notarized, installed, or production-ready behavior.
- Substitution check: automation and source inspection support the executed local CLI/shell paths but
  do not replace the blocked protected release, exact installed artifact, clean-Mac, or later browser
  onboarding paths.

## Automated Evidence

```bash
python -m pytest tests/release/test_native_payload.py tests/release/test_native_payload_builder.py tests/release/test_native_payload_assembler.py tests/release/test_public_bootstrap_manifests.py tests/release/test_ci_release_workflows.py -q
bash -n install.sh
python -c 'import pathlib,yaml; data=yaml.safe_load(pathlib.Path(".github/workflows/native-payload-release.yml").read_text()); assert isinstance(data,dict)'
ruff check scripts/viventium/native_payload.py scripts/viventium/build_native_payload.py scripts/viventium/assemble_native_payload.py scripts/viventium/native_runtime.py scripts/viventium/native_process_guard.py scripts/viventium/install_native_payload.py tests/release/test_native_payload.py tests/release/test_native_payload_builder.py tests/release/test_native_payload_assembler.py tests/release/test_public_bootstrap_manifests.py tests/release/test_ci_release_workflows.py
python -m pytest tests/release/ -q
```

- Focused result: **70 passed**.
- Shell and workflow syntax: **PASS**.
- Ruff: **PASS** after removing three unused imports.
- Full release result in the shared dirty worktree: **1,068 passed, 46 failed, 30 skipped**. Two
  failures identified this new report/map integration and were corrected immediately; the remaining
  failures are in unrelated agent-sync, memory, prompt, QA-report, and voice surfaces with missing
  nested assets/dependencies or concurrent worktree changes. This is not a full-suite pass claim.

## Findings

- Defects: clean re-activation could overwrite `previous` with the active release; fixed with a
  regression. The builder resolved away a symlinked root and replaced existing output sets; both now
  fail closed. Candidate provenance was under-constrained; it now pins producer path, explicit
  dispatch, repository, commit, conclusion, architecture, and inventories before secrets.
- Regressions: none in the focused scope.
- Flakes: none observed.
- Environment issues: full release suite has unrelated failures in the shared dirty worktree; no
  Apple/GitHub production authorities were available or requested.
- Residual risks: exact no-tools arm64/x86_64 producer execution; reviewed bootstrap hashes; real
  signing/notarization/stapling; protected environment and immutable-release administration;
  MongoDB redistribution approval; live download/interruption;
  clean-Mac install/rollback/restart/provider/continuity/accessibility acceptance; human publication.

## Authority And Administration Blockers

External authority that implementation code cannot invent:

1. release-owner approval of the real manifest signer public key and Apple team identifier;
2. Account Holder-created Developer ID Application certificate and App Store Connect notary access;
3. protected `native-payload-release` environment deployment policy and secrets; use separate
   reviewers/no-self-review only when the organization has another authorized reviewer, not for the
   current sole-owner configuration;
4. repository-owner enablement of GitHub immutable releases;
5. human review and publication after clean-Mac acceptance.

Verification blockers that remain before requesting publication:

1. record the required MongoDB redistribution approval;
2. run the implemented producer for arm64/x86_64 and review the exact candidate inventories;
3. run the protected payload/bootstrap signing and notarization workflow, then bind reviewed exact
   bootstrap hashes into the public hand-off;
4. run exact-artifact clean-Mac installation and the full natural-user recovery/product matrix.

Primary guidance: [Apple Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/),
[Apple notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[Apple notarization issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues),
[GitHub protected environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
[GitHub secure workflow use](https://docs.github.com/en/actions/reference/security/secure-use),
[GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations), and
[GitHub immutable releases](https://docs.github.com/en/enterprise-cloud@latest/code-security/concepts/supply-chain-security/immutable-releases).

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
