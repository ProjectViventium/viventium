# Easy Install Lifecycle And Safety QA — 2026-07-19

## Summary

- Result: **PARTIAL source-candidate acceptance; not public-release-ready**.
- Build/source under test: the local uncommitted parent and nested source candidate after the
  2026-07-19 installer fixes; this is not an immutable release artifact.
- Runtime/artifact under test: source-built Easy Install Native in a no-share Apple Silicon macOS
  VM, plus read-only inspection of the raw universal helper and a locally assembled helper bundle.
- Environment: macOS Apple Silicon VM for mutation; shared personal Mac for read-only safety
  inventory only; canonical npm-lock temporary checkout for focused LibreChat tests.
- Tester: Codex user-path QA with an independent visible Fable 5 Extra review-only pass.
- Related change: local Easy Install / Custom Settings Install, readiness, rollback, preservation,
  helper, loopback, Node 24, and QA-contract changes. This installer-audit workstream created no
  commit, stage, push, PR, or release; unrelated repository work continued independently.
- Public names: **Easy Install** and **Custom Settings Install**. The persisted compatibility values
  remain `express` and `custom` so existing configuration and upgrades do not break.
- Real user proof: a no-share Apple Silicon macOS VM passed Easy Install, rerun, restart, local
  account creation, automatic Connected Accounts handoff, provider authorization start/cancel,
  disconnected-provider recovery wording, Feelings discovery and persistence, failed-upgrade
  recovery, idempotent reinstall, preserve-data uninstall, and manual recovery of the tested
  synthetic config, Mongo user, and Feelings state.
- Physical-machine safety: strict identity verification and Viventium-only absence inventory passed
  on the available shared personal Mac. Installation was intentionally not run inside the personal
  login because a dedicated folder is not a security boundary.
- Automated proof: after the final upgrade and continuity hardening, the complete parent release
  suite passed with **1,072 passed, 7 skipped, 0 failed** in **172.45 seconds** with the supported
  Node 24 explicitly first on `PATH` and the declared Python dependencies supplied.
- Release blockers remain: signed/notarized immutable payload, truly vanilla no-developer-tools
  Mac, completed provider grant and persistent first answer, public full-payload restore, broad fault
  and inclusive-UX matrices, physical Docker comparison, and nested pin/build/payload alignment.

## Scope Run

| Case ID | Result | Evidence | Notes |
| --- | --- | --- | --- |
| `INST-001` | PARTIAL | Real install/rerun/start/stop, failure and recovery paths in the VM | Exact immutable payload and broad fault matrix remain open |
| `INST-002` | PASS | QA template and public-safety release tests; sanitized report review | Raw local evidence intentionally remains outside the public tree |
| `INST-003` | PARTIAL | Easy Install defers worker/nightly setup; preservation contracts pass | Later activation and established-user live upgrade not run |
| `INST-004` | PARTIAL | Minimal preset, generated config, readiness rows, browser core | Provider first answer and all optional brain surfaces not proven |
| `INST-005` | PARTIAL | Positive producer marker plus schema/domain/hash/bounded-content validation, metadata/marker-less/private-helper refusal, standard-library-only no-mutation validation, and full-tree uninstall preservation; validator does not call this recoverable | Public full-payload capture/apply, Mongo semantic proof, and browser-visible independent-target restore absent |
| `INST-006` | PARTIAL | Reconfigure backup and missing-secret atomic failure | Full helper settings/crash/reload matrix absent |
| `INST-007` | PARTIAL | Destination and manifest verifier automation | Public bootstrap still compiles mutable source |
| `INST-008` | PARTIAL | Real Easy Install Native browser lifecycle in no-share VM | Signed payload and first useful provider answer absent |
| `INST-009` | PARTIAL | Unprobed core/Brain Setup rows now say Configured; live core says Running | Full provider/channel failure taxonomy absent |
| `INST-010` | PARTIAL | Account handoff, disconnected state, OAuth start/cancel/retry | Grant/answer/expiry/reauth/revoke and channels absent |
| `INST-011` | PARTIAL | Isolated VM install, retry, rollback, restart, uninstall | Vanilla, low-resource, network, interruption and Intel lanes absent |
| `INST-012` | PARTIAL | Real-browser Feelings discovery, nine bands and persistence | Accessibility/degraded-provider/shipped artifact lanes absent |
| `INST-013` | PARTIAL | Loopback listeners and non-loopback refusal in VM | Second-host, firewall, remote and optional-service lanes absent |
| `INST-014` | PARTIAL | Native core profile, lifecycle and browser setup | Exact no-developer-tools payload and Docker delta absent |
| `INST-015` | BLOCKED | Raw helper and release architecture inspected | No signed/notarized immutable app/runtime payload exists |
| `INST-016` | BLOCKED | Guest prerequisites inventoried | VM image contained dormant developer tools |
| `INST-017` | PARTIAL | Synthetic local user and OAuth cancellation/retry | No provider grant or persistent first/second answer |
| `INST-018` | PARTIAL | Required-domain artifact ledger, standard-library-only validation, overlap/expansion/no-mutation refusal, and full App Support preservation/manual supporting recovery | No public one-click complete apply or independent-target browser recovery |
| `INST-019` | PARTIAL | Dirty-upgrade refusal/service recovery and uninstall recovery | Remaining fault-injection matrix not run |
| `INST-020` | PARTIAL | Source digest, universal architecture and local assembled-bundle check | Raw x86_64 slice is unsigned; Developer ID/notarization/headed QA absent |
| `INST-021` | BLOCKED | Strict read-only physical safety inventory only | Docker/install mutation refused inside a shared personal login |
| `INST-022` | FAIL | Eleven nested heads/pins/dirty states compared | Dirty LibreChat/GlassHive content is not pinned or shipped |
| `INST-023` | BLOCKED | Ordinary desktop Chromium only | Dedicated inclusive-UX matrix not run |
| `INST-024` | PARTIAL | Six source surfaces and VM runtime use Node 24 | Exact-payload process provenance absent |

