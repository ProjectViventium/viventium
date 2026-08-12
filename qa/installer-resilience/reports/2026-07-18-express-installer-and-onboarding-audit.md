# Easy Install And Onboarding Audit — 2026-07-18

## Summary

- Result: **PARTIAL source-candidate acceptance; not public-release-ready**.
- Real user path: isolated Easy Install/restart, browser registration/setup handoff, two provider
  popup cancel/retry attempts, signed-out Feelings redirect, authenticated Feelings discovery, and
  refresh persistence passed.
- Substitution check: no source/test/model result substitutes for the unrun signed-payload,
  provider-answer, restore, helper/security, Docker, delivery-alignment, or accessibility gates.

## Scope Run

| Scope | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Express Native source candidate | PARTIAL | Disposable macOS VM plus real Chromium and loopback socket/process checks | Exact signed payload and vanilla no-tools machine remain blocked. |
| Focused implementation regression | PARTIAL | 386 earlier tests plus post-review Node alignment contract and 90 focused preflight/launcher passes | Source toolchain alignment is fixed; exact artifact and broader release gates remain open. |
| Broad parent release suite | PARTIAL | Independent isolated 1,024-test run, detailed below | No Express behavioral failure; QA hygiene findings remain. |

## Disposable Express Native execution update

Result: **PARTIAL**. The source-candidate Express Native path now installs and restarts in an
isolated Apple Silicon macOS VM, reaches healthy API/web surfaces without Docker, creates a local
user, opens Connected Accounts automatically, starts the OpenAI authorization flow, recovers from
popup cancellation, exposes Feelings from the ordinary right-side controls, and preserves the
Feelings route across refresh. This is meaningful user-grade evidence, but it is not a public
release pass: the candidate is a sanitized local source snapshot rather than the exact signed
payload; the VM base already contains dormant Command Line Tools/Homebrew state; provider
authorization/first answer, Keychain/helper GUI, full restore, clean no-developer-tools packaging,
and the physical-Mac Docker delta remain open.

### Isolated target and safety boundary

- Tart `2.32.1`, official `macos-tahoe-base` OCI digest
  `sha256:a8e1c8305758643f513fdccdd829c2243687c60791083dea42f73f0b7aeb435c`;
  Apple Silicon macOS `26.5`, 4 vCPU, 8 GiB RAM, 80 GiB disk.
- VM launched without host mounts, clipboard, audio, or graphics. SSH used a disposable key and a
  loopback-only host tunnel for browser QA.
- Guest state was isolated under `~/Library/Application Support/Viventium-QA`; only synthetic
  account/config data was used. The established host Viventium App Support, databases, Keychain,
  helper config, and running personal runtime were not installation targets.
- No commit, push, PR, release, cloud configuration, provider grant, or channel mutation occurred.
- Tart and its `softnet` formula were installed locally on the host after formula inspection; no
  privileged Softnet/DHCP setup was run.
- After QA, Viventium was stopped cleanly in the guest, the dedicated loopback SSH tunnel was
  closed, and both the untouched baseline and disposable run VM were retained in a stopped state.

### What actually ran