This installer-audit workstream performed no commit, stage, push, PR, release, cloud configuration,
provider grant, external message, channel mutation, personal-account login, or personal-data
inspection. Unrelated repository work continuing from the same login is outside this claim.

## Natural User Use Case Checklist Run

| Use Case ID | Natural user action | Real surface used | Result | Visible evidence | Supporting evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | Install, rerun, stop, start, fail and recover | Installer/CLI/helper in no-share VM | PARTIAL | Healthy core plus clear recovery output | Timings, processes, listeners, logs and state | Exact signed payload and wider recovery matrix |
| `INST-UC-002` | Review the public-safe evidence record | QA report and release-test surface | PASS | Sanitized evidence is reviewable | QA contract and safety scans | Raw evidence remains private by design |
| `INST-UC-003` | Rerun evidence checks after report/artifact changes | Release-test surface | PASS | Final wording and evidence remain accepted | Focused and complete parent suites | None for the evidence-record case |
| `INST-UC-004` | Reach core chat before worker/nightly setup | Easy Install preset and VM runtime | PARTIAL | Optional worker systems are deferred | Generated config and status rows | Later guided activation not run |
| `INST-UC-005` | Compare Easy Install and Custom Settings Install readiness | Wizard/compiler/status/browser | PARTIAL | Correct labels, minimal core and Configured-vs-Running truth | Config, summary and browser evidence | Every optional feature-owner journey not run |
| `INST-UC-006` | Create and independently restore the promised backup | CLI preserve/uninstall plus browser | PARTIAL | Metadata-only restore is refused; manual same-target recovery returns synthetic state | Hashes, counts, Mongo and browser state | Public independent-target restore absent; structural bundle validation is not restore proof |
| `INST-UC-007` | Change one established-user setting and fail safely | CLI/wizard/compiler | PARTIAL | Reconfigure backs up; missing secret fails without canonical drift | Candidate/canonical hashes and logs | Full helper/crash/reload matrix absent |
| `INST-UC-008` | Bootstrap empty, valid, unrelated, dirty and corrupt targets | Bootstrap verifier automation | PARTIAL | Invalid targets/references are refused | Manifest, target identity and rollback tests | Immutable signed public payload absent |
| `INST-UC-009` | Complete one command through account, answer, Feelings and restart | Installer/helper/Playwright browser in VM | PARTIAL | Core, account handoff, cancel/retry and Feelings persist | Browser, API, DB and lifecycle evidence | Provider grant, useful answer, channel and public restore absent |
| `INST-UC-010` | Distinguish configured, running and failed states | Install summary, Brain Setup and CLI | PARTIAL | Unprobed core and configuration-only rows say Configured | Shared readiness contract and focused tests | Complete live provider/channel failure taxonomy absent |
| `INST-UC-011` | Connect, test, repair and revoke providers/channels | Connected Accounts in real Chromium | PARTIAL | Disconnected state, OAuth start/cancel/retry and repair guidance work | UI and backend state | Grant, self-test, expiry, reauth, disconnect, revoke and channel lanes absent |
| `INST-UC-012` | Exercise constrained/interrupted/recovery combinations | Installer/CLI in no-share VM | PARTIAL | Tested failures preserve or recover prior state | Exit codes, logs, hashes and health probes | Vanilla/low-resource/network/reboot/Intel breadth absent |
| `INST-UC-013` | Discover Feelings from ordinary chat and recover setup states | Playwright real Chromium | PARTIAL | Nine-band page and enabled toggle persist | Browser plus DB confirmation | Completed/degraded provider and inclusive-UX matrix absent |
| `INST-UC-014` | Verify local-only services reject non-loopback access | VM sockets and probes | PARTIAL | Core remains usable over localhost only | Listener and refusal evidence | Second-host, firewall, remote and optional-service lanes absent |
| `INST-UC-015` | Install Native without Docker/tools, get an answer, then add capability | VM plus read-only physical safety gate | PARTIAL | Source-built Native core lifecycle works; unsafe personal-login Docker mutation was refused | VM browser/runtime plus physical absence inventory | Signed no-tools payload, first answer, optional capability and Docker delta absent |
| `INST-UC-016` | Use one Node major from install through restart | Source contracts and VM process | PARTIAL | Tested source/runtime paths use Node 24 | Tests, generated config and process evidence | Immutable-payload process provenance absent |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

| Feature | Requirement | User use case | QA case | Expected result | Actual evidence | Remaining gap |
| --- | --- | --- | --- | --- | --- | --- |
| Easy Install | Installer requirement doc | One command reaches a healthy local core | `INST-001`, `INST-008`, `INST-014` | Minimal choices, truthful progress, resumable failures | A corrected retry with warmed dependency/build artifacts reached healthy core in 32.15 s; rerun 18.66 s; API/web healthy | Cold signed-payload timing, vanilla base, persistent first answer |
| Custom Settings Install | Installer requirement doc | Change advanced settings without damaging a stable setup | `INST-006` | Candidate compile, clear error, atomic preservation | Missing Keychain reference returned one user-facing error, no traceback, exit 1, canonical hash unchanged | Helper UI, preview, crash/reload breadth |
| Readiness | Installer requirement doc | User can tell configured from working | `INST-004`, `INST-009` | Configuration alone never says Ready | In the real VM CLI, the same healthy runtime rendered core services as Configured without `--probe-live` and Running with it; Brain Setup asks for live/self-test; release regressions pass | Complete provider/channel live error taxonomy |
| Account onboarding | Connected Accounts contract | New user is guided to connect an account | `INST-010`, `INST-017` | Automatic handoff, cancel/retry, actionable missing-auth result | Registration redirected to account setup; OpenAI/Anthropic were visibly Disconnected; OpenAI authorization opened the official provider site; cancel recovered; disconnected chat named the exact repair path | Grant, self-test, first/second answer, expiry, reauth, revoke |
| Feelings | Emotional Cortex requirement | Discover and use Feelings from normal chat | `INST-012` | Navigation, visible state, persistence | Right control exposed Feelings; nine bands rendered; enabled toggle persisted across refresh, restart, reinstall, failed-upgrade recovery, and manual uninstall recovery; DB state agreed | Keyboard/mobile/a11y, degraded-provider, signed delivery alignment |
| Local privacy | Local network contract | Local services are not reachable from LAN by default | `INST-013` | Explicit loopback listeners | API, web, Mongo, and scheduler listened on loopback; guest non-loopback probes failed | Second physical host, firewall modes, optional services, declared remote modes |
| Upgrade safety | Installer requirement doc | Unsafe upgrade is refused before pull/stop/component mutation | `INST-019` | Structured blocker, no false rollback claim, continuity error never auto-restarts | Post-audit automation plus a live no-share VM returned `1` for running/no-restart and `3` for dirty selected LibreChat before audit/stop/pull; HEAD, config hash, audit count, API, and web were unchanged. The earlier VM run proved only availability recovery, not rollback | Successful update and late-failure live lanes, headed helper dialog, corrupt payload, crash/reboot, downgrade and migration breadth |
| Uninstall preservation | Continuity requirement | Preserve data and recover it | `INST-005`, `INST-018`, `INST-019` | Drained full state is recoverable | Uninstall moved the full App Support tree to a private recovery root; config hash and Mongo payload were preserved; manual recovery restored the user and Feelings UI | One-command snapshot/restore into an independent target |
| macOS helper | Installer/helper contract | Install without source drift and pass platform security | `INST-020`, `INST-024` | Matching universal signed/notarized helper | The source aggregate matches `source.sha256`, the exact raw binary matches `binary.sha256`, and the artifact contains arm64/x86_64. Adjacent hashes detect drift/corruption but do not prove publisher identity. An installer-assembled local bundle verifies ad hoc, while strict raw verification still fails | Bind both digests in an immutable signed manifest, sign both raw slices, obtain Developer ID/notarization, and run headed permission/login/Keychain acceptance |
| Physical Docker delta | Shared-profile contract | Docker adds capabilities without changing core lifecycle | `INST-021` | Safe side-by-side physical comparison | Machine identity and absence inventory only | No isolated Standard user/VM was available in the personal login; Docker lane not run |

## Full-View Evidence Checklist