| Surface | Outcome history | Evidence |
| --- | --- | --- |
| First Express preflight | FAIL -> fixed | Homebrew's Mongo tap path required an additional transitive tap trust step. Express now downloads exact MongoDB `8.0.23`, verifies SHA-256, bounded/safe extraction, Developer ID team and version, and installs only the allowed runtime files under App Support. Express preflight/start now fail closed if that exact app-owned binary or listener identity is absent; arbitrary `PATH` and Homebrew Mongo remain available only to legacy/custom paths. |
| Compiler/doctor | FAIL -> fixed | Missing Groq configuration left `${GROQ_API_KEY}` in generated LibreChat YAML. Express now removes an entirely unavailable env-backed custom endpoint and its `addedEndpoints` entry without affecting user-provided Groq configuration. |
| Failed frontend build | FAIL -> fixed | A deliberately incomplete staged source snapshot produced a real Vite module-resolution failure. Installer readiness previously waited behind live wrapper/sidecar processes; it now detects current-attempt build failures immediately, ignores stale-log and benign Docker-cleanup lines, and allows the launcher's owned clean dependency retry to finish before classifying a terminal failure. |
| Easy Install and rerun | PASS on source candidate | API `:3180` and web `:3190` became healthy; voice/playground/search remained deferred; repeated install, stop, restart, and health probes passed. Cached post-build restarts reached healthy surfaces in about 20 seconds. |
| Local network boundary and status truth | FAIL -> fixed -> PARTIAL | Guest socket inspection showed Mongo `:27117`, API `:3180`, and web `:3190` bound to `127.0.0.1`; direct probes to the guest's non-loopback address were refused and Playground was deferred. Both the shared status summary and the launcher's final banner had advertised an unreachable raw LAN URL; both now show localhost only and were exercised through the live VM CLI/start path. Second-host, firewall, remote-mode, and all-service matrices remain open. |
| Node/runtime build | PARTIAL for runtime alignment; build-only evidence PASS | Guest Node `24.16.0`; data-provider and production client builds passed. Post-review source tracing and red-first contracts reproduced a split where the main launcher, optional Skyvern launcher, and macOS helper still selected Node 20 while preflight/common/doctor selected Node 24. All six source surfaces now select Node 24; the cross-layer contract, full preflight suite, Express launcher summary, package-rebuild contract, detached supervision checks, both shell syntax checks, and helper build pass (90 passed, 1 environment-limited skip). The default-heap build also failed honestly at approximately 2 GiB; the bounded `NODE_OPTIONS=--max-old-space-size=6144` build passed. Exact-payload clean-install process/build/start/restart provenance remains unrun. |
| Browser registration/login | PASS | Real Chromium registration created a synthetic local user. Login consumed `/c/new?setup=accounts`, left a clean `/c/new` URL, and visibly opened the real Connected Accounts panel. |
| OpenAI Connect initiation | PASS; completion NOT RUN | The final browser run returned HTTP `200` in 4.214 seconds with `popup_callback` and an `https://auth.openai.com/oauth/authorize` PKCE URL. The API now refuses to construct callback origins from an untrusted request `Host` when no explicit trusted origin is configured. No provider credentials were supplied and no grant was completed. |
| OAuth cancel/retry | FAIL -> fixed -> PASS | Closing the provider popup originally left a spinner until bounded polling expired, and an older async attempt could race a newer one. Each attempt now has an identity token; stale results cannot tear down a later flow, poll success closes the popup, and cancellation restores Connect immediately. The final browser run passed two consecutive popup cancel/retry attempts. |
| Feelings discovery/persistence | PASS | A signed-out real-browser visit to `/feelings` visibly redirected to login rather than rendering blank. After authentication, Chromium clicked Feelings in the right-side control panel, rendered the Feeling Spectrum, and retained `/feelings` plus visible state after refresh. |
| Login abuse protection | PASS unhappy path | Repeated synthetic logins returned HTTP `429` and visibly explained that there were too many attempts; no blank screen or generic failure occurred. |
| Parent regression set | PASS | 386 focused installer/compiler/preflight/native/startup/helper/payload/transaction/onboarding/navigation tests passed in 55.36 seconds. This is a focused slice, not the full release suite. |
| Broad parent release suite | PARTIAL; Express slice PASS | Final independent guarded run collected 1,024 tests: 1,014 passed, 2 failed, 8 skipped in 139.39 seconds. Every Express Native/installer/onboarding behavioral test passed. Both failures are pre-existing/unrelated QA-report hygiene: noncompliant emotional-cortex/memory-hardening/prompt-architecture reports, and an untracked memory report containing a private worker runtime identifier field. |
| Nested focused tests | PASS | 7 registration/setup-handoff client tests and 11 Connected Accounts API tests passed in the VM under Node 24. |
| Native payload verifier | PASS as reference tooling | 14 tests cover canonical manifest, SSH signature/tamper, digest/size/platform/schema gates, hostile ZIP rejection, immutable activation, journal/lock, and health rollback. It is not yet wired into the public bootstrap. |
| Helper artifact | PARTIAL | Swift source builds and the prebuilt helper is universal `arm64`/`x86_64`; the package has no Swift test target. Interactive SMAppService/Keychain/Gatekeeper behavior was not run in the headless VM. |
| QA harness Keychain isolation | FAIL -> fixed -> PASS | A broad-run wizard test unexpectedly reached the real `security add-generic-password` command and blocked before authorization/completion. The isolated test process was stopped, the test now mocks secret storage, and the authoritative rerun also placed a fail-closed `security` stub first on `PATH`. No password/authorization was supplied and no Keychain value was read back or exposed. |

The repeatable browser case is
`qa/installer-resilience/scripts/express-native-browser-qa.cjs`. It refuses non-loopback and
production/CI targets, uses caller-supplied synthetic credentials, does not print OAuth state or
secrets, and stores screenshots in a temporary private directory.

The final focused parent rerun was:

```bash
python -m pytest \
  tests/release/test_wizard.py \
  tests/release/test_config_compiler.py \
  tests/release/test_preflight.py \
  tests/release/test_native_stack_helpers.py \
  tests/release/test_install_summary.py \
  tests/release/test_cli_upgrade.py \
  tests/release/test_macos_helper_install.py \
  tests/release/test_native_payload.py \
  tests/release/test_config_transaction.py \
  tests/release/test_express_launcher_summary.py \
  tests/release/test_connected_accounts_onboarding_contract.py \
  tests/release/test_feelings_navigation_contract.py \
  -q -p no:cacheprovider
# 386 passed in 55.36s
```

### Broad parent release-suite result

The independent final run used a temporary home/cache/config/data tree, disabled host-path
discovery, removed global/system Git configuration, and placed a fail-closed temporary `security`
stub first on `PATH`. It did not use App Support, runtime, or cloud state.

```text
1024 collected; 1014 passed; 2 failed; 8 skipped in 139.39s
```

- The installer audit's required report headings and all three new release-test owners were fixed;
  the final ownership gate passes and this Express audit no longer appears in the report-template
  failure.
- Residual failure 1 covers four other QA reports: one emotional-cortex report, two
  memory-hardening reports, and a pre-existing prompt-architecture baseline.
- Residual failure 2 is an untracked memory-hardening report containing a private worker runtime
  identifier field. It was not rewritten as part of this installer task.
- Six skips require optional `fastmcp`, one is an opt-in live evaluation, and one is a macOS host
  process-inspection limitation. These are not Express acceptance passes.

### Release gates still open

1. Replace source clone/build and package-manager bootstrap with the signed/notarized, versioned,
   prebuilt Native payload. `native_payload.py` is a verified reference implementation, not the
   installed production entrypoint.
2. Run a truly vanilla macOS image with no CLT, Homebrew, Git, Python, pnpm, uv, or system Node and
   prove the packaged app/helper path plus Keychain and Gatekeeper.