| Evidence layer | Result | Evidence |
| --- | --- | --- |
| Owning requirements/docs | PASS | Installer, public/private, runtime QA map, stable runtime, continuity, and Feelings requirements were reconciled |
| Trigger and public entrypoints | PARTIAL | `install.sh`, public CLI, helper install, configure, upgrade, restart, snapshot refusal, and uninstall ran from the source candidate; immutable public release did not |
| Wizard/compiler/generated output | PASS for tested paths | Public minimal preset compiles without pre-existing Keychain state; Custom Settings Install missing-secret rollback is clean; internal values remain compatible |
| Runtime/process/listeners | PASS for tested core | API/web/Mongo/scheduler health and loopback state confirmed; optional services were deferred as designed |
| Browser-visible result | PARTIAL | Registration, login, Connections, disconnected chat, OAuth launch/cancel, Feelings, refresh and restart were exercised in real Chromium | No granted provider or rendered model answer |
| Persistence/DB/state | PARTIAL | Synthetic user and enabled Feelings state agreed in Mongo and survived lifecycle operations | Complete chat/memory/RAG/schedule/auth/channel continuity ledger not run |
| Owner-state safety backup | PASS for audit safety; not a product restore claim | Before final QA, canonical config, generated/runtime configuration, private user-state records, database-native Mongo and SQLite exports, and dormant RAG storage were copied to a private mode-0700 root outside the repo and active App Support tree; gzip/archive dry-run, SQLite integrity, permissions, and config hash passed | Keychain secrets and rebuildable Meilisearch/ephemeral sandbox caches were intentionally not exported; provider reauthentication remains required |
| Logs and failure wording | PASS for tested failures | Missing secret produced no traceback; upgrade recovery now says partial on-disk state instead of claiming rollback; disconnected provider named one repair action |
| Prebuilt/shipped artifact | PARTIAL | Source and binary SHA-256 sidecars match the exact universal arm64/x86_64 helper; only the installer-assembled local bundle verifies ad hoc. Adjacent sidecars are integrity evidence, not publisher provenance | Signed immutable manifest, raw-slice signing, Developer ID/notarization, and immutable runtime payload are absent |
| Nested component/pin alignment | FAIL | LibreChat and GlassHive HEADs are parents of their configured merge pins but have identical committed trees; their 153 and 4 dirty worktree entries are unpinned. Seven other clean component checkouts have genuine tree drift from their pins | Commit intended nested changes, update parent pins, then align client build, payload and installed hashes before release |
| Public/private safety | PASS for this report | Synthetic values and placeholders only; no personal identity, hostname, fingerprint, credential, local absolute path, raw ID, or private screenshot |

## User-Grade Evidence

- Surface exercised: Easy Install and Custom Settings Install CLI flows, the macOS helper artifact,
  and the built LibreChat UI in real Playwright Chromium inside a no-share Apple Silicon VM.
- Real user path: install, register, log in, inspect Connected Accounts, open/cancel provider
  authorization, attempt disconnected chat, open and enable Feelings, refresh, restart, reinstall,
  refuse a dirty upgrade, preserve-data uninstall, and manually recover.
- Visible outcome: the core became healthy, account setup opened automatically, disconnected chat
  named one repair action, Feelings rendered nine bands, and tested failure paths retained the prior
  configuration or service.
- Expanded/detail state: OpenAI and Anthropic cards visibly showed Disconnected; the provider login
  opened on the official domain; the Feelings toggle showed enabled; post-change upgrade output
  refuses unsafe mutations early and no longer claims that old on-disk state was restored.
- Persistence/reload result: the synthetic user and enabled Feelings state survived refresh,
  service restart, idempotent reinstall, failed-upgrade recovery, and manual recovery after
  preserve-data uninstall.
- Backend/log/DB confirmation: loopback listeners and health probes agreed with the UI; Mongo held
  one synthetic user and the enabled nine-band Feelings state; config hashes and recovery counts
  matched; no browser console errors occurred.
- Final model/runtime wording check: no model answer was possible without a provider grant; the
  runtime correctly said the account was not connected and directed the user to Connected Accounts
  instead of claiming success.
- Substitution check: automated tests, source inspection, helper hashes, logs, API responses, and DB
  state support the real installer/browser evidence but cannot replace the unrun signed-payload,
  provider-answer, public-restore, headed macOS-security, Docker, or inclusive-UX user paths.

### Easy Install happy path

1. The first VM attempt exposed a real first-run Groq/Keychain dependency. The public minimal preset
   and compiler were corrected so Easy Install does not require a pre-existing provider secret.
2. The corrected retry reached healthy API and web services in 32.15 seconds after dependency/build
   artifacts had been warmed by the first attempt. This is not a cold-install performance result.
   Earlier cold source builds exhausted a 2 GiB heap and API readiness could take several minutes;
   cold immutable-payload timing remains unmeasured.
3. Stop completed in 8.51 seconds. Launch handed off in 0.51 seconds and the API was healthy about
   16 seconds later.
4. Reconfigure completed in 4.06 seconds and created a prior-config backup.
5. Idempotent reinstall completed in 18.66 seconds without losing the synthetic user or Feelings.

### First clueless-user browser journey

1. Registration created a synthetic local user and redirected to login with the account-setup
   return target.
2. Login automatically opened Connected Accounts.
3. OpenAI and Anthropic were visibly Disconnected and offered Connect actions.
4. OpenAI Connect opened the official provider login in a second tab. Closing it restored the
   Connect state so the user could retry.
5. Sending a chat while disconnected showed: OpenAI is not connected, open Settings > Account >
   Connected Accounts, sign in, then retry. It did not fail silently or show a generic error.
6. Feelings was discoverable from the ordinary right control, rendered nine bands, and its enabled
   toggle survived refresh and the later lifecycle operations.
7. The browser console contained no errors; one non-fatal React Router future warning remained.

No real provider credential or account was used, so the first-answer release gate is `PARTIAL`.

### Unhappy paths and recovery

| Path | Result | Visible/system outcome |
| --- | --- | --- |
| Missing Easy Install provider secret | FAIL -> fixed -> PASS | Secret is optional until browser onboarding; generated runtime contains no unresolved secret placeholder |
| Missing Custom Settings Install secret | PASS | One clear failure, no traceback, canonical config unchanged |
| Disconnected provider chat | PASS | Exact setup location and retry action shown |
| OAuth popup cancel/retry | PASS | Connect action recovers and can be retried |
| Dirty nested component during upgrade | PASS for source-level refusal; PARTIAL live recovery | Structured inspection exits `3` before pull/stop/component mutation. The earlier VM failure restarted service from current on-disk state; that was availability compensation and did not prove the upgrade remained unapplied. Post-change live rerun remains open |
| Repeated install | PASS | Existing synthetic user and Feelings state persist |
| Metadata-only snapshot restore | PASS for truthfulness | Public restore refuses it rather than claiming recovery |
| Arbitrary marker-less/corrupt restore | PASS for truthfulness | Positive v1 marker, complete domain coverage, typed artifacts, size/hash/content checks, and path safety are required before target mutation |
| Preserve-data uninstall | PASS for preservation | Full drained App Support tree moved to private recovery storage; active runtime/helper/process removed; repo retained |
| Manual recovery after uninstall | PASS as supporting proof | Config hash, Mongo data, local account, and Feelings state return |
| Public one-click restore | BLOCKED | Current public snapshot remains metadata-only |
| Signed/helper security prompts | BLOCKED | Headed Developer ID/notarization/Keychain/login-startup lane was not available |

### Adversarial upgrade/continuity continuation

The final sanity pass found that the prior upgrade recovery wording overstated what the product did.
There is no source/config/component rollback transaction: restarting after a late failure launches
the current on-disk state, which may already be partially changed. The implementation and evidence
were corrected rather than preserving that claim.

Post-change automated evidence:

- `upgrade --check` observes the remote with `git ls-remote`, does not change `FETCH_HEAD`, and does
  not create App Support state
- a dirty selected component at its exact pin returns exit `3`; a clean selected HEAD mismatch is
  `component_refresh_required` and returns `0`; an unselected dirty component does not block
- valid JSON blocker details remain visible in the macOS helper when the CLI returns nonzero
- a running stack without `--restart`, an untrustworthy pre-audit, and a failed stop abort before
  pull/component mutation; `--allow-dirty` requires `--skip-pull`
- post-continuity `error` disables automatic restart, and generic failure recovery explicitly says
  the upgrade may be partially applied
- the final continuity/upgrade/helper/label gate passed **148 tests**; the helper fallback rebuilt as a universal
  `arm64`/`x86_64` binary and both source and binary digests match
- on the retained no-share guest, running/no-restart exited `1` before a new continuity audit and
  dirty-selected-LibreChat with `--restart` exited `3` before stop/pull/component mutation; in both
  runs HEAD, canonical config hash, and the four-file audit count were unchanged and API/web stayed
  HTTP 200
- the guest's public `upgrade --check --json` also returned `3` with the structured LibreChat
  `dirty_worktree` result while the pre/post `FETCH_HEAD` digest matched
- the guest helper installer selected the shipped prebuilt, assembled a universal app bundle,
  passed strict local code-sign verification, relaunched the helper process, and left API/web HTTP
  200; this is not Developer ID/notarization or a headed modal pass

Current local component evidence is intentionally non-mutating: LibreChat and GlassHive are blocking
dirty selected checkouts, while seven clean managed checkouts are refreshable. No nested work, pin,
commit, or remote state was changed. The post-change no-share guest proved both refusal paths with
unchanged HEAD/config/audit count and healthy API/web, and installed/relaunched the rebuilt universal
helper. This improves fail-closed behavior but does not clear `INST-022`; the headed helper dialog,
successful-update, and late-failure lanes remain open.

The same continuation closed the most dangerous restore-validation hole. Restore no longer treats
an arbitrary directory as recoverable merely because `.viventium-metadata-only` is absent. A
positive v1 marker and complete manifest now require config, logical Mongo, files, schedules,
Recall/RAG rebuild policy, auth reauthentication policy, and channels exactly once. Declared payload
files carry role, capture method, schema, media type, size, and SHA-256, with bounded
config/gzip/SQLite/JSON checks and traversal/collision/symlink/hardlink/undeclared-file rejection.
The standard-library-only validator rejects boolean schemas, source/target overlap, and archive
expansion abuse. `--validate-only` leaves an absent independent target absent. The apply path exits
`4` before live audit, channel copy, Recall marker, or target mutation; validation is not called
restore and Mongo semantic validation is explicitly not performed. This advances `INST-005`/`INST-018` but leaves
complete capture/apply and browser-visible independent recovery blocked.