3. Complete one synthetic provider grant and rendered first answer, denial/wrong-account/expiry/
   quota/network cases, restart persistence, disconnect, and revoke.
4. Prove the full continuity payload and independent restore; current work does not close the
   backup/restore release gate.
5. Run low disk/RAM, offline/DNS/TLS, corrupt/interrupted payload, occupied ports, double install,
   crash/reboot, rollback/downgrade, uninstall-preserve/delete, accessibility, localization, and
   two-host network lanes.
6. After those Native core gates, use the separate MacBook Air for the shared Express Docker delta;
   do not treat the source-candidate VM result as Docker acceptance. Follow the
   [physical-machine preparation, connection, comparison, and teardown handoff](../macbook-air-docker-qa-handoff.md).
7. Align the delivery chain before release: the VM-tested LibreChat tree is
   `a55efcdc4cfc0847877e30c90f76d693ba31cb25` plus uncommitted changes, while the parent manifest
   pins the one-commit descendant `f051e431524e394f18cebcd0dda7df1685d328aa`. Neither state is the
   exact tested public artifact.
8. Finish Node toolchain acceptance. Post-review remediation aligns preflight, shared PATH setup,
   doctor, dependency repair, both owning launchers, and the helper on Node 24 with a passing
   cross-layer contract. Prove
   build/start/restart and resolved process paths under that same runtime in the exact installed
   payload (`INST-024`).

### Original-objective completion sanity check

Independent repository review, structured Claude review, and a visible Fable 5 Extra review were
asked to challenge the release conclusion against the user's verbatim original request. The
defensible result remains **not done**:

- PASS: locally available commit/history inventory; fresh-versus-established analysis; public-safe
  research/design package; local-only/no-push boundary; QA case inventory.
- PARTIAL: isolated Native source-candidate QA; backup safety (without full product restore);
  preferred-account onboarding; new/existing-user unhappy paths; Feelings discovery; Telegram,
  Groq/Grok, Slack, WhatsApp, and community-skill product design.
- FAIL: 100% executed coverage; one-command no-developer-tools release; configured-versus-live
  readiness; delivery-chain alignment. Node runtime alignment is now PARTIAL at source level.
- BLOCKED: signed/notarized payload, truly vanilla Mac, full provider lifecycle/first answer, full
  continuity restore, complete fault/uninstall matrix, headed helper/Keychain/Gatekeeper,
  Native-versus-Docker physical delta, and accessibility/localization matrix.

| Original requirement | Status | Current evidence | Exact remaining proof |
| --- | --- | --- | --- |
| Full locally available project-history inventory | PASS | 216 public-parent commits, 115 installer/delivery ledger entries, eight lifecycle phases, and managed-component pin inventory | State explicitly that unavailable pre-public/remote-only history is outside the evidence boundary. |
| New-machine/new-user versus established reliable owner setup | PARTIAL | Fresh-versus-established state/risk map plus disposable VM comparison | Analysis passed; add literal step-by-step procedures for both personas and complete existing-user cloned-state acceptance. |
| Protect and back up personal state before risky QA | PARTIAL | Owner App Support/database/Keychain were not install targets; private safety material remained outside git | Audit safety passed; independently restore every promised continuity domain into a disposable target (`INST-018`). |
| Secure sandbox and real user-experience QA | PARTIAL | No-host-mount Tart macOS VM plus real Chromium registration, setup handoff, OAuth start/cancel/retry, Feelings, refresh, rerun, and restart | Exact payload, vanilla image, provider answer, helper/security, full faults, Docker, and inclusive UX remain. |
| No cloud changes or publication | PASS | No push, PR, release, provider grant, external message, or channel mutation | Preserve this boundary until separately authorized. |
| 100% project/nested-feature executed coverage | FAIL | Complete acceptance inventory exists, but the broad suite had failures/skips and `INST-015`–`INST-024` include BLOCKED/PARTIAL/FAIL | Run or explicitly rescope every remaining feature-owner and release gate; do not claim 100% meanwhile. |
| Happy and unhappy paths for new and existing users | PARTIAL | Selected install/retry/rate-limit/OAuth-cancel/restart paths pass; comprehensive cases are documented | Run provider denial/expiry/quota/network, low-resource/offline/corrupt/interruption, existing-user restore/upgrade/rollback, and uninstall preserve/delete. |
| One-command Express Native without Docker/developer tools | FAIL | Native API/web source candidate works without Docker, but this does not satisfy the release promise | Wire the signed/notarized prebuilt payload and prove a truly vanilla Mac (`INST-015`, `INST-016`). |
| Connect preferred account and receive a useful persistent answer | PARTIAL | Browser provider authorization starts and cancellation/retry works | Complete synthetic grant, live self-test, first and second answers, refresh/restart persistence, disconnect, and revoke (`INST-017`). |
| Deep current open-source research and hands-on clone inspection | PARTIAL | Grounded research and recorded revisions for disposable shallow inspections | Attach durable primary-source citations for popularity/strength claims and either retain a dedicated inspection workspace or explicitly document that disposable clones are the accepted deliverable. |
| Whole research/evaluation/test/foundation/conclusion package | PASS | Inventory, research, action plan, cases, reports, and independent reviews are linked as an audit package | Keep the conclusion synchronized with new proof; the package does not make the product complete. |
| Telegram, Slack, WhatsApp, Groq, Grok, other channels | PARTIAL | Staged design passed: Telegram-first, Slack-Advanced, WhatsApp-unsupported, and Groq-versus-xAI/Grok boundaries are documented | Run Telegram and Groq/xAI lifecycles; do not advertise Slack/WhatsApp before real adapters and acceptance exist. |
| Community skills and trust model | PARTIAL | Skills/MCP discovery, trust, consent, and staging patterns are documented, but the product lifecycle is not shipped | Implement and QA an explicit install/enable/disable/update/revoke lifecycle before presenting community skills as available. |
| Feelings flagship control-panel discovery | PARTIAL | Source-candidate right-control entry, signed-out redirect, visible spectrum, and refresh pass | Commit/repin/rebuild/install the tested delta; run missing/degraded provider, keyboard, narrow/mobile, and accessibility cases. |
| Clueless-user account guidance and minimal choices | PARTIAL | Express terminal avoids provider secrets; registration hands off to Connected Accounts; cancel/retry is visible | Finish one shared truthful connection/readiness state machine and prove the entire first-answer journey on the exact artifact. |
| Existing-user configure, upgrade, recovery, and uninstall | PARTIAL | Headless transactional configure plus selected rerun/restart contracts pass | Run interactive/helper transaction, full restore, upgrade/rollback/downgrade, crash/reboot, and preserve/delete uninstall. |
| Quality plus performance/resource reliability | PARTIAL | Warm restart and bounded-build evidence exist; default build OOM was captured honestly | Measure complete install/first-answer time, RAM/CPU/swap/disk/thermal/battery and failure behavior on supported physical hardware. |
| Claude/Fable adversarial review | PASS | Structured Claude review and visible Fable 5 Extra review challenge the same evidence and verbatim prompt as supporting review | Review cannot substitute for the blocked real user paths. |
| Physical MacBook Air Native/Docker QA | BLOCKED | Expected known-host fingerprint matched locally, but the required relay port refused connection; no remote command executed | Restore the relay, then perform read-only preflight before creating the dedicated synthetic QA root. System-wide/helper/Docker/destructive cases require explicit physical-machine safety approval. |