### Shared personal-Mac safety decision

The connection used strict known-host verification and key-only authentication. Read-only checks
confirmed the target class, current macOS, resources, absence of Viventium-specific install/config
state, and absence of common installer dependencies. A mode-0700 dedicated QA root was created for
Viventium evidence only. No unrelated file, app, browser, message, account, VPN, SSH configuration,
Keychain item, helper, or personal Viventium state was inspected or changed.

Installation stopped at the safety gate: a folder inside the same personal login does not isolate
Keychain, LaunchAgents, TCC, package managers, ports, Docker contexts, or App Support. The supported
next physical lane is a separate disposable Standard macOS user or a no-share VM. The Docker delta
must wait for that boundary.

At final closeout the same strict SSH command returned connection refused on the temporary relay.
Host-key checks were not weakened and no alternate path was attempted, as required by the handoff.
The dedicated no-share Tart guest was shut down through `bin/viventium stop`; its exact two-port
loopback SSH forward was then closed and the VM was retained in a stopped state for reproducibility,
not deleted. Three stale bootstrap helper processes tied to the first disposable guest attempt were
also terminated; the final scoped-process check returned zero. The physical target could not be
re-entered for teardown after the relay expired; the last verified mutation there remained limited
to the dedicated mode-0700 Viventium QA root.

## Automated Evidence

Commands were run from the repository root unless the command changes directory. The temporary
LibreChat path is a sanitized stand-in for a no-owner-state canonical npm-lock copy.

```bash
PATH="/opt/homebrew/opt/node@24/bin:$PATH" uv run --offline --with pytest --with pydantic --with PyYAML --with requests --with httpx --with jsonschema --with croniter --with fastapi -- python -m pytest tests/release/ -q
uv run --offline --with pytest --with PyYAML -- python -m pytest tests/release/test_continuity_bundle.py tests/release/test_continuity_audit.py tests/release/test_cli_upgrade.py tests/release/test_macos_helper_install.py tests/release/test_stable_dev_runtime_workflows.py tests/release/test_install_experience_labels.py -q
bash -n bin/viventium install.sh scripts/viventium/restore.sh scripts/viventium/install_macos_helper.sh scripts/viventium/build_macos_helper_fallback.sh viventium_v0_4/viventium-local-state-snapshot.sh viventium_v0_4/viventium-librechat-start.sh
python3 -m py_compile scripts/viventium/continuity_bundle.py scripts/viventium/upgrade_check.py
cd /tmp/viventium-librechat-clean/repo && npm run build:packages
cd /tmp/viventium-librechat-clean/repo/client && npm test -- --runInBand --watch=false src/components/Feelings/FeelingsView.spec.tsx
cd /tmp/viventium-librechat-clean/repo/client && npm run typecheck
```

The final type-check remains nonzero because of broad pre-existing LibreChat diagnostics outside the
audited feature. After typing the synthetic Feelings trail fixture against the real data contract,
the type-check emits no `Feelings` diagnostic; its focused 13-test view suite passes.

| Check | Result |
| --- | --- |
| Complete parent release suite | PASS — final rerun after upgrade/continuity hardening: 1,072 passed, 7 skipped, 0 failed in 172.45 s with supported Node 24 explicitly first on `PATH` and declared Python dependencies supplied |
| Focused installer safety gate | PASS — 148 continuity, upgrade, helper, update-check, and install-label tests |
| Interpreter-path control | PASS — the upgrade fixture and public restore validator pass when the executing Python path contains both directory and filename spaces; stock-standard-library bundle validation also passes without PyYAML/site packages |
| Real VM configured-versus-live summary | PASS — unprobed CLI showed `Viventium is configured` and core `Configured`; probed CLI showed core `Running`; no unprobed `Ready` row |
| Scheduling Cortex nested suite | PASS — 113 passed plus 6 subtests |
| macOS helper source/architecture checks | PASS for integrity/alignment — aggregate sources match `source.sha256`, the exact raw executable matches `binary.sha256`, and the artifact contains arm64/x86_64; adjacent hash files do not provide publisher provenance |
| Helper signature verification | PARTIAL — an installer-assembled local bundle verifies ad hoc, but strict verification of the raw prebuilt fails because the x86_64 slice is unsigned; neither surface has a Developer ID Team ID or notarization |
| Owner-state safety backup | PASS — 389 MiB, 3,851 files, canonical config hash match, Mongo gzip plus restore dry-run, both SQLite integrity checks, and mode 0700 parent/payload ownership verified; active services were not stopped or changed |
| Visible Fable 5 Extra second opinion | PASS for the audit package only — the same Fable 5 Extra session found F1-F7 plus four minor residuals, then independently re-inspected every correction. Its focused run reproduced 148 passed; its alternate full environment collected the same 1,079 tests (1,077 passed, 2 skipped). It found no new material defect and retained PRODUCT RELEASE: PARTIAL |
| Shell syntax and source contracts | PASS for affected installer/launcher/helper surfaces |
| LibreChat real built browser path | PASS for the tested registration/account/Feelings/disconnected states |
| LibreChat focused Feelings Jest tests | PASS in a temp-only canonical npm-lock install — 62 passed across client view (13), API package service/kernel/config (28), data-schema persistence (4), and server route/telemetry (17); the owner checkout failure was dependency skew from an untracked pnpm/Jest 30.4.x install versus the npm lock's Jest 30.2.0 |