The OpenAI/OAuth retry/security improvements and Feelings sidebar entry are present only in the
dirty nested LibreChat worktree. The parent pin contains the older underlying features but not the
tested Express hardening/onboarding/sidebar delta. A fresh pinned install therefore does not receive
the behavior exercised by the VM/browser lane.

The final Fable completion review also confirmed four adjacent product gaps. `README.md` does not
present the Express journey, and neither public example config declares `install.experience`, so
the intended profile is not yet discoverable from the public front door or presets. The fail-closed
OAuth origin needs a cross-mode installer proof that a trusted return origin is always generated.
Groq/xAI pruning needs a late-key reconfigure case proving the endpoint reappears without reinstall.
Meilisearch remains in the Native core and still needs an explicit necessity/resource decision for
low-spec Macs. The OAuth attempt-identity fix is client-side; no server-side attempt-isolation claim
is made.

> Baseline record: several source-level defects identified below were narrowed later the same day.
> See the [remediation QA run](2026-07-18-installer-safety-remediation-qa.md) and the execution-status
> table in the [action plan](../express-installer-remediation-plan.md). Clean-machine, restore,
> account, delivery-pin, shipped-artifact, and installed-runtime gates remain open, so the release
> decision is unchanged.

## Historical Audit Baseline — Before The Remediation Above

- Result: **FAIL** — the Express/public-release claim failed; the local evidence audit itself passed.
- Build/source under test: parent checkout at `8ebb89c` plus the nested-repository states and
  delivery pins described in the lifecycle inventory.
- Runtime/artifact under test: the installed local runtime was inspected read-only; a temporary
  wizard/compiler flow and the unauthenticated local web surface were exercised. No installer,
  configure, reset, restore, runtime activation, account, channel, or cloud mutation was run.
- Environment: an established Apple Silicon development Mac with a running local runtime and
  personal state. Public evidence is sanitized; private backup material remains outside git.
- Tester: Codex with independent read-only repository mapping, open-source research, and installer
  QA review passes. The independent Fable 5 Extra verdict and reconciled corrections are recorded in
  [`fable-review-2026-07-18.md`](../fable-review-2026-07-18.md).
- Release conclusion: the current product has strong lower-level automation, but it does not yet
  prove a safe, truthful, nontechnical one-command Express journey on the exact shipped artifact.
- Highest-risk blockers: metadata-only backups presented as successful, nontransactional
  reconfiguration, misleading Easy copy, configured-only states shown as `Ready`, mutable/unverified
  bootstrap targeting, an unenforced loopback-only playground boundary, mandatory but poorly
  disclosed credentials and worker authentication, and no current clean-Mac end-to-end acceptance.

## Historical Baseline Scope Run

| Case or audit ID | Recorded outcome | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-001` | PARTIAL | `doctor`, shell syntax, isolated wizard/compiler, source trace | Real host install/recovery was intentionally not run. |
| `INST-002` | PASS (audit package); FAIL (current working tree) | Public-safety scan plus full release suite | This audit package is sanitized; separate pre-existing untracked dated reports violate the evidence contract. |
| `INST-003` | NOT RERUN | Existing 2026-05-31 focused report | The prior automated result remains PASS; separate clean-Mac install remains unproved. |
| `INST-004` | FAIL | Wizard, readiness, summary, docs, feature-owner map | Current source contradicts the readiness contract and user-facing copy. |
| `INST-005` | FAIL | Snapshot wrapper, helper UI, restore path, local restore rehearsal | Metadata-only success is allowed and fallback may rewrite the latest real snapshot manifest. |
| `INST-006` | FAIL | CLI configure/recovery/headless source trace | Existing config can be replaced without transactional merge/backup. |
| `INST-007` | FAIL | `install.sh` bootstrap trace | Existing destination origin is not validated; immutable/provenance hardening remains planned release scope. |
| `INST-008` | BLOCKED | Existing QA catalog and live unauthenticated browser | Exact clean public artifact has no full Express-to-first-answer proof. |
| `INST-009` | FAIL | Install-summary and readiness source trace | Several configured-only features are displayed as `Ready`. |
| `INST-010` | PARTIAL | Provider/channel inventory | Telegram is mature; Slack is absent; WhatsApp is unavailable; Groq/xAI onboarding is incomplete. |
| `INST-011` | BLOCKED | Isolation capability review | Linux VM profiles cannot certify macOS Keychain/helper/LaunchAgent behavior. |
| `INST-012` | FAIL | Side-panel/account-menu code plus browser redirect | Feelings is not discoverable from the requested control-panel surface. |
| `INST-013` | FAIL | Launcher source, installed Next help, and live listener | Playground defaults to a wildcard listener instead of enforcing loopback-only local mode. |

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | Exercise installer/CLI/helper failure and recovery truth. | Doctor, shell syntax, isolated wizard/compiler, signed-out browser | PARTIAL | Diagnostics and auth errors were honest | No host install/recovery mutation ran | Disposable full flow required. |
| `INST-UC-002` | Create a public-safe evidence record. | This audit package | PASS | Sanitized report and package | Targeted scans passed | Separate untracked reports still fail the working-tree suite. |
| `INST-UC-003` | Rerun evidence checks after report corrections. | This audit package | PASS | Corrected package remains public-safe | Targeted contract and privacy checks | Recurring report generator remains unidentified. |
| `INST-UC-004` | Verify default nightly workflow install/upgrade. | Not rerun | PARTIAL | Historical 2026-05-31 PASS only | Prior focused report | Current clean separate-Mac rerun remains outstanding. |
| `INST-UC-005` | Run Express/Advanced brain readiness. | Wizard, readiness, summary, docs | FAIL | Easy copy understates prompts; status can overstate readiness | Three QA-owner paths also dangle | Reconcile current contract and live-test readiness. |
| `INST-UC-006` | Protect and independently restore an existing setup. | Snapshot/restore trace; private logical rehearsal | FAIL | Helper can say backup created for metadata-only output | Fallback may also rewrite the latest real manifest | Immutable attempts plus full browser-visible restore. |
| `INST-UC-007` | Reconfigure one setting without drift. | CLI/source trace | FAIL | Not run destructively | Canonical config can be overwritten directly | Transactional candidate/merge/rollback workflow. |
| `INST-UC-008` | Bootstrap into empty, valid, unrelated, and failed targets. | Bootstrap source trace | FAIL | No real clean-target run | Existing `.git` origin is not validated | Immediate origin guard; later provenance acceptance. |
| `INST-UC-009` | Complete one command through first answer, Feelings, restart, and restore. | Established signed-out browser only | BLOCKED | Login validation and Feelings auth redirect worked | Fresh registration and all authenticated steps unavailable | Disposable clean macOS target required. |
| `INST-UC-010` | Distinguish configured from live-ready. | Summary/readiness source trace | FAIL | Several rows can show `Ready` from configuration presence | No live provider request proves them | Unified state model and live self-tests. |
| `INST-UC-011` | Connect and manage supported providers/channels. | Provider/channel inventory | PARTIAL | Telegram is mature; Slack absent; WhatsApp unavailable | Fresh integration lifecycle unproved | Synthetic account/channel matrix. |
| `INST-UC-012` | Run isolated platform/failure matrix. | Isolation capability review | BLOCKED | Linux VM cannot prove macOS surfaces | No disposable macOS target | Apple Silicon VM plus physical Mac where needed. |
| `INST-UC-013` | Discover Feelings from ordinary chat. | Direct signed-out route and source trace | FAIL | Auth redirect and account-menu route exist | Current requirement does not yet specify the requested control-panel entry | Update requirement, implement, build, and browser-test. |
| `INST-UC-014` | Verify local services are not exposed to the LAN by default. | Launcher, live socket, and loopback/non-loopback probes | FAIL | Loopback returned the playground; non-loopback probe timed out | Process still listened on wildcard and Next documents `0.0.0.0` as its default | Pass an explicit loopback hostname and run clean-Mac firewall/network matrix. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: public bootstrap, installer, configuration compiler, helper, onboarding, connected
  accounts, integrations, runtime status, Feelings discovery, continuity, and restore.
- Requirements: `01_Key_Principles.md`, `39_Installer_and_Config_Compiler.md`,
  `40_Public_Private_Boundaries_and_License_Matrix.md`, `45_Runtime_Feature_QA_Map.md`,
  `47_Remote_Access_and_Tunneling.md`, `50_Stable_Dev_Runtime.md`,
  `51_GlassHive_Workflows_Self_Healing_and_Feature_Requests.md`,
  `54_Emotional_Cortex_And_Feeling_State.md`, and `qa/README.md`.
- Use case: a nontechnical new user runs one supported command, gets an honest and recoverable
  install, creates an account, connects a preferred provider, receives a useful answer, optionally
  connects a channel, discovers Feelings, and retains the result after restart.
- QA cases: `INST-005` through `INST-013`, plus existing `INST-001` through `INST-004`.
- Expected result: the shipped clean artifact completes the journey with minimal required choices,
  verified components, Keychain-backed secrets, truthful status, clear recovery, and no dependence
  on owner-machine state.
- Actual evidence: automated lower-level contracts are strong; the current dirty working-tree suite
  is not clean because of separate pre-existing untracked reports; critical backup/config/bootstrap/
  status defects exist; and the clean end-to-end journey has not been run on the exact public
  artifact.
- Remaining gap: implement the phased remediation plan, then run the clean macOS matrix and the
  single decisive end-to-end case without substituting source, tests, logs, or mature-runtime state.

## Delivery Inventory And Fresh-Versus-Established Truth

Fresh installs follow `components.lock.json`. The development workspace observed during this audit
does not match that delivery boundary:

| Repository | Delivery relationship at audit time | Dirty state | Consequence |
| --- | --- | --- | --- |
| Parent | Current checkout `8ebb89c`; public history also contains later delivery work | 127 tracked, 17 untracked | Working-tree behavior is not a clean release artifact. |
| LibreChat | One commit behind its configured delivery pin | 125 tracked, 14 untracked | Current Feelings/onboarding behavior may include unpublished work. |
| GlassHive | One commit behind its configured delivery pin | 4 tracked | Worker behavior may differ from the public pin. |
| Other managed components | Seven additional checkouts behind pins; two exact | Clean | Local checkout heads still cannot stand in for manifest checkout QA. |

The established runtime also has persistent App Support state, Keychain references, databases,
scheduled work, caches, models, provider routes, helper state, and worker sandboxes. A fresh machine
has none of those. Evidence must therefore remain split into:

1. exact public pins in a disposable clean environment;
2. existing-user continuity against a cloned/restored copy of established state;
3. current dirty development behavior, useful for investigation but never release proof.

The detailed repository and commit ledger is in
[`installer-lifecycle-inventory-2026-07-18.md`](../installer-lifecycle-inventory-2026-07-18.md).

## Confirmed Findings

### P0 — Backup success is not equivalent to recoverability

The public snapshot wrapper can fall back to a metadata-only continuity manifest and exit `0` when
the private payload helper is unavailable. The macOS helper maps that exit to “Backup snapshot
created.” Public restore directly applies only limited Telegram configuration; database recovery is
left as manual follow-up. This behavior is explicitly permitted by the current installer requirement,
the continuity-ops contract, and its release test, so it is a requirements/UX/system defect rather
than an accidental code regression.

The fallback is more dangerous than wording alone: it can select the latest existing snapshot
directory and rewrite that snapshot's manifest in place. A later metadata-only attempt can therefore
collapse snapshot history and replace the manifest for a previously real snapshot, undermining age
and restore-safety checks. The requirement, continuity contract, implementation, and test must be
changed together.

The audit created a private, local, access-restricted safety copy outside the repository and captured
logical Mongo and search-engine backups. Archive integrity and a Mongo dry-run restore passed. That
reduces immediate audit risk but is **not** sufficient to prove product restore: browser-visible
chat, memory, recall, schedules, auth, and helper continuity were not restored into a disposable
runtime.

### P0 — Reconfigure is nontransactional

`bin/viventium configure`, recovery `reconfigure`, and headless `install --config-input` can replace
the canonical config without first creating a full backup, merging existing values, showing a diff,
validating a candidate, atomically swapping it, or offering rollback. Only the `start-over` recovery
branch invokes the existing backup helper. The product should not instruct existing users to use
configure until this is transactional.

### P0 — Easy/Express copy is materially inaccurate

The profile copy says Easy “Only asks for Groq and optional Telegram.” The owning flow additionally
asks about voice, web-search provider, scraper provider, hosted keys or Docker, Recall/RAG,
transcripts, remote access, and browser authentication. It then blocks on a signed-in Codex or Claude
CLI because GlassHive is mandatory, and the useful primary model still requires a browser account
and connected-account step. The initial choice does not disclose this prerequisite chain.

Docs also disagree: one feature document describes automatic local search when Docker is available
and a minimal/off path otherwise; the installer contract describes guided web search. There must be
one current contract.

### P0 — Status overstates readiness

The install summary derives `Ready` for multiple surfaces from credential presence, a selected mode,
an enabled flag, or a configured folder. The installer requirement explicitly says credentials are
only `Configured` until a live request proves them. Use one state machine across installer, Brain
Setup, status, helper, and integrations:

`not_configured`, `connecting`, `configured`, `ready`, `degraded`, `needs_auth`, `missing_scope`,
`invalid_credential`, `quota_or_rate_limit`, `network_unavailable`, `dependency_unhealthy`,
`unsupported`, `update_required`.

### P0 — Bootstrap target and release are insufficiently verified

When the default destination already contains `.git`, `install.sh` fetches/checks out/pulls without
first proving that the origin is Viventium. An unrelated repository at that path can be mutated; this
is the immediate product defect. The bootstrap also follows mutable `main`. Versioned bootstrap,
checksum/signature/provenance, exact manifest pins, and an SBOM/digest record are already documented
future release-hardening scope and should remain a separately tracked delivery boundary rather than
being represented as one already-regressed P0.

### P0 — Mandatory Groq and worker prerequisites are brittle

The interactive wizard asks for a Groq developer key in every profile. Preset/headless paths are more
nuanced: xAI activation can be selected through an override, and a headless preset can omit
GlassHive. Interactive Express still requires a signed-in Codex or Claude CLI for mandatory
GlassHive without disclosing it at the profile choice. Existing release evidence shows provider
rejection can make xAI fallback essential, yet Easy does not collect or validate that fallback.
Groq activation needs its own live-tested readiness row and a supported recovery/fallback story. UI
wording must distinguish “Groq API” from “xAI API — Grok models.”

### P1 — The first useful browser journey is fragmented

The isolated preset/wizard/compiler dry run passed and selected OpenAI connected-account auth before
a browser-local account or connection could exist. The live established runtime showed a polished
login surface and correct blank-form errors. Direct unauthenticated `/feelings` safely redirected to
login. Because registration is disabled for this existing-user runtime, it cannot prove the fresh
first-admin experience.

### P0 — Local playground does not enforce its loopback boundary

The launcher starts the modern playground with `next dev -p PORT` and no hostname. The installed
Next CLI states that its default hostname is `0.0.0.0`, and the established runtime was observed
listening on wildcard port `3300` while product docs describe a localhost surface. Loopback returned
HTTP `200`; a same-host non-loopback probe timed out, so actual LAN reachability on this Mac was not
proven. Firewall behavior is not an acceptable product boundary: local mode must pass an explicit
loopback hostname, and intentional remote access must use the declared authenticated tunnel/public
mode and its own acceptance cases.

### P1 — Feelings is implemented but not flagship-discoverable

`/feelings` exists and the enabled account menu includes a Feelings entry. The right-side control
panel contains Assistant Builder, Agent Builder, Prompts, Memories, Parameters, Files, Bookmarks,
MCP Builder, and Hide Panel, but no Feelings entry. The current Feelings requirement names the
account-menu route, so the requested control-panel entry is a new flagship-discovery requirement,
not a failure against the existing contract. Existing browser harnesses typically navigate directly
to `/feelings`, so they do not prove discovery from normal chat. The planned slice should update the
requirement first, then add a first-class entry and cover:
available, disabled, signed out, provider missing, degraded provider, preserved draft, keyboard,
mobile/narrow layout, refresh, and return-to-chat behavior.

### P1 — Channel scope must remain honest

- Telegram: first priority and substantially mature, but its fresh BotFather → hidden token → live
  self-test → allowlist → restart journey is not one accepted Express case.
- Slack: no first-class installer, runtime owner, status row, or QA owner. Local Socket Mode is a
  plausible Advanced design, not a shipped capability.
- WhatsApp: correctly marked unavailable. Official Business Cloud requires a Meta business/app,
  tokens, and public webhook infrastructure; consumer/unofficial libraries must not be presented as
  Express.
- Google/Microsoft: current advanced credential forms are not a novice one-click OAuth journey.

### P1 — QA ownership and release claims disagree

`brain_readiness.py` points to three nonexistent QA-owner paths: generic GlassHive, two connected-
account references to the same missing directory, and Code Interpreter. The actual nearby owners
use more specific names. `INST-001` is only partial in this audit; `INST-002` passes for the new
audit package but fails for separate pre-existing untracked reports; `INST-003` was not rerun; and
`INST-004` now fails against current source truth. The July fresh-clone report intentionally did not
start the stack, so it cannot
prove interactive Easy, first account, first connected provider, first response, schedules,
Feelings discovery, or restart. Release wording must not say final gates are closed while owning
case catalogs retain those gaps.

### P1 — Public/private boundary defect in search backup defaults

A search-engine dump request without an explicit dump directory wrote into the process working
directory, which was the public checkout. The audit immediately moved the generated dump into the
private backup area and removed the now-empty directory; no pre-existing file was removed and git
remained clean for that path. Product backup code must always supply an explicit private state
directory and fail if it resolves inside a public source tree.

## Full-View Evidence Checklist

| Evidence surface | Required question | Sanitized evidence pointer |
| --- | --- | --- |
| Requirement and use case | Which requirement and user journey are evaluated? | Installer docs, QA contract, decisive Express chain, and new `INST-005`–`INST-013`. |
| Code owning path | Which code owns it? | `install.sh`, `bin/viventium`, wizard, compiler, preflight, readiness, install summary, snapshot/restore, helper, playground launcher, LibreChat account menu and side-panel hooks. |
| Docs and nested repos | Are source, pins, nested histories, and feature truth aligned? | No; current/pin/dirty behavior differs and multiple docs contradict code or each other. |
| Scripts or harnesses | What automation ran? | Full release suite, shell syntax, isolated noninteractive wizard/compiler, doctor, Playwright, and computer-use. |
| Logs | Which sanitized logs support the result? | Doctor reported successful compile plus dirty/non-pinned component validation; browser had no error, only a framework future warning. |
| DB/state/persistence | What state was checked? | Private continuity inventory plus logical backup integrity and Mongo dry-run restore; no raw IDs or payloads published. |
| Generated/shipped artifact | Was output inspected? | Isolated compiler summary passed; exact shipped-pin full startup was not run. |
| Real user path | Which user surface was used? | Local login page, blank-submit validation, and unauthenticated Feelings redirect. |
| Visual/UX comparison | Did visible behavior match the target journey? | Partial. Login errors and auth redirect were honest; fresh registration, connection, answer, and Feelings discovery were not available. |
| Not run / blocked | What cannot be claimed? | Clean macOS install, first answer, live channel onboarding, restart, uninstall, full restore, Intel matrix, and exact-pin end-to-end acceptance. |

## User-Grade Evidence

- Surface exercised: real local Chrome/Playwright login surface and direct `/feelings` navigation.
- Real user path: open the local app signed out, submit an empty login form, and try to open
  Feelings directly.
- Visible outcome: login rendered; empty submission produced “Email is required” and “Password is
  required”; Feelings redirected to login while preserving a return target.
- Expanded/detail state: current established runtime exposed no registration link because
  registration is disabled; this is existing-user evidence only.
- Persistence/reload result: not applicable to the nonmutating signed-out path. No account or local
  data was created to avoid touching personal runtime state.
- Backend/log/DB confirmation: doctor passed prerequisites and config compilation while explicitly
  reporting dirty/non-pinned component checkouts; private backup integrity and logical Mongo restore
  dry run passed. The playground listener was wildcard-bound; loopback returned HTTP `200`, while a
  same-host non-loopback probe timed out.
- Final model/runtime wording check: the visible login errors and auth redirect were truthful; the
  installer/readiness wording is not truthful enough for release.
- Substitution check: source, history, tests, logs, backup archives, and model review support this
  audit; they do not substitute for the blocked clean-Mac user path, live provider request, first
  answer, restart, or browser-visible restore.

## Automated Evidence

```bash
viventium_v0_4/voice-gateway/.venv/bin/python -m pytest tests/release/ -q
bash -n install.sh
bash -n bin/viventium
bash -n scripts/viventium/restore.sh
bin/viventium doctor