The parent-suite skips are environment/opt-in cases and are not counted as acceptance passes.
The real built browser result and the clean temp Jest result support the affected LibreChat behavior,
but neither makes the delivery-alignment failure disappear. No dependency repair was attempted in the
owner checkout; the canonical test install used a private temporary HOME and npm cache.

## Original Request Sanity Matrix

| Original requirement | Verdict | Evidence / remaining gap |
| --- | --- | --- |
| Inventory the project lifecycle and installer-related history | PASS for documentation | Timestamped all-ref parent inventory plus installer/delivery path ledger and nested-repo state map; see the lifecycle inventory |
| Explain new-machine setup versus the reliable owner setup | PASS for audit analysis | New-user/owner deltas are mapped across prerequisites, config, provider state, optional services, helper, persistence, and delivery artifacts |
| Use a secure local sandbox and protect personal data | PARTIAL user-path coverage | No-share VM carried mutations; owner state received a verified private backup; shared personal Mac was read-only and correctly refused for installation because a folder is not isolation |
| Make no cloud/push/publish/external-message changes | PASS for this workstream | No stage, commit, push, PR, release, provider grant, channel action, or external message; unrelated same-login activity is excluded from this claim |
| Audit every nested repo/feature with literal 100% coverage | PARTIAL | Broad inventory and 1,072-pass parent suite exist, but exact delivered pins, signed payload, every optional feature, inclusive UX, Docker, Intel, and full fault matrix remain open |
| Independent Fable 5 Extra review with the original context | PASS for second-opinion process | The visible same-session review found material defects, rejected the superseded package, rechecked every remediation and residual, reproduced the focused gate, reconciled the full collected total, and kept the product verdict PARTIAL |
| Cover every installer happy/unhappy path and guarantee reliability | PARTIAL | Core install/rerun/recovery/account-cancel/Feelings paths ran; provider grant, first/second answer, low-resource/network/interruption/reboot/migration and signed-artifact lanes remain open |
| One command, then connect accounts, then everything works | PARTIAL | Easy Install reaches local core and browser account handoff; completed provider grant, self-test, persistent answers, and owner-parity are not proven |
| Deep current web research and popular OSS inspiration | PASS for research package | Evidence-ranked installer/onboarding patterns and separate inspiration inventory are documented; popularity evidence is not treated as product acceptance |
| Telegram, WhatsApp, Slack and other channel design | PARTIAL / design only | Telegram-first and Custom Settings channel journeys are specified; WhatsApp remains unavailable and no end-to-end channel grant/send/receive/revoke lane passed |
| Groq key and Grok reliably available in LibreChat | PARTIAL | Configuration and distinct-provider wording are covered; live key validation, answer, quota, expiry, repair and revoke are not proven |
| Feelings is a discoverable flagship feature | PARTIAL | Real browser discovery, nine bands, toggle persistence, API/DB agreement and lifecycle survival passed; inclusive UX, degraded-provider and signed-delivery lanes remain open |
| Rename the install choices | PASS | Active user-facing paths use **Easy Install** and **Custom Settings Install**; internal `express`/`custom` values remain solely for backward compatibility |

This matrix is the completion gate: no lower-level automated or source result upgrades a `PARTIAL`
row when its required real user surface remains unrun.

## Findings

- Defects: the locally scoped installer/readiness/rollback/preservation defects listed below were
  fixed; raw helper signing and delivery alignment remain open defects.
- Regressions: no affected-path regression was found in the parent release suite or the focused
  canonical Feelings suites; repository-wide LibreChat type-check debt remains nonzero.
- Flakes: none observed in the recorded parent or focused nested reruns.
- Environment issues: the VM was not truly vanilla, its corrected timing used warmed build artifacts,
  the shared personal login was not a safe mutation boundary, and the owner LibreChat checkout had
  untracked pnpm/Jest dependency skew.
- Owner-state protection: a private verified configuration/database safety backup now exists outside
  both the repository and active runtime. It supports rollback of this audit's relevant state but is
  not represented as the still-missing public full-payload restore product.
- Residual risks: every item in Open release blockers remains a release gate rather than an implied
  future nice-to-have.

### Fixed in the local working tree

- Primary installer choices, active setup/readiness guidance, README examples, and browser-QA
  messages now say Easy Install and Custom Settings Install; internal persisted values and dated
  compatibility filenames remain backward compatible.
- Easy Install's public preset is a genuinely minimal local core and no longer requires terminal
  Groq/worker/voice/search/channel setup before browser onboarding.
- Configuration-only setup never claims Ready.
- `preflight --fix` dead guidance now points to the supported apply action.
- Legacy launcher behavior stays legacy when no install-experience marker exists.
- Configure provisions Easy Install prerequisites and rolls back on prerequisite failure.
- Helper source and binary sidecars agree with the current aggregate source and exact universal raw
  executable; the installer verifies both before using the prebuilt. The adjacent sidecars do not
  prove publisher identity, and release signing remains open.
- Helper install/uninstall cleanup is limited to Viventium-owned scripts and known launch state; it
  no longer reads or rewrites shell history, zsh sessions, or Terminal saved state.
- Scheduler and other tested core services explicitly bind to loopback.
- Unsafe upgrades are refused before pull/stop/component mutation where current state is not
  trustworthy; late-failure recovery may restart the current partially applied on-disk state and
  is never described as rollback.
- A running-stack upgrade stops before pull, rechecks component alignment structurally after
  bootstrap, installs the helper without launching it, and relaunches only after an accepted
  continuity result and successful runtime restart.
- Public update checking and restore validation do not bootstrap or create App Support. Restore
  validates with standard-library Python, refuses overlap/unsafe bundles, and performs no partial
  target/channel/Recall mutation while the transactional apply engine is absent.
- Custom Settings Install configuration failure no longer falls through into a traceback.
- Preserve-data reset/uninstall drains and moves the full App Support state instead of copying four
  files and deleting the databases.

### Open release blockers

1. Build, sign, notarize, publish, and verify an immutable versioned Viventium app/runtime payload.
2. Prove that exact payload on a pristine supported Mac with no Git, Homebrew, CLT, Python, Node,
   pnpm, uv, or Docker before first answer.
3. Complete a synthetic provider grant, self-test, first and second rendered answers, refresh,
   restart, denial, wrong account, expiry, quota, network, reauth, disconnect, and revoke.
4. Implement and prove a complete public backup/restore payload across chats, saved memory, RAG,
   schedules, auth/provider state, channels, config, runtime selection, and reauth truth.
5. Run low disk/RAM, offline/DNS/TLS, corrupt/interrupted payload, occupied ports, double install,
   crash/reboot, rollback/downgrade, explicit-delete uninstall, and migration matrices.
6. Complete Developer ID/notarization/Gatekeeper/Keychain/SMAppService/login-startup headed QA.
7. Align every nested commit, parent pin, built client, payload, and installed hash.
8. Run keyboard, screen-reader, narrow/mobile, localization, reduced-motion, and high-contrast QA.
9. Run the physical Native-versus-Docker delta only in a disposable macOS user/VM boundary.
10. Prove hostile/unrelated existing-target refusal and Git-hook-safe immutable bootstrap behavior.
11. Complete the loopback/firewall/second-LAN-host/declared-remote-mode/optional-service matrix.
12. Run an established-user live upgrade/migration/rollback journey on a disposable restored clone.
13. Resolve bundled MongoDB redistribution/licensing and publish the Intel support decision.

### Future integrations and skills

- Telegram is the first optional channel: guided BotFather setup, Keychain token, `getMe` test,
  allowlist pairing, polling-conflict recovery, synthetic send/receive, restart, disconnect/revoke.
- Slack belongs in Custom Settings Install initially because local Socket Mode still requires an app,
  app token, bot OAuth, scopes, and workspace administration.
- Consumer WhatsApp is not supported. Official WhatsApp Business Cloud requires Meta business/app
  onboarding and a public webhook boundary; unofficial personal-account libraries are rejected.
- Groq API and xAI API/Grok models must remain visibly distinct. Consumer Grok access is not an xAI
  API entitlement.
- Community skills remain disabled by default until exact digest/signature, license, permissions,
  filesystem/network/account scope, secret references, review, update, disable, revoke, and removal
  lifecycles are implemented.

## Public-Safety Review

- [x] Synthetic account/data only.
- [x] No password, token, cookie, OAuth state, SSH key, host fingerprint, personal email, username,
  machine name, local absolute home path, raw database ID, or private runtime identifier recorded.
- [x] No personal files, messages, browser data, accounts, applications, or unrelated configuration
  inspected.
- [x] This installer-audit workstream made no cloud mutation, commit, stage, push, PR, release,
  external message, or channel action; unrelated same-login repository activity was not attributed
  to this audit.
- [x] Shared personal-Mac installation refused when the isolation boundary was insufficient.
- [x] Raw screenshots, traces, logs, and recovery payloads remain local and untracked; this report
  records only sanitized conclusions and counts.

## Release Decision

**Do not market or publish the current source candidate as a brainless one-command finished
installer.** It is materially safer and the tested Easy Install core is useful, but public release
readiness is still **PARTIAL** until the exact signed payload, pristine-Mac first answer, full public
restore, broad recovery/security/inclusive-UX matrices, physical Docker delta, and delivery-chain
alignment pass.

The correct current promise is: **Easy Install Native source candidate for continued local QA**.
Custom Settings Install is available for explicit advanced configuration, with the tested
missing-secret transaction now failing safely.