audit_tmp="$(mktemp -d /tmp/viventium-express-audit.XXXXXX)"
viventium_v0_4/voice-gateway/.venv/bin/python scripts/viventium/wizard.py \
  --non-interactive --preset config.minimal.example.yaml \
  --output "$audit_tmp/config.yaml"
viventium_v0_4/voice-gateway/.venv/bin/python scripts/viventium/config_compiler.py \
  --config "$audit_tmp/config.yaml" --output-dir "$audit_tmp/runtime" --dry-run
```

Result summary:

- Final full release-suite rerun against the current dirty working tree: **958 passed, 8 skipped,
  3 failed** in 121 seconds.
  - Failure: pre-existing untracked dated QA reports lack required evidence-template sections.
  - Failure: one pre-existing untracked nightly health report contains a GlassHive runtime ID
    pattern. This does not prove the committed release is red; the recurring report-generation
    workflow still needs to be traced and corrected.
  - Failure: the RAG launcher lock concurrency test raced on a duplicate guard directory. The same
    test passed in the earlier full run and passed **5/5** immediate isolated reruns, classifying it
    as a reproducible-suite flake rather than a documentation regression.
- Shell syntax: PASS for installer, public CLI, and restore script.
- Isolated preset wizard: PASS; wrote only to a generated directory under `/tmp`.
- Isolated compiler dry run: PASS; selected native/local runtime and OpenAI connected-account
  primary auth, demonstrating the pre-browser dependency.
- Doctor: PASS for prerequisites/config; PARTIAL for delivery fidelity because dirty/non-pinned
  component checkouts were accepted and reported.
- Browser: PASS for signed-out login rendering, required-field errors, and auth redirect; BLOCKED for
  fresh registration and all authenticated onboarding.
- Local network boundary: FAIL because the playground process listened on wildcard port `3300` and
  the launcher does not pass Next's hostname option; actual LAN reachability was not proven.

## Findings

- Defects: backup false-success, overwrite-prone reconfigure, misleading Easy promise, configured
  versus ready drift, unverified bootstrap destination, mandatory prerequisite disclosure, missing
  Feelings control-panel entry, unsafe implicit search-dump location, and wildcard playground bind.
- Working-tree QA drift: the current full release suite is red due to pre-existing untracked QA
  evidence/public-safety files; those user-owned files were not changed during the audit. This is
  not sufficient evidence to label the committed release artifact regressed.
- Flakes: one RAG launcher lock concurrency race; it passed 5/5 isolated reruns after failing once
  in the final full suite.
- Environment issues: no isolated macOS VM or sacrificial Mac was available. Linux VM/container
  isolation cannot validate Keychain, Homebrew/Xcode dialogs, LaunchAgents/helper, native voice,
  TCC permissions, or authentic macOS first-run behavior.
- Residual risks: the full exact-pin journey, restore, Intel support, provider failure matrix,
  Telegram installer onboarding, Slack/WhatsApp roadmap, accessibility, cancellation at every
  stage, low-resource behavior, offline/proxy/TLS failures, rollback, and uninstall remain open.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots, emails, account identifiers, or customer data.
- [x] No conversation, message, session, call, Telegram, database, or provider request identifiers.
- [x] No private absolute paths, usernames, hostnames, machine names, raw runtime dumps, or personal configuration values.
- [x] Private backup data remains outside git with access restricted to the local user.
- [x] Public evidence uses only sanitized counts, statuses, commit identifiers, and conclusions.
- [x] No cloud, account, repository-remote, runtime-config, database, or live integration mutation was made.

## Release Decision

**Do not describe the current Easy Install path as one-command, nontechnical, fully safe, fully
covered, or release-ready.** Proceed through the remediation plan, then require the exact clean
public artifact to pass the complete macOS journey and an existing-user restore/upgrade journey from
cloned state. Until then, every broader completion claim is `PARTIAL` or `BLOCKED`.
