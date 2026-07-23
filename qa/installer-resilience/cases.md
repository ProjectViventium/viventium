# Installer Resilience QA Cases

## Case ID Convention

Use stable `INST-NNN` IDs for installer resilience cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `INST-001` | Install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | User-visible behavior matches source, docs, persisted state, and logs | installer/CLI/helper, generated env, status output | `tests/release/test_config_compiler.py` plus user-grade QA when visible | PARTIAL 2026-07-21; Native and isolated Docker source-candidate install/recovery paths, separate provider-answer lanes, and a provisional independent restore passed. The exact replacement artifact, provider plus restore on that same artifact, headed helper/Keychain/Gatekeeper path, and wider physical/native matrices remain open. |
| `INST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PARTIAL 2026-07-22; complete local parent-candidate inventory and public-safety review passed, and `python3 -m pytest tests/release/ -q` passed with 1,542 tests and 11 skips. Staged and remote parent-PR exactness remain open. |
| `INST-003` | Custom Settings Install and upgrades of that runtime include the nightly workflow without owner-specific setup; immutable Easy Install states that the service is not packaged. | An Easy user reaches chat without worker tooling or a false installed claim, while a Custom Settings user's explicit active/disabled posture survives upgrade. | installer/CLI, preflight, config compiler, generated env, install summary, Workbench seed | `test_default_nightly_routines.py`, `test_wizard.py`, `test_preflight.py`, `test_config_compiler.py`, `test_cli_upgrade.py`, `test_install_summary.py`, `test_prompt_workbench.py` | PARTIAL 2026-07-21; the Easy registry classifies omitted nightly services as Custom Settings-only and automated Custom Settings upgrade contracts preserve explicit disables, while final exact-artifact wording and an established-user live upgrade remain unproved |
| `INST-004` | Easy Install Brain Readiness aligns the installer with the shipped core inventory without pretending omitted or user-owned integrations are ready. | A new or upgrading user gets the core brain spine plus guided OpenAI setup, honest Custom Settings boundaries/status rows, and no developer-private defaults. | wizard, preflight, config compiler, install/status summary, generated env, QA map, public examples | `test_brain_readiness.py`, `test_wizard.py`, `test_install_summary.py`, `test_config_compiler.py`, `test_preflight.py`, feature-owner suites as applicable | PARTIAL 2026-07-21; public copy uses Easy Install/Custom Settings Install, only the core app is classified installed, saved provider credentials are not reported Ready, and four raw-provider lifecycles pass in scoped browser lanes. One clean exact-artifact optimized OpenAI journey and the shared tested-at readiness model remain open. |
| `INST-005` | A backup is called successful only when the complete promised payload is independently restorable. | Existing users can recover chats, saved memory, Recall/RAG, schedules, auth status, channels, config, and runtime selection after failure. | CLI/helper snapshot, manifest, databases, state, restore, browser | Snapshot/restore contract tests plus disposable full-payload restore QA | PARTIAL 2026-07-21; current-format public capture and synthetic independent-target transactional apply pass, and a pristine no-tools VM restored a provisional-payload backup to an independent target, recovered the synthetic browser user, and preserved Connected Accounts/Feelings across refresh and restart. Legacy candidates remain `recoverable: false`; exact rebuilt-artifact restore, helper interaction, provider/channel reconnect, Recall rebuild, and the remaining promised domains remain open. |
| `INST-006` | Custom Settings configure/reconfigure is transactional and preserves existing user-managed state; immutable Easy Install fails closed instead of mutating its payload. | A user can change one Custom Settings value without silently replacing unrelated configuration or losing a reliable setup. | CLI/helper/wizard, candidate config, compiler, semantic diff, reload, rollback | Candidate/merge/atomic-swap tests plus disposable existing-user QA | PARTIAL 2026-07-21; Custom Settings reconfigure backup/reapply and missing-secret rollback pass while Native immutable configure fails closed; interactive helper preview, crash journal, and wider reload proof remain |
| `INST-007` | Bootstrap validates its destination and installs a verified immutable release. | One command never mutates an unrelated repository and every installed component matches the selected release. | bootstrap, target directory, release manifest, signatures/digests, component pins, installed artifacts | Bootstrap identity/signature/interruption tests plus fresh public-entrypoint QA | PARTIAL 2026-07-19; destination identity, relocatable assembly/install, deterministic compressed build, verification/stage/activation/recovery, bundled-Python bootstrap source, and fail-closed unprovisioned Native hand-off pass locally; the exact dual-architecture workflow, approved license/trust, Developer ID/notary execution, and fresh exact-artifact QA remain blocked |
| `INST-008` | The exact public artifact completes the decisive Easy Install journey on a clean supported Mac. | A novice reaches an optimized OpenAI-backed answer, Feelings, and restart persistence with minimal truthful choices; omitted integrations point to Custom Settings Install. | terminal installer, helper, browser onboarding/chat, Feelings, restart | Cross-surface clean-Mac E2E ledger; automation supports but does not replace it | PARTIAL 2026-07-21; disposable source-candidate installation/recovery, raw provider-card persistence, account-menu Feelings, and provisional independent restore pass in scoped lanes. Ordinary-chat right-control Feelings, exact signed artifact, optimized OpenAI answer, and one uninterrupted end-to-end novice run remain open. |
| `INST-009` | Setup/status distinguishes configured values from live-tested readiness. | Users know exactly what works, what is pending, why it failed, and how to repair it. | install summary, Brain Setup, status, helper, provider/channel self-tests | Shared-state contract tests plus live failure matrix | PARTIAL 2026-07-21; configuration-only Brain Setup surfaces say `Configured`, while scoped OpenAI, Anthropic, Groq, and Grok browser lanes distinguish invalid key, quota, outage, and network failures with repair. One shared cross-surface state/timestamp model and remaining provider/channel matrices remain open. |
| `INST-010` | Provider and channel onboarding is truthful, secure, recoverable, and capability-scoped. | Users can connect, test, reauth, repair, disconnect, revoke, and delete local secrets without exposing credentials. | connected accounts, Keychain, Telegram, Google, Microsoft, future Slack/WhatsApp, diagnostics | Adapter-state tests plus real synthetic account/channel QA | PARTIAL 2026-07-21; stable browser-entered OpenAI, Anthropic, Groq, and Grok API-key lifecycles pass in headed Chromium, including repair, local Disconnect, zero post-disconnect provider contact, and re-add. Custom Settings compiler/Keychain simulation now covers all four provider env mappings and missing-reference rollback; the new browser-residue guard passes offline but still needs a headed rerun. Native Keychain/TCC, provider-side lifecycle, Telegram, Google/Microsoft, Slack, and WhatsApp remain open. |
| `INST-011` | Supported platform, prerequisite, resource, interruption, and recovery matrices are run in isolated environments. | Installer failures are bounded, specific, resumable, and never drift host state. | disposable macOS, optional isolated Linux/container harness, install journal, restart/rollback | Matrix automation plus real clean Apple Silicon and Intel when supported | PARTIAL 2026-07-20; the no-share Tart lane and a separate no-host-mount Apple-silicon Docker VM lane cover core install, restart, daemon loss/recovery, failed-start cleanup, and preserve-data uninstall. Vanilla base, low-resource/network/interruption breadth, signed helper/Keychain/TCC, Intel, Docker Desktop GUI, and physical sleep/wake remain open. |
| `INST-012` | Flagship features are discoverable from ordinary product navigation and guide missing setup. | A normal chat user can open Feelings without knowing a URL or inferring where provider setup lives. | LibreChat side panel, account menu, Feelings, auth/setup states, narrow/a11y layouts | Real Playwright/browser navigation, provider-state, refresh, persistence, and config/log checks | PARTIAL 2026-07-21; authenticated account-menu keyboard discovery, nine visible Feelings bands, refresh/restart persistence, missing-provider independence, narrow/reduced-motion behavior, Node 24 build, and DB state pass. The ordinary chat right-control link exists in source but has not been exercised on the real browser surface; disabled/degraded setup, native assistive technology, and final installed-artifact alignment remain open. |
| `INST-013` | Local-only mode explicitly binds every user-facing service to loopback unless a declared remote-access mode owns exposure. | A new install is not accidentally reachable from the LAN because a framework default changed. | launcher, playground, LibreChat, helper/status, socket table, firewall/network matrix | Bind-host contract tests plus clean-Mac loopback/LAN probes | PARTIAL 2026-07-20; immutable Native source now removes both backend API `3180` and MongoDB `27117` TCP listeners, using exact support-owned Unix sockets while the public web proxy remains loopback-only. An isolated exact MongoDB 8.0.23 launch proved one mode-`0600` socket and zero TCP listeners. The replacement exact payload, second-host/firewall/remote-mode, and every optional-service matrix remain open |
| `INST-014` | Easy Install Native and the planned Easy Install Docker profile share the safe onboarding/readiness/rollback contract, while Docker prerequisites never block Native first chat. | A novice installs Easy Native without Docker or developer tools, connects OpenAI, receives a persistent answer, and can deliberately choose the separate Easy Docker profile when that artifact is shipped. | schema/wizard, preflight/compiler, native services, manifest/bootstrap, browser setup/chat, status, restart/restore | Profile contract tests, exact-payload tests, and disposable Tart browser/install matrix | PARTIAL 2026-07-22; the source-candidate Docker delta and raw provider-card answers pass, a provisional-payload backup restored into an independent target, and all 11 clean nested changes are merged and exactly repinned with reviewed-tree equality. The current immutable payload is Native-only; signed Native payload, optimized OpenAI answer, shipped Easy Docker artifact, full fault matrix, and physical Docker Desktop remain open. |
| `INST-015` | The public bootstrap installs an immutable, signed, notarized Native payload rather than compiling a mutable source checkout. | A clean Mac installs without Git, Homebrew, Xcode/CLT, npm, pnpm, uv, Python, or system Node. | bootstrap, release manifest, app/helper/runtime bundles, Gatekeeper | Signature/notarization/tamper tests plus exact-artifact clean-Mac install | BLOCKED 2026-07-19; exact producer/bootstrap/runtime and payload/bootstrap signing workflow source pass local contracts, including PID/helper/secrets hardening and a target-like local install/health smoke. MongoDB redistribution approval, public trust/authorities, actual dual-arch build/sign/notary/staple execution, and clean-Mac installed-artifact QA do not exist yet |
| `INST-016` | The exact payload works on a truly vanilla supported Mac with the published CPU/macOS/RAM/disk matrix. | A novice is not surprised by hidden developer dependencies or unsupported hardware. | macOS first run, helper, Keychain, runtime, resource monitor | Pristine VM/physical-Mac matrix | FAIL 2026-07-20; a provisional exact local-QA payload installed in a disposable vanilla guest and exposed four independent Native defects: missing pruned `mongodb`, missing local password recovery, a broken first-admin browser handoff, and a hidden Connected Accounts surface. The dependency, bundled `password-reset-link`, cookie-bound first-admin proxy, and secret-free account-capability source regressions now pass their focused checks. The replacement exact payload and full pristine lifecycle must still be rebuilt and rerun. |
| `INST-017` | The supported Easy Install OpenAI path completes the full lifecycle and proves a useful persistent optimized Viventium answer; other provider cards make no broader parity claim. | Add, validate, replace, disconnect, and delete a browser-entered encrypted API key; recover from invalid key, quota, outage, and network failure; preserve first/second chat across refresh/restart. The experimental subscription bridge is tested separately and never presented as official. | Connected Accounts, encrypted user key, optimized agent/chat, persistence, status; supplemental raw-provider cards and experimental bridge | Stable API-key browser lifecycle plus `openai-connected-account-lifecycle-qa.cjs` as experimental compatibility coverage | PARTIAL 2026-07-21: headed Chromium on the integrated disposable arm64 runtime proved credential transport, raw selected-model answers, refresh/restart persistence, failure guidance, local Disconnect, zero provider contact while disconnected, and key re-add for OpenAI, Anthropic, Groq, and Grok. That does not prove optimized Viventium brain parity across four providers. The exact signed installed OpenAI-first optimized answer and current tested-at readiness state remain NOT RUN. |
| `INST-018` | A complete synthetic installation can be backed up and independently restored across every promised continuity domain. | Existing users can prove recovery before relying on a snapshot. | chat/memory/RAG/schedules/auth/channels/config/runtime selection, helper/CLI/browser | Full-payload capture/restore ledger | PARTIAL 2026-07-21; a pristine no-tools VM created a complete provisional-payload backup, restored it to an independent target, recovered the synthetic browser account, and retained Connected Accounts/Feelings visibility across refresh and full runtime restart with zero external attempts. Exact rebuilt artifact, helper interaction, provider/channel reconnect, and Recall rebuild remain open. |
| `INST-019` | Interrupted, constrained, concurrent, rollback, upgrade, downgrade, and uninstall paths preserve a recoverable state. | Failures are bounded and retryable without corrupting the previous install. | journal, disk/network/process faults, ports, reboot, rollback, uninstall | Fault-injection matrix on disposable targets | PARTIAL 2026-07-21; the current synthetic contract matrix covers atomic activation and health rollback, interrupted stage/upgrade/config/continuity recovery, low-disk refusal, exact process/LaunchAgent ownership, daemon failure, and operation-lock concurrency. Physical power loss/reboot, sleep/wake, broader network and low-resource faults, MDM/no-admin, downgrade/delete breadth, headed Docker Desktop, and the exact signed artifact remain open. |
| `INST-020` | The signed helper, Finder-launched bootstrap, SMAppService, Keychain, Gatekeeper, login startup, and user-visible repair actions work together. | macOS security prompts and bootstrap progress/failure/recovery states are minimal, truthful, accessible, and recoverable. | bootstrap/helper GUI, LaunchAgent, Keychain, Gatekeeper/notarization | Source/compiled contracts plus physical/headed macOS acceptance | PARTIAL 2026-07-21; the Finder bootstrap now posts bounded dynamic status announcements, both native packages compile, cancellation drains an owned synthetic descendant process group and preserves the activation boundary in source-level QA, and the helper menu exposes named app/status semantics. The rebuilt helper is universal and hash-aligned, but remains ad-hoc/linker signed. Developer ID/notarization, real visible Cancel/Retry/success, VoiceOver, permission prompts, login startup, and Keychain lifecycle remain open. |
| `INST-021` | The planned Easy Install Docker profile changes only declared capability adapters and preserves the safe Native onboarding/readiness/rollback contract. | A user can deliberately choose the Docker profile without receiving a different or more brittle core product. | physical Mac, Docker Desktop, capability services, browser/status | Native-versus-Docker delta matrix | PARTIAL 2026-07-20; an isolated no-host-mount Apple-silicon Docker VM passed core source-candidate install/start, browser Connected Accounts and Feelings discovery, supported stop/start, local password recovery/fresh login, daemon loss/recovery, named-volume user continuity, loopback binds, and preserve-data uninstall. A shipped Easy Docker artifact, Docker Desktop GUI/TCC/Keychain, physical sleep/wake/resource behavior, optional Recall/RAG, exact component bootstrap, and parity remain open. |
| `INST-022` | Every nested component commit, parent pin, compiled artifact, and installed artifact under test is identical. | A clean install receives the behavior that QA approved. | nested repos, `components.lock.json`, built client, public payload, installed runtime | Commit/pin/hash and runtime artifact alignment checks | PARTIAL 2026-07-22; all 11 clean nested changes are merged, every fetched `origin/main` and parent ref equals its captured hosted merge commit, and every merged tree equals its audited review head. Rebuilt payload, shipped, and installed identity remain open. |
| `INST-023` | Onboarding and recovery remain usable with keyboard, screen reader, narrow/mobile layout, localization, reduced motion, and high contrast. | Nontechnical users are not excluded by presentation or input mode. | installer/helper/browser dialogs and controls | Accessibility/localization browser and native UI matrix | PARTIAL 2026-07-21; the existing LibreChat matrix passes, and a fresh modern-playground Chromium run now proves named keyboard stops, 320 px reflow, forced colors, zero retained motion durations under Reduce Motion, and non-clipped tall content after two fixes. Complete translations, native VoiceOver/helper/Keychain/TCC interaction, Intel, and exact shipped-artifact proof remain open. |
| `INST-024` | Preflight, doctor, build, launchers, helper, packaged runtime, and diagnostics select one supported Node major. | A first install or upgrade does not download two runtimes, build under one runtime, launch under another, or resurrect an obsolete runtime through an optional feature. | preflight/common/doctor, LibreChat and optional launchers, macOS helper, dependency install, client build, packaged runtime | Cross-layer version contract plus clean-install process/path provenance and exact-artifact build/start QA | PARTIAL 2026-07-19; six source surfaces align on Node 24, the full parent suite and helper rebuild pass, and the VM built/started/restarted under Node 24; exact-payload process-path provenance remains unrun |
| `INST-025` | Source helper install/uninstall mutates only an owned Viventium bundle through a same-filesystem rollback transaction. | A personal app or external symlink target is never deleted because its filename resembles Viventium. | `install_macos_helper.sh`, `~/Applications`, current and legacy helper bundles | Ownership/symlink/sentinel/rollback tests plus headed installed-helper QA | PARTIAL 2026-07-20; synthetic symlink, unrelated-app install/uninstall, owned rollback, exact legacy migration, universal prebuilt source/binary digest, and clean synthetic prebuilt-install regressions pass; installed headed behavior and publisher signing/notarization remain unrun |
| `INST-026` | Native compliance inventories the exact physical pruned payload and the entire compiled-client module closure, and fails closed on unreviewed license expressions or absent notice bytes. | A published payload has path-accurate SBOM/notices instead of treating export subpaths as packages, trusting a declaration without its notice, or omitting browser-only/vendored runtime licenses. | exact Native payload, physical npm graph, Rollup closure, minimal Python, MongoDB, SPDX/notice/scan bundle | Exact-layout fixtures, compiled-closure/tamper/hash checks, and generator/verifier on the assembled payload | BLOCKED 2026-07-20; the earlier rejected payload proved that a physical production-node inventory alone omits browser code already compiled into `client/dist`. Minimal component staging and hash-bound Python manifests now pass focused tests, while the full rendered-client notice closure and replacement exact-payload generator/verifier run are still in progress. No legal approval or missing notice content is inferred. |
| `INST-027` | Native runtime defaults are compiler-owned, secret-free, relocatable, and registration/default-agent closure is synchronous. | A clean user creates the only first admin, direct registration closes before success returns, the default agent exists after restart, and no build-host credential reaches a child service. | Native compiler/defaults, assembler, supervisor/private API socket, MongoDB, browser proxy 3190 | Strict env/assembly tests plus exact-candidate first-admin, zero-3180-listener, login, DB/default-agent, restart, process-env, and log evidence | FAIL 2026-07-20 for the provisional exact payload. After the pruned dependency defect was corrected, headed QA found that the one-time page could not post under its CSP and omitted `confirm_password`; ordinary `/register` also led to an unexplained rejection. The proxy now uses an HttpOnly SameSite cookie and clean URL, permits only same-origin setup POSTs, supplies matching confirmation, intercepts `/register`, exposes progress/retry errors, and retains fail-closed replay/close behavior. The backend now uses an owner-checked private Unix socket so a foreign process on historical port `3180` receives zero traffic. Focused supervisor/proxy/socket tests pass; replacement exact-payload registration, DB/default-agent, restart, helper/browser QA remain pending. |
| `INST-028` | The exact Native candidate contains no producer-local paths, runtime logs/audits, Python bytecode/cache, private identity, or credential material. | A public download cannot reveal the build machine or accidentally ship mutable runtime evidence. | compiled defaults, assembled payload/bootstrap, candidate/release workflows, binary/text artifact scan | Prompt-path, exclusion, exact-prefix, private-path, secret-pattern, and workflow-gate regressions plus exact-candidate scan | PARTIAL 2026-07-22; the complete reconstructed parent source candidate and all clean audited nested deltas passed public-safety review before merge. The earlier provisional payload's dependency failure remains historical; a replacement exact immutable payload still must be rebuilt, rescanned byte-for-byte, signed/notarized, and rerun in a pristine guest. |
| `INST-030` | Browser artifact code runs from a separately owned, loopback-only, upgrade-safe origin in Native, source, dev, and Docker profiles. | Artifacts work without sharing the authenticated app origin, colliding with local prod, going stale across upgrade, or producing false-ready installer/helper status. | LibreChat API listener, Native proxy, source launcher, Docker image, compiler/dev offsets, installer/status/helper | `test_sandpack_runtime_contract.py`, Native assembler/proxy tests, LibreChat listener/adapter tests, real two-origin browser and upgrade QA | PARTIAL 2026-07-22; exact reviewed source heads, the complete post-merge 1,542-test parent suite, the recorded post-merge 128-test workflow/manifest/payload/public-safety slice, historical pre-merge 311-test slice, focused browser contracts, and the exact modern-playground headed accessibility/loopback run pass. Corrected LibreChat reviewed head `44ac1f7a...` is locally and hosted green; its exact tree is merged and pinned at `38527a8651...`. The exact replacement payload, headed upgrade persistence, and exact Docker-image browser proof remain required. |
| `INST-031` | First-run Connected Accounts is truthful, dismissible, and network-quiet before the user connects a provider. | A novice can inspect or close provider setup without contradictory credential promises, keyboard traps, hidden retries, unsolicited cloud requests, or noisy missing-credential errors. | first-admin handoff, Connected Accounts dialog, provider model discovery, Native logs | LibreChat dialog/keyboard/provider-config regressions plus exact-payload headed browser and network/log trace | PARTIAL 2026-07-22; the provisional payload failure remains historical, and the structural fixes now pass focused source and all 15 hosted LibreChat checks. Corrected LibreChat reviewed head `44ac1f7a...` is locally and hosted green; its exact tree is merged and pinned at `38527a8651...`. The exact replacement payload, headed first-run/network trace, and installed-artifact proof remain open. |
| `INST-032` | Disposable release QA is single-VM, receipt-owned, storage-budgeted, and fail-closed. | Clean-machine proof cannot silently fill an owner's disk or delete unrelated Tart/Docker state. | QA host lease/receipt, Tart clone/delete, Docker baseline, sparse-disk and host free-space monitor | `tests/release/test_qa_storage_guard.py` with fake tools only; one guarded disposable-Mac acceptance run after the release candidate is frozen | PARTIAL 2026-07-21; twenty-one fake-tool regressions pass and qualify the storage-guard contract, but the guarded real-VM run remains open and must create and delete exactly one VM. |

These are umbrella installer cases. Feature owners retain detailed authority: `INST-005` links to
`qa/continuity-ops/`; `INST-007` incorporates rather than replaces `PIPE-001` under
`qa/installer-piped-bootstrap/`; `INST-010` links to Telegram and MCP/OAuth owners; `INST-008` is the
decisive cross-surface journey and does not replace the platform matrix in `INST-011`. `INST-014`
owns shared-profile parity and consumes rather than duplicates `INST-003`, `INST-007`–`INST-011`,
and `INST-013`.

## `INST-031` - Quiet, Truthful First-Run Provider Setup

- Requirement: opening Connected Accounts on a clean Easy Install must not contact a model provider
  until the user has intentionally supplied or authorized a credential. Dialog copy, expiry state,
  keyboard behavior, persisted state, network traffic, and logs must all agree.
- Escaped defect: the provisional pristine Native payload displayed a red promise that an API key
  would never expire while the active selector said it expired in 12 hours. Escape did not dismiss
  the populated modal. Before any key existed, model discovery sent three OpenAI requests and the
  Native log recorded a missing implicit auth file plus a fail-open undefined capability path.
- Preconditions: a pristine exact payload; a fresh synthetic local admin; no provider credentials,
  provider files, browser state, or developer tools; outbound requests observed and blocked.
- User actions:
  1. Complete first admin and follow the automatic Connected Accounts handoff.
  2. Open each supported credential dialog, inspect expiry/disclosure copy, change the expiry choice,
     then close using Escape, Cancel, and the close control.
  3. Refresh, restart the runtime, and repeat without saving a credential.
  4. Inspect browser requests and sanitized runtime logs before, during, and after those actions.
- Expected result: every displayed expiry statement matches the selected persisted expiry; Escape,
  Cancel, and close restore focus and leave the provider missing; the zero-credential path performs
  zero provider requests and emits no missing-optional-auth or undefined-capability error.
- Forbidden result: contradictory permanence/expiry copy, a keyboard trap, hidden credential save,
  unsolicited provider model discovery, retry storms, stack traces, secret-bearing diagnostics, or
  source/unit evidence presented as the exact-payload browser result.
- Evidence to capture: visible modal and restored focus, selected/persisted expiry state, external
  request count and destinations, sanitized log classification, refresh/restart result, source and
  exact installed artifact identities.
- Last run: **FAIL 2026-07-20** on the provisional arm64 local-QA payload. The source-level expiry,
  keyboard-dismissal, provider-discovery, and capability-path regressions now pass, but they do not
  change the escaped payload result. A rebuilt exact candidate and repeat headed run are required
  before this case can pass.

## `INST-032` - Storage-Bounded Disposable QA

- Requirement: release QA must acquire one persistent exclusive lease before it creates a machine,
  fail if any Viventium QA VM already exists, and delete only the exact VM named in its receipt.
  Host free space, physical/logical Docker sparse-disk growth, and pre-existing Docker resource IDs
  remain monitored until cleanup completes.
- Escaped defect: parallel disposable-machine work retained 17 QA clones while Docker's sparse disk
  grew independently. Apparent APFS clone size and physical host use were not separated, and policy
  prose did not provide an executable stop gate.
- Preconditions: a frozen candidate; public-safe evidence outside the repo; the tracked storage
  policy; an empty QA-VM inventory; the Docker context and sparse-disk identity inventoried read-only.
- User actions:
  1. Run `prepare` with one safe run ID, exact matching VM name, candidate, private state root, and
     explicit Tart/Docker executables and sparse-disk path.
  2. Run `clone`; verify Tart receives `TART_NO_AUTO_PRUNE=1` and only the receipt VM is created.
  3. Run QA through `run -- <argv>`; observe the command as an argument vector, never a shell string.
  4. Inject low free space, host/Docker growth, an unowned QA VM, a missing pre-existing Docker
     resource, child failure, and guard interruption.
  5. Run `cleanup` with an exact repeated run-ID confirmation and inspect the retained receipt.
- Expected result: one VM maximum; every limit stops only the guarded process group and leaves an
  explicit `CLEANUP_REQUIRED` lease; cleanup targets only the receipt-owned VM; pre-existing Docker
  containers, images, volumes, context, and sparse-disk identity survive; no post-baseline Docker
  object remains; the owned process group is proven empty even when its leader exits before a
  grandchild; successful cleanup leaves no QA VM and releases the lease.
- Forbidden result: stale-lease adoption, auto-prune, global Docker/Tart cleanup, wildcard deletion,
  shell evaluation, deleting a VM by prefix, deleting a pre-existing Docker resource, silently
  resetting the persistent clean baseline, or calling fake-tool/unit evidence a real VM pass.
- Evidence to capture: policy digest, receipt phases, exact VM name, before/peak/after host free
  bytes, Docker logical and physical bytes, baseline-survival result, command exit/timing, and empty
  post-cleanup QA-VM inventory. Raw host IDs stay only in private evidence.
- Last run: **PARTIAL 2026-07-21**. Twenty-one automated release regressions passed using fake Tart/Docker
  executables only, including crash/failure residue and deletion refusals. No real VM or Docker
  resource was created, changed, or removed; the real frozen-candidate path remains blocked until an
  exact candidate and isolated machine are available.

## Discrete Easy Install Release Gates

These cases are intentionally separate so one broad `PARTIAL` cannot hide a missing release proof.

| Gate | Expected result | Forbidden result | Evidence required | Current status |
| --- | --- | --- | --- | --- |
| `INST-015` signed payload | The one command verifies and activates a notarized immutable payload. | Mutable branch checkout, source build, or package registry resolution is presented as Easy Install. | Signature/notarization/tamper ledger and exact payload digest. | BLOCKED |
| `INST-016` vanilla Mac | No undeclared developer tools are used before first answer. | Dormant or host-installed tools silently make the run pass. | Pristine-image inventory, installer trace, and process/file provenance. | FAIL; provisional exact payload reached startup but omitted a required production module. Replacement run pending. |
| `INST-017` provider lifecycle | One synthetic browser-entered API key produces an answer that survives refresh/restart; every failure state has a repair action. | Saving a key or starting experimental OAuth alone is called usable chat. | Browser video/screens, sanitized provider state, answer persistence, API/log confirmation; experimental bridge evidence remains supplemental. | PARTIAL 2026-07-20; the scoped synthetic raw-provider browser lifecycle passed, while the exact signed optimized Viventium answer and experimental bridge browser path remain unrun. |
| `INST-018` restore | Every promised continuity domain is restored into an independent target. | Metadata, source inspection, or DB copy alone is called recoverable. | Before/after browser ledger, manifest hashes/counts, auth re-login truth. | PARTIAL |
| `INST-019` fault matrix | Every interruption retains either the previous healthy version or a resumable journal. | Partial install overwrites the last healthy state. | Stage-by-stage fault ledger and rollback state. | PARTIAL |
| `INST-020` macOS integration | Bootstrap/helper/login/Keychain/Gatekeeper behavior passes on a headed supported Mac. | Source build or universal architecture alone substitutes for user interaction. | Visible native UI, system registration, Keychain and process evidence. | PARTIAL; Finder AppKit source/compiled contracts pass, but the local synthetic headed session was blocked by the locked desktop. |
| `INST-021` Docker delta | Docker adds only selected adapters; core onboarding remains equivalent. | Docker masks a Native defect or becomes an undeclared prerequisite. | Side-by-side physical-Mac comparison. | BLOCKED |
| `INST-022` delivery alignment | Nested commit, pin, build, payload and installed runtime hashes agree. | A dirty source candidate is treated as the public artifact. | Commit/hash ledger at all five surfaces. | PARTIAL; all 11 nested changes are merged, every parent ref equals fetched `origin/main`, and every merged tree equals its audited review head. Replacement build/payload/shipped/installed identity remains open. |
| `INST-023` inclusive UX | All critical steps remain perceivable and operable across the declared matrix. | Pointer-only, English-only, or desktop-width success is generalized. | Accessibility tree, keyboard, viewport and localization ledger. | PARTIAL |
| `INST-024` Node runtime alignment | Every install/build/start/status layer uses the same supported Node major carried by the exact payload. | Preflight passes under one major while startup installs or forces another. | Version-contract test, clean-install PATH/process provenance, production build and restart on the exact artifact. | PARTIAL |
| `INST-032` storage-bounded QA | One receipt-owned VM stays within host/Docker budgets and is deleted immediately after evidence capture. | Parallel clones, automatic pruning, global cleanup, or an abandoned lease is accepted. | Guard receipt, before/peak/after metrics, exact Tart events, Docker baseline survival, and empty QA-VM inventory. | PARTIAL; automated fake-tool guard contracts pass, while the guarded real candidate run remains unrun. |

### `INST-020` / `INST-023` Finder-launched Easy Install bootstrap procedure

- Requirement: double-clicking `ViventiumBootstrap.app` with no arguments presents a native Easy
  Install window; any invocation with arguments stays headless for release automation.
- Preconditions: exact candidate app bundle, supported headed macOS user session, synthetic local
  installer outcome, no personal accounts or secrets, and a separate disposable/private evidence
  directory.
- Steps:
  1. Open the app from Finder and record the initial window, accessibility tree, focus, and process.
  2. Verify title, textual stage, indeterminate progress, bounded detail, and Cancel; repeat with
     Reduce Motion enabled and confirm progress becomes static without losing the textual status.
  3. Request Cancel using Escape and the button at pre-download, staging, pre-activation, activation,
     and health-wait checkpoints. Confirm the UI says it is finishing a safe checkpoint and the
     installer retains the prior healthy release or a resumable journal.
  4. Exercise nonzero failure, Retry, success, Open Viventium, Quit, window close, and Command-Q.
     Confirm raw stdout/stderr, commands, paths, secrets, and token URLs never appear.
  5. Run the exact compiled executable with `--self-check` plus synthetic arguments and assert exact
     argument order, stdout, stderr, and exit status forwarding through the signed bundled Python.
  6. Repeat the visible flow under VoiceOver and keyboard-only control on the exact Developer ID
     signed/notarized candidate; correlate each visible result with installer journal/health evidence.
- Expected result: a novice always sees what is happening and what to do next; cancellation starts
  cooperatively, escalates only after bounded grace periods, drains owned child processes, and stays
  truthful about journal recovery; Retry is safe; success opens only the fixed local Viventium
  origin; CLI release workflows remain observable through their exact streams and status.
- Forbidden result: a Finder launch fails only in invisible stderr, a hung spinner exposes no stage,
  Cancel leaves descendants running or claims rollback without exit/journal evidence, success is
  shown after a failed health gate, an error renders raw child output or a local path, or adding the
  window changes `--self-check` behavior.
- Automation: `tests/release/test_native_bootstrap_ui.py` plus the signed-bundled-Python and candidate
  workflow contracts in `tests/release/test_native_payload_assembler.py`.
- Last run: PARTIAL 2026-07-22. The Native bootstrap cancellation regression now also covers the
  macOS/Python 3.14 `EPERM` liveness race after a process-group leader exits: the installer treats
  the still-existing group as alive and continues bounded cleanup rather than abandoning its owned
  descendant. The 48-test Native payload suite proves phase-aware cancellation,
  pre-publish staging cleanup, and durable-health recovery; the 7-test bootstrap suite compiles the
  AppKit package and proves an owned synthetic descendant receives termination. Source contracts,
  exact headless forwarding, bounded status-announcement semantics, a universal hash-aligned helper,
  and the scoped modern browser accessibility lane also pass. The helper is still ad-hoc/linker
  signed. No safely isolated headed native session was available, so visible AppKit layout, real
  Cancel/Retry/success, VoiceOver, Keychain/TCC/Gatekeeper, login startup, and exact Developer ID
  artifact interaction remain `BLOCKED`, not inferred from automation.

### `INST-017` supported Easy Install API-key lifecycle procedure

- Preconditions: a disposable runtime built from the integrated LibreChat candidate; one synthetic
  `.invalid` local user; the selected OpenAI, Anthropic, Groq, or Grok endpoint configured to a loopback-compatible stub; no
  real provider account or credential; experimental direct subscription auth disabled.
- User actions: open Connected Accounts, enter a synthetic API key, run a live test/send two useful
  prompts, refresh, restart, replace with an invalid key, recover, exercise quota/outage/network
  failures, Disconnect locally, try chat while disconnected, and add the valid synthetic key again.
  After every credential mutation plus refresh/restart, inspect cookies, local/session storage,
  Cache Storage, and IndexedDB without publishing the synthetic value or a raw storage dump.
- Expected result: a saved key is only Configured until a live request succeeds; useful answers
  render and persist; each failure names one repair action; Disconnect deletes only Viventium's
  encrypted user key, reports Disconnected, and prevents another provider request; re-adding the
  key restores useful chat.
- Forbidden result: direct OAuth offered by default; configuration called Ready without a live
  request; provider contact after Disconnect; answer loss after refresh/restart; secret values in
  logs, browser storage, screenshots, reports, or diagnostics; API-only evidence presented as
  browser acceptance.
- Automation: `qa/installer-resilience/scripts/openai-api-key-lifecycle-qa.cjs`, owned by
  `tests/release/test_openai_api_key_lifecycle_qa.py`, plus supporting release contracts.
- Current result: **PARTIAL** on 2026-07-20. The scoped raw-provider lifecycle passed in headed
  Chromium against the integrated disposable arm64 runtime for OpenAI, Anthropic, Groq, and Grok,
  with zero external browser network attempts; see the dated reports. This result does not prove the
  optimized Viventium first-answer path and does not substitute for signed-payload,
  pristine-install, restore, accessibility, Docker, Intel, or delivery-alignment gates. The
  browser-residue guard and its fail-closed offline regression pass on 2026-07-21, but that added
  inspection has not yet been rerun in the headed lifecycle and is not retroactively claimed by the
  2026-07-20 evidence.

### `INST-017` experimental compatibility-bridge lifecycle procedure

- Preconditions: a disposable runtime built from the integrated LibreChat candidate; one synthetic
  `.invalid` local user; OAuth token and Codex Responses URLs configured to the loopback stub
  described in `qa/installer-resilience/README.md`; no real provider account.
- User actions: deny authorization, retry and close the popup, retry and grant in the visible
  synthetic provider page, send two useful prompts, refresh, restart, force expiry and early 401,
  force failed refresh, follow reconnect guidance, Disconnect locally, try chat while disconnected,
  and regrant.
- Expected result: every successful grant is visibly Connected; answers render and persist; each
  refresh happens exactly once; failed refresh gives one actionable repair path; Disconnect deletes
  Viventium's stored credential, reports Disconnected, refuses chat without contacting the provider,
  and explains provider account controls for upstream invalidation; regrant restores useful chat.
- Forbidden result: any non-loopback browser/provider request, OAuth start reported as connection,
  a local delete labeled as provider revocation, silent refresh/disconnect failure, provider contact
  after local Disconnect, answer loss after refresh/restart, secrets or OAuth state in public output,
  or mocked/API-only evidence presented as browser acceptance.
- Automation: `node qa/installer-resilience/scripts/openai-connected-account-lifecycle-qa.cjs`.
- Boundary: this is supplemental compatibility evidence, not the Easy Install default and not an
  official OpenAI integration. It requires `VIVENTIUM_EXPERIMENTAL_DIRECT_SUBSCRIPTION_AUTH=true`.
- Provider-side revocation is unsupported; Disconnect removes only Viventium's local credential,
  and provider account controls remain the truthful upstream invalidation path.
- Current result: **PARTIAL.** The browser lifecycle was not run on 2026-07-20. The local provider self-test
  and release contracts pass. The integrated candidate is not ready, so the disposable VM remains
  stopped and no real-browser result is claimed.

## `INST-001` - Core User Flow

- Requirement: Install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_config_compiler.py` plus any narrower feature tests discovered during implementation.
- Last run: PARTIAL 2026-07-21. A no-share disposable VM ran the Easy Install source candidate
  through install, rerun, stop/restart, authenticated registration and account handoff, OAuth popup
  cancel/retry, disconnected-provider guidance, Feelings discovery and persistence, missing-secret
  Custom Settings Install rollback, failed-upgrade service recovery, idempotent reinstall,
  preserve-data uninstall, and manual recovery of the tested synthetic state. Separate scoped lanes
  completed persistent answers for all four API-key providers and a provisional independent restore.
  The tested core installed in 32.15 seconds and reran in 18.66 seconds. No personal state was used.
  One exact signed-artifact journey combining install, provider answer, restore, headed helper/
  Keychain/Gatekeeper, and the wider fault matrix remains open.

## `INST-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: PARTIAL 2026-07-22. The dated lifecycle reports use synthetic values and public-safe
  placeholders. Complete local parent-candidate inventory and public-safety review passed, and the
  reconstructed source passed post-merge `python3 -m pytest tests/release/ -q` with 1,542 passed,
  11 skipped, and 0 failed in 293.15 seconds. Staged and remote parent-PR exactness remain open.

## `INST-003` - Profile-Aware Nightly Workflow Install And Upgrade

- Requirement: all supported paths carry the nightly-workflow capability without hardcoding a
  developer account or relying on owner-machine leftovers. New Easy Install Native installs defer its
  activation until post-ready worker setup; Custom Settings Install choices and existing explicit upgrade
  state are preserved.
- Risk covered: new users install Viventium successfully but do not get the intended nightly
  reflection/memory workflow, or the workflow only works on the original developer laptop.
- Preconditions: synthetic config/temp state can be used; at least one positive worker-auth case
  and one missing-auth case must be exercised without writing private account details to public QA.
- Steps:
  1. Build a new Easy Install Native config and confirm GlassHive worker execution, Prompt Workbench
     schedule activation, and memory hardening are setup-pending and do not block core preflight.
  2. Activate worker setup and prove the same canonical capability becomes runnable without
     reinstalling the core.
  3. Run the reconciler over legacy, explicitly active, and explicitly disabled upgrade-shaped
     configs and confirm each posture is preserved while `operator_user_email` remains empty.
  4. Simulate Codex-ready and Claude-ready machines and confirm an empty generated worker profile is
     filled from the signed-in CLI instead of a hardcoded developer machine value.
  5. Confirm an explicit existing worker profile is preserved even when another CLI is detected.
  6. Simulate no signed-in Codex/Claude CLI: Easy Install Native core passes with worker setup pending;
     an explicitly activated worker fails only that capability with one clear sign-in action.
  7. Compile config and inspect generated env for `START_GLASSHIVE`, `START_PROMPT_WORKBENCH`,
     `VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_*`, `GLASSHIVE_DEFAULT_WORKER_PROFILE`, and memory
     hardening env keys.
  8. Start or harness Prompt Workbench with a synthetic admin and confirm the built-in
     `Subconscious Deep Thought` schedule is active, `glasshive_host`, and uses the selected worker
     profile.
  9. Inspect install-summary rows and confirm the user sees GlassHive, Prompt Workbench, Nightly
     Reflection, and Memory Hardening status without private account/path leakage.
- Expected result: new Easy Install Native reaches first chat without worker CLI auth; later activation
  compiles a runnable nightly workflow; upgrades preserve explicit state; no owner/private identity,
  raw prompt, local path, or manual App Support edit is required.
- Forbidden result: capability code omitted from Easy Install, missing worker auth blocks first chat,
  upgrade flips an explicit active/disabled choice, setup-pending is called Ready, or any public
  artifact contains a real user email/path/token/raw prompt.
- Evidence to capture: focused release-test results, sanitized generated env key summary, preflight
  item statuses for Codex/Claude/none scenarios, Workbench synthetic seed row, install-summary rows,
  public-safety scan, and Claude review summary when used.
- Automation: `test_default_nightly_routines.py`, `test_wizard.py`, `test_preflight.py`,
  `test_config_compiler.py`, `test_cli_upgrade.py`, `test_install_summary.py`,
  `test_prompt_workbench.py`.
- Last run: PARTIAL 2026-07-19. The public Easy Install preset and isolated VM core now leave
  nightly routines, Prompt Workbench, and GlassHive disabled so worker authentication does not
  block first chat. Automated upgrade contracts preserve explicit disables. The
  [2026-05-31 report](reports/2026-05-31-default-nightly-workflow-install-upgrade-qa.md) remains
  historical evidence for post-activation behavior, but later activation and an established-user
  live upgrade are still unproved.

## `INST-004` - Easy Install Rich Brain Readiness

- Requirement: Easy Install, Custom Settings Install, and upgrade-shaped configs must converge on the full
  Viventium Cognitive System readiness contract without watering down parity or hardcoding a
  developer machine.
- Risk covered: a new user gets a thin install that omits the brain surfaces running in the mature
  local runtime, or the installer claims readiness while provider auth, transcript source, RAG,
  MCP/OAuth, worker CLI, or optional communications are still pending.
- Preconditions: synthetic config/temp state can be used for automated cases; public evidence must
  not include local account emails, private paths, tokens, transcript text, prompts, screenshots, or
  raw DB payloads.
- Required feature posture matrix:

| Surface | Easy Install/upgrade posture | Required test cases | Feature owner |
| --- | --- | --- | --- |
| Core app/helper | Installed | happy path, restart/status, generated env, public-safety | `qa/installer-resilience/` |
| First local browser account | Required first-run browser step | registration enabled only on safe local surface, first admin, login/logout, wrong password, restart, public-registration boundary | `qa/installer-resilience/` |
| Connected Accounts UI | Installed, provider connection pending | empty state, connect/test, denial, wrong account, expiry, reauth, disconnect, restart | `qa/connected-accounts-handoff/` |
| Agent Builder and user agents | Installed | seeded built-ins, create/edit, user-field preservation, live-vs-source drift, reload, tool availability | `qa/agent-config-continuity/` |
| MCP Builder and tool controls | Installed | empty state, discover/install/enable separation, permissions, secrets, failure/repair, removal | `qa/mcp-tooling/` |
| Prompt Templates | Installed | discover/create/edit/use, empty state, persistence, public/private safety | `qa/prompt-workbench/` |
| Memories, files, and bookmarks | Installed | empty state, create/import, retrieval, permissions, persistence, restore, deletion | `qa/memory-continuity/`, owning core UI cases |
| Feelings | Installed when enabled | ordinary navigation discovery, signed-out return, provider missing/degraded, persistence, narrow/a11y | `qa/emotional-cortex/`, `INST-012` |
| Scheduler | Custom Settings Install only | service health, DB ledger count, due item, callback proof, restart | `qa/scheduling-cortex/` |
| GlassHive | Custom Settings Install only | no-worker first-chat pass, Codex-ready, Claude-ready, explicit activation failure, worker profile preservation | `qa/glasshive_host_workers/` |
| Prompt Workbench | Custom Settings Install only | pending state, activation, health, visible schedule, completed run detail, restart | `qa/prompt-workbench/` |
| Nightly reflection | Custom Settings Install only | pending state, activation, scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger -> Workbench shows completed | `qa/prompt-workbench/`, `qa/scheduling-cortex/` |
| Memory hardening | Custom Settings Install only | pending state, activation, dry-run-first, eligible-user count, disabled-memory skip, power/thermal skip, run state | `qa/memory-hardening/` |
| Transcript ingest | Custom Settings Install only | no folder pending, folder set, missing folder, catch-up/manual ingest, privacy scan | `qa/meeting-transcript-memory/` |
| Conversation Recall/RAG | Custom Settings Install only | skipped by default, Docker/Ollama missing, enabled health, browser recall answer | `qa/conversation-recall-rag/` |
| Web search | Custom Settings Install only | local Docker path, hosted-key path, missing keys, SearXNG degraded, Firecrawl degraded | `qa/web-search/` |
| Groq activation | Optional post-ready provider | skipped/pending, invalid/revoked/quota/network/model rejection, live self-test, xAI fallback, Groq versus Grok wording | `qa/installer-resilience/` |
| Primary AI | OpenAI API key guided for the intended optimized Easy Install path; readiness waits for a live request and visible answer | key saved but untested, live probe, first visible Viventium answer, restart persistence, invalid/revoked/quota/network repair | `qa/connected-accounts-handoff/` |
| Secondary/fallback AI | Guided optional | skipped visible state, fallback configured, provider failure wording | `qa/connected-accounts-handoff/` |
| Voice | Custom Settings Install only | local Apple Silicon path, hosted guided path, disabled/setup-pending state, provider auth missing | `qa/modern-playground-voice/` |
| Telegram | Guided browser setup; Custom Settings operator adapter remains supported | encrypted token, pairing, two-turn delivery, Keychain compatibility, polling ownership/conflict, restart, repair, disconnect | `qa/telegram-runtime/`, `qa/channel-connections/` |
| Telegram Codex | Custom Settings Install only | separate token, missing token pending, polling conflict | `qa/telegram-runtime/` |
| Google Workspace MCP | Custom Settings Install only | pending OAuth, configured endpoint, expired token/action required | `qa/mcp-oauth/` |
| Microsoft 365 MCP | Custom Settings Install only | pending OAuth, Docker/prereq missing, endpoint/action required | `qa/mcp-oauth/` |
| Slack | Guided browser Socket Mode setup | manifest, encrypted tokens, pairing, missing scope, threaded/direct delivery, restart, repair, disconnect | `qa/channel-connections/` |
| WhatsApp | Guided Business Cloud setup | encrypted credentials, public HTTPS edge, callback verification, HMAC/tenant scope, idempotent delivery, restart, repair, disconnect | `qa/channel-connections/` |
| Code Interpreter | Off by default | disabled by choice, Custom Settings Install or later configure opt-in only, no public default-on example | `qa/installer-resilience/` until a dedicated owner exists |
| Skyvern | Off by default | disabled by choice, Custom Settings Install or later configure opt-in only, no public default-on example | `qa/installer-resilience/` |
| OpenClaw | Off by default | disabled by choice; the standalone bridge remains lab-only and must not claim LibreChat client wiring until authenticated initialize/tool-call and lifecycle acceptance are shipped | `qa/installer-resilience/` |
| Remote access | Off by default | local-only default, guided Custom Settings Install opt-in, tunnel state/error public safety | `qa/remote-access/` |

- Steps:
  1. Build Easy Install configs (`install.experience: express`) for no Docker, Docker present,
     Codex-ready, Claude-ready, and neither worker-ready scenarios.
  2. Build Custom Settings Install configs that select and skip each guided surface; confirm the same registry
     labels/guidance and no behavior fork.
  3. Run an upgrade-shaped reconciler over existing configs with explicit disables and confirm they
     remain disabled while readiness/status cards are added.
  4. Compile generated env and inspect only public-safe key presence for Scheduler, GlassHive,
     Workbench, nightly reflection, memory hardening, transcript source, RAG, web search, MCPs,
     Telegram, and voice.
  5. Run `bin/viventium status` or the install-summary harness and confirm every core brain surface
     shows `Ready`, `Needs setup`, `Degraded`, `Skipped`, `Disabled by choice`, or `Not available`
     with a concrete next action.
  6. Run feature-owner user-grade QA for any surface whose behavior changed. Browser-facing setup
     or Workbench proof must use a real browser surface before a release-ready claim.
  7. Run public-safety scans over changed docs, examples, QA reports, generated samples, and test
     fixtures.
- Expected result: Easy Install gives the full installed core spine plus honest boundaries for
  Custom Settings-only services; Custom Settings Install exposes the broader registry; upgrades preserve user choices; no
  public artifact leaks private data; and no optional/lab feature is falsely enabled by default.
- Forbidden result: supported brain capabilities are absent from the later setup surface, or their
  missing prerequisites block Easy Install Native first chat; Recall/RAG turns on from ambient Docker without opt-in; the installer invents
  secrets, transcript paths, OAuth grants, or account emails; WhatsApp is advertised without a real
  integration; Code Interpreter/Skyvern/OpenClaw/Remote Access appear default-on; or status says
  ready while a required provider/worker/ledger/callback is pending.
- Evidence to capture: registry coverage test, wizard simulations, generated env assertions,
  install/status rows, scheduler ledger summary, feature-owner case links, public-safety scan, and
  Claude review summary when used.
- Automation: `test_brain_readiness.py`, `test_wizard.py`, `test_install_summary.py`,
  `test_config_compiler.py`, `test_preflight.py`, `test_default_nightly_routines.py`,
  `test_prompt_workbench.py`.
- Last run: PARTIAL 2026-07-19. The public choices now use `Easy Install` and
  `Custom Settings Install`; internal `express`/`custom` compatibility remains covered. The Easy
  path discloses the browser primary-AI connection and skippable optional features without asking
  for Groq or worker credentials; focused naming/front-door tests pass. Configuration-only Brain
  Setup rows now say `Configured` and request a live/self-test instead of claiming `Ready`, and the
  full parent release suite passes. Completed-provider readiness, every applicable feature-owner
  live journey, and the decisive exact-artifact clean-Mac journey remain open. The 2026-05-31
  [implementation report](reports/2026-05-31-express-rich-brain-readiness-implementation.md) remains
  historical automated evidence, not the current result.

## `INST-005` - Truthful Full-Payload Backup And Restore

- Requirement: snapshot success means the complete documented payload is independently restorable;
  metadata-only continuity audits use different wording and status.
- Risk covered: a user accepts destructive installer/configure/upgrade/reset/uninstall QA because a
  helper said “Backup created,” then discovers chats, memory, Recall, schedules, auth, or state were
  never captured.
- Preconditions: disposable synthetic runtime with representative chat history, saved memory,
  Recall corpus, schedules, provider/auth references, Telegram configuration, helper selection, and
  component-version state.
- Steps:
  1. Inventory each continuity class and record public-safe counts/schema versions.
  2. Create a full snapshot through the public CLI and helper surfaces.
  3. Interrupt exports at representative stages and verify the prior good snapshot survives.
  4. After a real snapshot, force repeated metadata-only fallback attempts and prove each attempt
     creates a new immutable audit directory without rewriting any prior manifest.
  5. Point default and explicit restore selection at a metadata-only attempt and prove refusal occurs
     before a live audit or other restore-side state.
  6. Restore a complete payload into a separate disposable runtime, never over the source fixture.
  7. Compare counts/hashes plus visible chats, memory answer, Recall answer, schedule state, channel
     setup status, and reauthentication guidance.
  8. Verify snapshot, helper, manifest, logs, and restore summary use identical success/degraded/error
     semantics.
- Expected result: only a complete verified payload is called a recoverable backup; intentionally
  unexported Keychain secrets produce explicit reauthentication requirements.
- Forbidden result: metadata-only manifest exits as backup success or rewrites the latest snapshot
  manifest; metadata-only state is dereferenced as a restore payload; live DB files are copied
  unsafely; dumps land in source; partial restore is called complete; source runtime is overwritten.
- Evidence to capture: sanitized inventory/count/hash ledger, manifest status, interruption result,
  restore logs, browser-visible continuity, generated config/version alignment, and public-safety
  scan.
- Automation: snapshot-plan, manifest-schema, output-path, interruption, checksum, version, and
  restore contract tests plus real disposable restore QA.
- Last run: PARTIAL 2026-07-19. The public fallback creates a fresh immutable metadata-only
  attempt, refuses a private-helper no-op as a snapshot, and the helper explicitly says no
  recoverable payload was created. Default and explicit restore now refuse that marker before
  creating restore-side state. Uninstall now drains services and moves the entire App Support tree
  to a private recovery root outside the active path. In the disposable VM, a manual recovery
  restored the exact config hash, synthetic user, Mongo payload, and enabled Feelings state in the
  browser. This proves preserve-data uninstall safety, not a public one-click snapshot/restore or an
  independent-target domain ledger, so recoverable-backup acceptance remains open.

## `INST-006` - Transactional Configure And Reconfigure

- Requirement: all configure entrypoints edit a candidate derived from existing config, preserve
  unrelated user state, validate/compile, backup, atomically replace, reload, and roll back on
  failure.
- Risk covered: a user follows documented configure guidance and silently loses reliable settings,
  integrations, schedules, agents, memory policy, or future fields.
- Preconditions: disposable existing-user fixture with explicit disables, optional features,
  unknown forward-compatible fields, Keychain references, and generated runtime outputs.
- Steps:
  1. Run a no-op configure and compare config/output hashes.
  2. Change one field through interactive configure, recovery reconfigure, headless config input,
     helper UI, and upgrade reconciliation.
  3. Inspect a redacted semantic diff before apply.
  4. Cancel, close, crash, fail schema, fail compiler, and fail reload at separate stages.
  5. Confirm canonical config/generated output remains old until atomic apply and rolls back after a
     failed health check.
- Expected result: only the chosen field and required migrations change; unrelated/unknown values
  remain; retry is idempotent; rollback is visible and reliable.
- Forbidden result: direct canonical overwrite, secret values in diff/logs, unknown-field loss,
  explicit disables reset, generated output/config skew, or success after failed reload.
- Evidence to capture: public-safe before/candidate/after structural diff, backup verification,
  compiler summary, reload health, rollback result, and restart persistence.
- Automation: merge/preservation/property tests, atomic-write fault injection, entrypoint parity, and
  browser/helper QA in disposable state.
- Last run: PARTIAL 2026-07-19. Focused tests prove the headless CLI path deep-merges unknown fields,
  validates/compiles in a private candidate, creates a private backup, atomically applies, removes
  attempt state, and leaves canonical config byte-for-byte unchanged for invalid input. The VM
  re-applied Easy Install successfully, then a Custom Settings Install candidate with a missing
  Keychain reference failed with one clear message, no traceback, and the canonical config hash
  unchanged. Interactive helper preview, crash journal, and wider live-reload coverage remain.

## `INST-007` - Verified Bootstrap Destination And Release

Ownership: umbrella delivery case; piped command/download behavior remains owned by `PIPE-001` in
`qa/installer-piped-bootstrap/` and must be cross-run rather than duplicated here.

- Requirement: the public bootstrap proves destination identity and release authenticity before any
  mutation, then installs exact manifest versions.
- Risk covered: an unrelated repository is changed, mutable remote content executes, or local/pinned/
  built/installed versions silently diverge.
- Preconditions: disposable targets covering empty directory, valid prior Viventium clone, unrelated
  git repository, non-git files, dirty Viventium clone, offline/corrupt/partial artifacts.
- Steps:
  1. Invoke the supported public entrypoint against each target shape.
  2. Verify remote/release identity before fetch, checkout, pull, or script execution.
  3. Validate checksum/signature/provenance and capture manifest/SBOM/digests.
  4. Create synthetic signed release histories for no prior release, a valid next release, skipped,
     reused, duplicate, malformed, unsigned, and outer/embedded/payload sequence mismatch cases.
     Verify the protected workflow is globally serialized, checks every retained Native release,
     and begins no signing work unless the candidate is exactly the next sequence and the tagged
     shell floor matches it.
  5. On an established synthetic install, replay an older correctly signed payload and verify the
     persisted high-water mark rejects it. On a pristine target, verify the authentic current shell
     rejects a bootstrap below its reviewed floor; record that replay of an older valid shell plus
     its older signed release remains blocked on an external authenticated freshness authority.
  6. Interrupt download and component/bootstrap stages, then rerun.
  7. Compare selected release, component pins, compiled artifacts, helper bundle, and installed
     runtime versions.
- Expected result: unrelated/ambiguous targets fail without mutation; valid targets resume/repair;
  every delivery surface matches a verified immutable release.
- Forbidden result: any `.git` directory is trusted, mutable `main` is release truth, verification is
  skipped, failed downloads execute, or doctor accepts delivery skew as a clean-install pass.
- Evidence to capture: before/after target hashes/status, verified release metadata, journal stages,
  component/pin/artifact comparison, visible error/recovery, and public-safety scan.
- Automation: target-identity, signature/checksum, partial-download, resume, dirty-tree, and artifact-
  alignment tests plus `tests/release/test_native_release_sequence.py` signed-history/sequence
  replay regressions and fresh public-entrypoint QA.
- Last run: PARTIAL 2026-07-20. Destination-identity tests reject an unrelated origin, tracked-dirty
  state, and a clean local-ahead commit before CLI execution while accepting the supported SSH
  identity form. Native payload automation covers deterministic packaging, explicit unsigned local-
  QA policy, signed stable-manifest verification, hostile archives, durable immutable activation,
  lock/journal recovery, health rollback, and idempotent re-activation. The opt-in public Native
  hand-off has non-overridable empty trust slots and refuses network access or source fallback; the
  protected workflow also fails closed until approved public trust and release authorities exist.
  Focused sequence regressions now prove the embedded release policy rejects invalid/unbounded
  sequence values; exact outer/app/payload identity binding is present; signed release-history
  validation requires first sequence `1`, exact next sequence, unique tag/sequence, valid signature,
  bounded canonical index shape, and a globally serialized workflow. These source-level tests do
  not prove a pristine Mac has an authenticated current-release freshness authority.
  The default public entrypoint still installs mutable source. The exact architecture candidate
  producer, compiled/notarized bootstrap, real protected release, fresh public URL, interruption
  during download, and installed-artifact alignment remain unaccepted. See
  `reports/2026-07-19-native-payload-production-integration.md`.

## `INST-008` - Decisive Clean-Mac Easy Install Journey

Ownership: decisive cross-surface acceptance. It consumes `INST-005`, `INST-009`–`INST-012`, and
feature-owner results; it does not replace their detailed matrices.

- Requirement: the exact shipped artifact completes the natural first-user journey on every
  supported macOS class.
- Risk covered: isolated subsystem tests pass while a novice encounters undisclosed prerequisites,
  context switching, fake success, dead ends, or a first chat that cannot answer.
- Preconditions: disposable macOS VM or sacrificial Mac with no host mounts/personal state,
  synthetic account/provider/channel data, checkpoints before install/start/uninstall, and the exact
  public release artifact.
- Steps:
  1. Run the single supported command and choose Easy Install.
  2. Read prerequisite/time/privacy/cost disclosure and exercise missing-prerequisite recovery.
  3. Complete install, live health, first local account, and preferred provider connection.
  4. Send a synthetic first prompt and inspect the visible answer, details, logs, and persisted turn.
  5. Skip and later add optional channels; confirm setup, provider activation, worker readiness, and
     real delivery remain distinct, actionable states.
  6. Discover Feelings from ordinary chat, use it, return, refresh, restart services, and restart the
     machine.
  7. Snapshot, uninstall/preserve, restore into disposable state, and verify visible continuity.
- Expected result: minimal truthful choices lead to a useful answer; all optional setup is deferrable;
  every recovery preserves progress; restart/restore retain documented state.
- Forbidden result: undisclosed Groq/worker/browser gates, process-only success, direct-URL-only
  feature discovery, owner-state dependency, mocks replacing browser proof, or partial case hidden
  by release wording.
- Evidence to capture: timestamped stage ledger, visible screenshots with synthetic data, progress/
  retry/cancel states, first answer/detail, logs/DB/state, pins/artifacts, restart, restore, and final
  wording comparison.
- Automation: full release suite and focused component tests are required supporting evidence.
- Last run: PARTIAL 2026-07-21. An isolated Tart VM passed source-candidate install, rerun, restart,
  synthetic registration/login, Connected Accounts handoff, provider start/cancel/retry,
  disconnected-chat repair wording, Feelings discovery/toggle/refresh/restart persistence, dirty-
  component upgrade refusal with service recovery, idempotent reinstall, full-tree uninstall
  preservation, and manual recovery. Separate headed provider lanes completed persistent useful
  answers for OpenAI, Anthropic, Groq, and Grok, and a provisional-payload lane independently
  restored the synthetic browser user. An optional channel, ordinary-chat right-control Feelings,
  the exact signed artifact, and one uninterrupted full platform journey remain open.

## `INST-009` - Configured Versus Live-Ready Status

- Requirement: installer summary, Brain Setup, CLI status, helper, and feature UI share one structured
  readiness state derived from current live self-tests.
- Risk covered: users believe a provider, search, Recall, voice, channel, folder, or worker is usable
  because a key/flag/path exists.
- Preconditions: synthetic adapters covering no config, valid config/no test, success, invalid auth,
  forbidden/missing scope, quota/rate limit, network loss, unhealthy dependency, unsupported, and
  update required.
- Steps:
  1. Feed the same state to every status surface.
  2. Run live self-tests and verify transitions and last-tested metadata.
  3. Exercise retry, reauth, repair, disconnect, revoke, and secret deletion.
  4. Refresh/restart and verify state persistence and expiry semantics.
- Expected result: `Configured` is distinct from `Ready`; failure class and one next action agree
  across UI, structured output, and sanitized logs.
- Forbidden result: config presence produces Ready, generic “failed” hides failure class, stale
  success persists indefinitely, or surfaces contradict one another.
- Evidence to capture: state-transition ledger, visible cards/status, structured output, adapter
  self-test result, persistence, logs, and wording comparison.
- Automation: shared enum/schema, adapter contract, cross-surface snapshot, expiry, and error mapping
  tests plus real provider/channel failure QA.
- Last run: PARTIAL 2026-07-21. The shared install summary renders configuration-only enabled
  surfaces as `Configured` with a live/self-test action and never as `Ready`; the regression contract
  covers every Brain Setup row. Scoped headed OpenAI, Anthropic, Groq, and Grok lanes distinguish
  invalid-key, quota, outage, and network repair states. A shared cross-surface state model,
  last-tested expiry, helper parity, and the remaining provider/channel matrix remain open.

## `INST-010` - Secure Provider And Channel Lifecycle

Ownership: umbrella integration lifecycle; Telegram detail remains in `qa/telegram-runtime/`, and
Google/Microsoft OAuth detail remains in `qa/mcp-oauth/`.

- Requirement: each supported integration has a versioned capability/auth/scope/secret/self-test/
  health/migration/disconnect/revoke contract and novice-readable UI.
- Risk covered: credentials leak, users cannot recover wrong/expired accounts, unsupported channels
  appear real, or provider names/entitlements are confused.
- Preconditions: synthetic test accounts/bots and disposable Keychain/runtime state; no personal or
  production account may be used in public evidence.
- Steps:
  1. Connect and live-test each shipped provider/channel with least scopes.
  2. Exercise denial, wrong account, invalid/revoked credential, missing scope, quota, network,
     dependency, and provider outage.
  3. Reauthenticate/reconfigure without deleting unrelated state.
  4. Disconnect, upstream revoke where supported, and separately delete the local secret.
  5. Inspect Keychain references, browser storage, config, logs, diagnostics, and reports for leakage.
  6. Verify Groq API and xAI API/Grok wording; verify Slack/WhatsApp setup, failure, repair, and
     delivery states are specific and truthful.
- Expected result: user sees privacy/cost/data destination, current capabilities, live state, and a
  specific recovery action; raw secrets exist only in approved secret storage.
- Forbidden result: consumer subscription presented as API entitlement, plaintext secret, embedded
  webview OAuth, overbroad scopes, fake unavailable integration, or disconnect silently retaining/
  deleting credentials.
- Evidence to capture: capability manifest, least-scope grant, live self-test, failure/recovery UI,
  Keychain/reference audit, restart, revoke/delete result, and diagnostics redaction.
- Automation: adapter schema/state/error/redaction tests plus real synthetic account/channel QA.
- Last run: PARTIAL 2026-07-21. Headed Chromium passed the stable browser-entered OpenAI,
  Anthropic, Groq, and Grok/xAI API-key journeys on 2026-07-20, including useful answers,
  restart persistence, distinct failure repair, Disconnect, zero post-disconnect provider contact,
  and re-add. Custom Settings compiler tests now prove all four Keychain references map to their own
  source/service env values while Native output remains sentinel-only; a missing reference preserves
  the prior generated runtime. The added browser-residue guard passes its fail-closed offline test,
  but has not run headed. Existing compiler coverage continues to protect the operator Telegram
  `0600` service env; browser channels are owned by LibreChat rather than parent compiler secrets.
  Provider-side revocation/real accounts, native Keychain/TCC, external Telegram delivery,
  Google/Microsoft, Slack delivery, and WhatsApp webhook delivery remain open.

## `INST-011` - Isolated Platform And Failure Matrix

- Requirement: installer acceptance runs on isolated supported systems across hardware,
  prerequisites, resources, network faults, interruption, rerun, rollback, and uninstall.
- Risk covered: a mature owner Mac hides clean-install failures or testing damages personal state.
- Preconditions: disposable macOS targets with no writable host mounts and synthetic data; separate
  Intel target only if Intel remains supported; optional Linux VM profile for non-macOS subsystems.
- Steps:
  1. Run the documented supported OS/architecture matrix.
  2. Vary Xcode/Homebrew/runtime/Docker state, disk/RAM, ports, permissions, and virtualization.
  3. Inject offline/DNS/proxy/TLS/rate-limit/corrupt/partial-download failures.
  4. Cancel, quit, crash, and reboot at every transactional journal stage.
  5. Rerun, repair, update, migrate, roll back, downgrade, uninstall-preserve, and explicit delete.
  6. Exercise Gatekeeper/notarization/quarantine, first-launch permissions, MDM/no-admin, Safari
     and default-browser handoff, and a non-English macOS locale.
  7. Exercise forgotten local password without SMTP, a second local user, multiple local accounts,
     and cross-machine restore.
  8. Exercise laptop sleep, concurrent double install/locking, upgrade while a schedule runs,
     day-two disk exhaustion, and DB schema downgrade/forward-migration refusal.
  9. Run the recurring QA-report generation workflow and prove it produces contract-complete,
     public-safe evidence.
- Expected result: each failure is specific, bounded, resumable, and leaves the prior good state or
  verified recovery point intact.
- Forbidden result: different `HOME` treated as isolation, Linux container result called macOS
  acceptance, writable personal mounts, destructive retry, or unsupported matrix left ambiguous.
- Evidence to capture: environment policy, snapshot checkpoints, stage journal, visible errors,
  before/after filesystem/service state, installed artifacts, and public-safe report.
- Automation: fault-injection harness plus real platform runs.
- Last run: PARTIAL 2026-07-20. A no-share Tart VM ran the Native source-candidate journey. A
  separate Apple-silicon VM with no host filesystem mounts ran Easy Install Docker core install,
  restart, Docker-daemon loss and recovery, target-scoped failed-start cleanup, browser onboarding,
  and preserve-data uninstall. Its no-mount policy prevented the current Recall/RAG bind-mounted
  Compose graph from running. The wider low-resource, offline/network, interruption, OS,
  architecture, signed helper, Keychain/TCC, public restore, accessibility, Docker Desktop GUI, and
  physical sleep/wake matrix remains open. The exact real-hardware
  preparation, connection, evidence, comparison, and teardown lane is documented in the
  [MacBook Air handoff](macbook-air-docker-qa-handoff.md).

## `INST-012` - Feelings Discovery And Setup Guidance

- Requirement: `54_Emotional_Cortex_And_Feeling_State.md` now requires Feelings in ordinary
  right-side control-panel navigation under the same startup gate as the account-menu route, with
  contextual account/provider recovery that preserves the user's place.
- Risk covered: flagship functionality exists but users never find it, direct routes dead-end, or
  missing setup forces them to infer an unrelated account-menu flow.
- Preconditions: exact built LibreChat artifact in disposable state with feature enabled/disabled,
  signed in/out, provider ready/missing/degraded, narrow/mobile, reduced-motion, and keyboard cases.
- Steps:
  1. From ordinary chat, open the right control panel and select Feelings.
  2. Verify active/tooltip/keyboard/narrow layout and return-to-chat behavior.
  3. Repeat signed out and confirm login return target.
  4. Repeat with feature disabled, provider missing, invalid, quota-limited, and unavailable.
  5. Preserve a draft/current state while connecting or repairing.
  6. Use Feelings, refresh, open a second tab, restart, and compare persisted state/logs/config.
- Expected result: Feelings is discoverable without URL knowledge; unavailable/setup states explain
  what is missing, data destination, one Connect action, and a local alternative when supported.
- Forbidden result: direct-URL-only QA, hidden entry while feature is enabled, empty/error page,
  lost draft, prompt/name heuristics, inconsistent account-menu/control-panel availability, or
  source-only acceptance without built/installed artifact.
- Evidence to capture: browser video/screenshots with synthetic content, accessibility tree,
  enabled/disabled/startup config, provider state, persistence, logs/DB, nested commit, parent pin,
  built artifact, and installed artifact.
- Automation: side-panel rendering/navigation/state tests plus real Playwright/browser QA.
- Last run: PARTIAL 2026-07-20. Node 24 production build, focused contracts, login/setup handoff,
  account-menu keyboard activation, nine visible bands, enabled toggle, DB confirmation, and
  persistence across refresh, runtime restart, idempotent reinstall, and manual uninstall recovery
  pass in isolated QA. The right control-panel link exists in source but has not been exercised on
  the real browser surface. Right-control parity, native assistive technology, completed/degraded
  provider states, parent pin, signed shipped bundle, and release-installed artifact remain
  unproved.

## `INST-013` - Loopback-Only Local Service Boundary

- Requirement: local mode explicitly binds user-facing and control services to loopback; intentional
  remote access is enabled only through its declared authenticated mode.
- Risk covered: a framework's wildcard default silently exposes an unauthenticated or sensitive
  local surface to the LAN on some machines.
- Preconditions: exact built/installed runtime on disposable macOS targets with firewall on/off,
  active LAN interface, remote access disabled/enabled, and synthetic data only.
- Steps:
  1. Start local-only mode and inspect listening addresses for every documented service.
  2. Probe each service over loopback and every non-loopback interface from the host and a second LAN
     machine.
  3. Repeat with macOS firewall on/off and after restart/upgrade.
  4. Enable each supported remote-access mode and prove only its declared authenticated ingress is
     reachable; direct LAN listeners remain closed unless explicitly supported and disclosed.
  5. Compare launcher arguments, generated config, helper/status wording, socket table, access logs,
     and visible UI.
- Expected result: local mode binds to `127.0.0.1`/`::1` explicitly and non-loopback probes fail
  independent of host firewall behavior; remote access exposes only its declared route.
- Forbidden result: `0.0.0.0`, `[::]`, or `*` listener in local mode; firewall treated as the only
  boundary; a localhost URL used as proof of a loopback bind; remote mode exposing extra ports.
- Evidence to capture: sanitized socket matrix, loopback/LAN probe results, launcher arguments,
  firewall posture, remote-mode ingress result, restart result, logs, and public-safety scan.
- Automation: explicit-host launcher contract plus real two-host macOS network QA.
- Last run: PARTIAL 2026-07-19. Both modern Playground Next launch branches pass explicit
  `-H 127.0.0.1`; scheduler startup now also supplies `--host 127.0.0.1`; shell syntax and focused
  launcher tests pass. In the disposable Easy Install VM, Playground remained deferred, API `3180`,
  web `3190`, Mongo, and scheduler listened only on loopback, direct
  probes to the guest's non-loopback address failed, and the live CLI still reached both services
  over localhost. QA then caught and fixed a truthful-copy defect where status advertised a raw
  LAN URL that the listener could not serve; the updated VM status shows localhost only. A
  second-LAN-host probe, firewall on/off, every remaining service, and all supported remote-access
  modes remain open.

## `INST-014` - Shared Easy Install Native And Docker Profile Contract

- Requirement: `install.experience` and `install.mode` select one shared implementation. Public
  Easy Install maps to internal `express`; Easy Install Native reaches a persistent first answer
  without Docker/developer-tool/optional-worker/voice prerequisites; Easy Install Docker adds
  capabilities without forking lifecycle behavior.
- Risk covered: a reduced test-only installer passes in a VM while the shipped Docker path uses
  different transactions, setup states, recovery logic, or wording; optional features become
  hidden mandatory prerequisites again.
- Preconditions: exact candidate manifest/payload, disposable Tart VM without host mounts,
  synthetic provider account, and later a disposable physical Mac for the Docker delta.
- Steps:
  1. Generate Easy Install Native, Easy Install Docker, Custom Settings Install Native, and
     legacy-existing configs; compare
     shared transaction/journal/readiness fields and only the declared capability delta.
  2. Run Easy Install Native from the public candidate entrypoint with no Docker, Homebrew, Git, Xcode,
     pnpm, uv, Python, worker CLI auth, Groq key, voice models, or optional channel credentials.
  3. Create the first local user, connect one provider in the browser, prove a real rendered answer,
     refresh, restart services, and restart the VM.
  4. Exercise offline/corrupt/interrupted payload, low disk/RAM, occupied ports, double install,
     provider denial/invalid/quota/network, failed upgrade rollback, preserve-data uninstall, and
     restore.
  5. On the physical Mac, rerun the same lifecycle with Easy Install Docker and exercise only Docker,
     hardware permissions, Docker-backed capabilities, LAN/device, sleep/wake, and resource delta.
- Expected result: both profiles use the same lifecycle and state vocabulary; Native is a real
  useful product; Docker-only failures do not invalidate a healthy Native core; optional setup can
  be added without reinstalling.
- Forbidden result: source build or package-manager prerequisites on the final Native path, EOL
  runtime, mutable `main`, unsigned/unverified public payload, different profile implementations,
  configured-only Ready, personal-state dependency, or mocks/source inspection replacing the real
  browser and machine paths.
- Evidence to capture: manifest/digests/pins, journal, visible terminal/browser ledger, payload and
  installed-artifact identity, process/listener/resource measurements, config/readiness states,
  logs/DB persistence, restart/restore, VM snapshots, Docker delta, and public-safety scan.
- Automation: profile/schema/wizard/preflight/compiler/service/manifest/journal/rollback tests plus
  real Playwright and Tart/physical-Mac acceptance.
- Last run: PARTIAL 2026-07-20. Profile-aware wizard/compiler/preflight/native startup and status,
  exact Mongo vendor acquisition, a Node 24 production build, current-attempt failure detection,
  signed-manifest payload reference automation, isolated Tart install/restart/reinstall, synthetic
  local account, Connected Accounts authorization start/cancel/retry, disconnected guidance,
  account-menu Feelings, failed-upgrade recovery, Custom Settings Install rollback, uninstall
  preservation, and manual recovery pass. The VM still used a source candidate and a base with
  dormant developer tooling;
  the Node 24 source layers still lack exact-payload process provenance, and no signed public
  payload has completed provider answer plus restore on the same installed artifact; the full fault
  matrix and physical-Mac Docker Desktop delta also remain open. An isolated no-host-mount Docker VM now passes the core source-candidate
  install/start/browser/restart/daemon-recovery/uninstall delta, but used a QA-only empty component
  manifest because the then-selected nested checkout was dirty and not aligned with the parent pin.
  That rejected-payload finding is historical. Current lock refs equal all 11 fetched nested
  `origin/main` commits, and every merged tree equals its clean audited review head. Replacement
  built/payload/shipped/installed artifact identity remains unrun.

## `INST-019` - Failure, Rollback, And Removal Ownership

- Requirement: every failed start, reset, and uninstall mutates only the state owned by the exact
  install target and preserves a recoverable checkpoint.
- Risk covered: a failed attempt leaves a native Mongo process behind, a later CLI process forgets
  whether it owns the helper, or disabled Telegram cleanup removes an unrelated fixed-label job.
- Preconditions: isolated App Support target, synthetic process group/LaunchAgent recorder, and a
  dedicated Docker endpoint and volume namespace.
- Steps:
  1. Force Docker Mongo acquisition to fail after the launcher starts the target-scoped native
     fallback; verify install rollback drains the recorded process group and pid records.
  2. Install with helper creation explicitly skipped, exit that shell, then uninstall from a clean
     process without the skip environment variable.
  3. Stop with Telegram disabled and no receipt; repeat with a target-valid synthetic receipt.
  4. Remove the selected Docker daemon, run preflight against its explicit endpoint, restore the
     daemon, and restart the core.
- Expected result: failed-start ports/processes are clean; uninstall backs up App Support and skips
  helper removal from the persistent receipt; no-receipt Telegram makes no launchctl call; daemon
  preflight fails closed and recovery preserves the named volume.
- Forbidden result: broad process-name kill, helper removal inferred from the current shell,
  launchctl access inferred from a fixed label, destructive App Support deletion before ownership
  is read, or Docker context fallback accepted as outage evidence.
- Evidence to capture: target-scoped process commands, pid/pgid cleanup, receipt mode and decision,
  stop/uninstall logs, explicit Docker endpoint, loopback health, named-volume count, and public-safe
  dated report.
- Last run: PARTIAL 2026-07-21. The expanded synthetic matrix collected 300 fault/native cases. Its
  first run passed 296 and correctly failed four helper delivery checks after an accessibility
  source edit; the stale expectation was corrected, the universal helper rebuilt, and all five
  affected source/hash/prebuilt-install checks then passed. This supports source-level rollback,
  low-disk, ownership, and concurrency behavior only. Physical crash/power loss, reboot, sleep/wake,
  broader resource/network faults, MDM/no-admin, downgrade/delete breadth, headed Docker Desktop,
  and exact signed-artifact proof remain open.

## `INST-024` - Single Supported Node Runtime

- Requirement: preflight, shared PATH setup, doctor, dependency installation, production build,
  every product/optional launcher, the macOS helper, packaged runtime, status, and diagnostics select
  the same supported Node major.
- Risk covered: a fresh install downloads two Node runtimes, validates/builds under one major, then
  launches under another or fails because the second undeclared formula is unavailable.
- Preconditions: disposable clean macOS target, exact candidate payload, no host/global Node path,
  and process/path tracing enabled.
- Steps:
  1. Assert one version source owns every Node requirement and formula/path reference.
  2. Install with no Node present; record downloaded payload/formula and resolved `node`/`npm` paths.
  3. Build, start, probe, restart, upgrade, rollback, and run doctor/status; record runtime version
     and executable identity at every stage.
  4. Repeat with an unsupported global Node first on `PATH`, automatic dependency installation
     disabled, and the supported runtime missing/corrupt.
  5. Verify the exact packaged artifact carries the approved runtime and requires no second Node
     download before the first answer.
- Expected result: one supported pinned runtime owns every stage; unsupported PATH entries cannot
  override it; failures name one repair action and retain the last healthy release.
- Forbidden result: preflight passes Node 24 while the launcher installs/prepends/requires Node 20;
  build-only success is described as runtime acceptance; Homebrew silently supplies a second major.
- Evidence to capture: cross-layer contract output, installed files/formulas, resolved executable
  paths, process environment, build/start/restart versions, exact payload digest, timing/resource
  delta, and visible failure/recovery wording.
- Automation: a source contract that compares the owning Node-major constant/reference across
  preflight/common/doctor/LibreChat launcher/optional launcher/helper/package, plus exact-artifact
  clean-install behavioral QA.
- Last run: PARTIAL 2026-07-19. Cross-layer regressions reproduced and then closed the Node 20/24
  split across preflight/common/doctor, the LibreChat and Skyvern launchers, and the macOS helper.
  Six source surfaces now select Node 24, both shell launchers pass syntax, the helper rebuilds, the
  complete parent release suite passes, and the VM built, started, and restarted the source candidate
  under Node 24. Exact-payload process-path provenance and proof that no second runtime is resolved on
  a pristine install remain open.

## `INST-025` - Helper Bundle Ownership And Rollback

- Requirement: source helper install/uninstall validates the Applications directory without
  following symlinks, recognizes only the exact owned or historical Viventium helper shape, and
  replaces it through same-filesystem descriptor-relative staging and backup. Captured directory,
  bundle, and content identities remain the authorization boundary through commit or rollback.
- Expected outcome: an unrelated `Viventium.app`, symlinked `~/Applications`, or malformed legacy
  bundle fails before mutation; a replaced parent, changed same-inode bundle, partial activation,
  or interrupted result handoff fails closed, restores the prior owned helper when safe, and retains
  any backup whose identity can no longer be proven.
- Forbidden result: filename-only `rm -rf`, following a symlink into external personal data,
  deleting an unknown or in-place-changed app, losing activation state between the child and shell,
  or leaving the prior helper unavailable after a safely recoverable failure.
- Evidence to capture: target and parent `lstat`/ownership, bundle ID/executable/owner marker,
  recursive content fingerprints, external sentinel before/after, private persisted activation
  state, injected backup/activation/persistence failures, restored executable bytes, and installed
  headed behavior.
- Last run: PARTIAL 2026-07-21. All 30 helper tests pass, including clean-directory creation,
  parent replacement, short state writes, child-to-shell interruption recovery, partial activation,
  changed candidate/backup contents, install/uninstall/rollback, and legacy migration. The owning
  build script rebuilt the exact `x86_64`/`arm64` universal
  fallback after source freeze, its source and binary digests match, clean synthetic install selects
  it without invoking Swift, and 310 helper-adjacent installer/runtime/release tests pass. Installed
  headed behavior and publisher signing/notarization remain unrun.

## `INST-026` - Exact Native Payload Compliance Inventory

- Requirement: derive JavaScript packages from the shipped `package-lock.json` physical graph,
  preserve duplicate paths, exclude pruned and export-subpath manifests, require exact runtime
  notice paths, inventory pip vendored notices, and cryptographically bind cited notices.
- Expected outcome: generator and verifier agree with the exact payload; any absent required runtime
  notice, notice tamper, graph omission, or unreviewed license expression blocks release.
- Forbidden result: recursive `package.json` inventory, a fixture-only pass, invented legal approval,
  or a successful scan after a cited notice changes.
- Evidence to capture: component archive hashes/paths, physical lock-graph counts, scan paths and
  SHA-256 values, consolidated notice digest, exact assembled payload file count, generator/verifier
  exit state, and unresolved-license summary.
- Last run: PARTIAL 2026-07-20. The pinned arm64 archives matched policy; the 164,754-file assembled
  payload matched all 2,633 physical JavaScript paths and inventoried 42 pip/vendored notice files.
  Generator and verifier correctly remain blocked by 110 license-policy review records.

## `INST-027` - Native Runtime Environment And First-Admin Closure

- Requirement: compile and ship a strict secret-free Native behavior environment; start children
  without inheriting host credentials; close backend registration synchronously after the one-time
  first admin; resolve that exact admin by immutable ID; seed and verify the full built-in agent
  graph; and three-way upgrade untouched managed fields without overwriting real user edits.
- Expected outcome: invalid direct registration proves the gate is initially controlled, direct
  registration returns `403` after first-admin success and after restart, login persists, the exact
  default-agent ID exists once in MongoDB, and child environments contain no host provider keys.
- Forbidden result: copying the full compiler or host environment, shipping unresolved placeholders
  or build paths, starting an unbundled MCP, returning setup success while direct registration is
  open, seeding a synthetic agent-owner user before the real admin, advertising unavailable tools or
  handoffs, assuming a pruned production dependency remains top-level, or claiming the agent exists
  from YAML alone without DB verification.
- Evidence to capture: compiled/installed env key policy and modes, assembled default hashes, process
  environment allowlist, zero TCP listener on `3180` before/after/restart, proxy `3190` result, first-admin
  state without email, post-prune execution of the built `@librechat/api` entrypoint, login after
  restart, real-admin author/owner ACL rows for every shipped agent, managed-baseline hash/drift,
  interrupted three-way reseed, maintenance logs, exact agent DB count, health result, and browser
  view.
- Last run: FAIL 2026-07-20 for the provisional exact local-QA payload. A fresh compile produced 167
  accepted behavior-only keys and no enabled external services; canonical Native MCP servers were
  empty and the compiled agent bundle retained only `file_search` on the main agent with no
  unavailable handoff. The payload installed in a disposable vanilla guest and MongoDB started, but
  the API failed before registration because built `@librechat/api` directly imported `mongodb`
  after the production prune had removed it. The direct owner now declares a peer dependency, the
  backend consumer declares the production dependency, and the lock records both. A clean copy then
  completed dependency install, package build, production prune, dependency audit, and actual
  `require('@librechat/api')`; the missing-external regression and success case passed after prune.
  The candidate workflow executes that runtime-load guard after every prune. Headed diagnostic QA
  then found the one-time page could not post under its CSP, omitted `confirm_password`, and left the
  ordinary `/register` route as a dead end. The source now moves the one-time token from the query
  string into an HttpOnly SameSite cookie before rendering a clean URL, allows only the same-origin
  setup POST, submits matching confirmation, intercepts `/register`, displays progress/retry errors,
  and preserves close/replay failure behavior. Its focused live-proxy tests pass. The Native API
  now listens only on an owner-checked private Unix socket; the `3190` proxy uses that socket for
  HTTP, setup, and WebSocket traffic, and a live regression proves an obsolete/foreign TCP target
  receives zero requests. The secret-free
  Native behavior contract also carries `VIVENTIUM_CONNECTED_ACCOUNTS_ENABLED=true`, so account UI
  discovery does not require a provider key or subscription-auth sentinel. This supporting proof
  does not replace a rebuilt exact payload: registration, direct-port closure, DB state, restart,
  Connected Accounts, browser, signed dual-architecture candidate, and replacement pristine
  lifecycle remain pending.

## `INST-028` - Native Candidate Public-Safety Boundary

- Requirement: produce host-independent prompt metadata; exclude runtime logs, audit JSON,
  `__pycache__`, `.pyc`, and `.pyo`; prevent bootstrap self-check from regenerating bytecode; seal
  completed app bundles only after owned resources exist; and fail closed when the exact candidate
  contains a producer workspace/temp prefix, private home/temp path in Viventium-owned output, or
  high-confidence secret. The same candidate must embed a sanitized component-policy projection
  containing the exact LibreChat commit and every shipped runtime version/architecture digest.
- Expected outcome: the assembled payload and bootstrap are relocatable and public-safe, while
  dependency source directories with legitimate names such as `logs` remain intact.
- Forbidden result: sanitizing only source diffs, scanning only text, recording raw matched values in
  public evidence, signing an incomplete app before owner/self-check mutations, or deleting package
  source merely because a directory has a generic name.
- Evidence to capture: stable prompt paths, excluded-artifact inventory, exact candidate file/byte
  counts, completed-bundle signature verification, zero post-self-check bytecode, producer-prefix
  arguments, extracted-metadata-to-policy comparison, pass/fail exit, and only sanitized relative
  finding paths.
- Last run: PARTIAL 2026-07-22. The old exact local-QA candidate failed on the escaped prompt/build
  paths, audit JSON, and Python bytecode that motivated this case. The complete reconstructed parent
  source candidate and clean nested PR deltas now pass public-safety review, but source review is not
  exact payload proof. Rebuild, byte-scan, sign/notarize, and rerun the replacement immutable payload
  in a pristine guest.

## `INST-029` - Native Service Listener Ownership

- Requirement: before creating first-admin state, machine secrets, service records, or database
  changes, Native start must prove that the public proxy TCP listener and the private MongoDB/API
  Unix sockets are free or owned by the exact guarded PID recorded for the
  active immutable release. Readiness, health, and status must preserve that PID-to-listener proof
  and semantically probe the API; an HTTP response or successful connection alone is not ownership
  evidence.
- Risk covered: a second installation, stale record, foreign service, or owner runtime on the same
  TCP port or socket path can be mistaken for the candidate's MongoDB, API, or web proxy. Maintenance could
  then reach state that belongs to another runtime while the candidate reports false success.
- Preconditions: isolated synthetic support roots and listeners; no personal App Support, database,
  browser profile, or runtime is an allowed fixture.
- Steps:
  1. With the required public TCP port and both private sockets free, start the exact candidate and
     correlate MongoDB/API socket and proxy PID records with operating-system listener PIDs. Prove
     MongoDB's process group has zero TCP listeners.
  2. Bind each required TCP port or socket path from an unrelated synthetic process, with and without
     a stale or forged record, and invoke start. Separately occupy historical API port `3180` and
     prove it receives zero Native proxy traffic.
  3. Serve syntactically healthy API and release-health responses from the unrelated process.
  4. Exercise status, doctor, restart, interrupted start, and retry after releasing the collision.
  5. Confirm the collision path never creates first-admin state or secrets, never runs maintenance,
     never opens a database connection, never signals the unrelated process, and explains the
     occupied port and safe repair.
- Expected result: a foreign or ambiguous listener fails closed before mutable initialization; only
  an exact active-release guarded PID can satisfy readiness, status, or health; releasing the
  synthetic collision permits a clean retry.
- Forbidden result: treating open TCP, an HTTP `200`, a matching health body, a PID record alone, or
  another Viventium runtime as proof that this candidate owns the service.
- Evidence to capture: sanitized before/after support-tree inventory, listener PID table, guarded
  process records, collision error, maintenance-call ledger, retry result, and shipped-artifact hash.
- Last run: PARTIAL 2026-07-20. Focused supervisor/proxy regressions prove that foreign required
  listeners are rejected before first-admin/secrets/spawn, both private sockets are owner/mode/path
  checked, the API is semantically probed, the MongoDB process group is required to have zero TCP
  listeners, historical TCP `3180` receives zero traffic, Native helper health uses proxied `3190`,
  and source/Docker helper health preserves its configured direct API port. An isolated exact
  MongoDB 8.0.23 command-line run produced one mode-`0600` Unix socket and no TCP listener.
  Exact-candidate interruption, status/doctor, and clean retry evidence remain required.

## `INST-030` - Isolated Browser Artifact Runtime

- Requirement: Artifact execution uses a dedicated loopback origin with exact runtime ownership and
  upgrade-safe caching in Native, source local-prod, side-by-side dev, and Docker profiles.
- Risk covered: authenticated-origin code execution, local-prod/dev port collision, dead Docker
  mappings, stale mixed runtime files, foreign-listener acceptance, and false healthy/ready output.
- Steps:
  1. Compile every profile and verify API/web/artifact ports and public URLs, including dev `4191`.
  2. Start each runtime and correlate API/artifact listener PIDs or guarded Native proxy identity.
  3. Run static and React Artifacts in a headed browser; exercise refresh, restart, and upgrade.
  4. Test missing/tampered index, foreign port, mismatched URL/listen port, Host/origin/framing,
     traversal/dotfile/method, stream-removal race, and unhashed-file cache behavior.
  5. Verify installer, status, helper, watchdog, stop/restart, and recovery never report ready while
     the isolated origin is unavailable or belongs to another process.
- Expected result: the isolated origin is private, release/profile-owned, fresh after upgrade, and
  required for readiness; ordinary chat remains available and failures have one safe repair path.
- Forbidden result: same authenticated origin, upstream Docker image without the patched listener,
  year-long immutable caching of unhashed assets, marker-only ownership, or a healthy claim when
  Artifacts cannot load.
- Evidence: compiled envs, listener/PID table, response headers and digests, browser network/console,
  restart/upgrade screenshot, installer/helper status, and exact nested/payload identities.
- Last run: PARTIAL 2026-07-22. The prepared two-origin runtime, focused browser paths, Native proxy
  integrity tests, complete post-merge 1,542-test parent suite, recorded post-merge 128-test
  workflow/manifest/payload/public-safety slice, historical pre-merge 311-test slice, and exact
  modern-playground headed run pass. Corrected LibreChat reviewed head `44ac1f7a...` is locally and
  hosted green; its exact tree is merged and pinned at `38527a8651...`. The exact
  payload, headed upgrade, and Docker-image browser run remain open.

## `INST-033` - Complete Non-Docker Source Easy Install

- Requirement: a new or established user can run one supported Easy Install command from the public
  source checkout, connect a preferred provider in the browser, immediately use the optimized
  Viventium agents/configuration, optionally configure Telegram, Slack, or WhatsApp, and retain the
  result through reinstall, restart, and upgrade without inheriting an owner's data.
- Risk covered: owner-machine leftovers masquerading as product defaults; raw credentials in
  browser or generated files; Groq/Grok custom-endpoint drift; hidden responsive navigation;
  optional channel failures blocking first chat; reinstall/upgrade data loss; unrelated-process or
  personal-state removal during uninstall.
- Preconditions: isolated support, cache, temp, browser, database, ports, and synthetic account
  roots; loopback-only synthetic providers; no owner runtime or personal state in scope.
- Steps:
  1. Run the public headless Easy Install source entrypoint with the minimal Native/non-Docker
     profile; open its browser handoff and create the first local synthetic administrator.
  2. Connect OpenAI, Groq, and Grok/xAI independently; for each, obtain two useful answers, refresh,
     restart, exercise invalid credential, quota, provider outage, network failure, Disconnect, and
     re-add, then confirm no request occurs while disconnected.
  3. Confirm the public main/core/background agent inventory and prompts match source of truth, and
     confirm a custom provider's base URL and headers survive Background Cortex initialization.
  4. Open Settings > Channels on desktop and 320-pixel layouts. Exercise Telegram, Slack Socket
     Mode, and WhatsApp Business Cloud API setup/cancel paths, secret masking, official setup links,
     secret-free Slack manifest, keyboard operation, refresh/reopen, and degraded recovery.
  5. Rerun Easy Install, perform the supported established-user upgrade/restart, and compare user,
     conversation, message, agent, prompt, provider, and channel state before and after.
  6. Uninstall through the supported command. Confirm only the isolated owned runtime is stopped or
     removed, its preserved state is recoverable as promised, and all task listeners close.
- Expected result: one command reaches a useful first chat; the user receives the public optimized
  Viventium configuration but no owner's conversations or database; provider and optional-channel
  failures are specific and recoverable; restart/reinstall/upgrade are idempotent; uninstall is
  ownership-bounded.
- Forbidden result: owner-specific state or prompts, raw secret persistence, `user_provided` used as
  an API key, silent provider remapping, old LiveKit playground routing, invisible navigation
  intercepting Settings, optional-channel failure blocking chat, data loss, or unrelated cleanup.
- Evidence to capture: sanitized command/timing ledger; headed browser outcomes and accessibility
  scan; loopback request counters; before/after counts and hashes; generated config and component
  pin identity; listener ownership; uninstall result; public-safety scan.
- Last run: PASS 2026-07-23. The isolated source Easy Install and warm reinstall passed; OpenAI,
  Groq, and Grok/xAI each passed a 12-step headed lifecycle with two answers, refresh/restart,
  classified failures, disconnect/no-request, and re-add; the 12-agent/74-prompt public baseline
  matched; Connected Channels passed six headed desktop/mobile cases with zero accessibility
  violations; continuity remained unchanged. The final established-user upgrade and owned uninstall
  evidence are recorded in the dated report. Vendor-side message delivery and a signed/notarized
  immutable Native payload remain separately scoped external acceptance gates, not source-path
  failures.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Installer Resilience. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | On installer/CLI/helper, generated env, status output, verify that install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | owning requirement for `INST-001` / `INST-001` | installer/CLI/helper, generated env, status output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-07-21; disposable source-candidate install/rerun/restart, build/dependency recovery, Custom Settings Install rollback, failed-upgrade recovery, preserve-data uninstall, independent provisional restore, doctor/compiler, and browser paths ran. Exact replacement artifact, native helper interaction, and wider physical recovery remain open. |
| `INST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | The user sees an honest setup, retry, or degraded-state result for INST-002; no fake success is accepted. | PARTIAL 2026-07-22; the complete local candidate review and `python3 -m pytest tests/release/ -q` result of 1,542 passed/11 skipped is current, while staged and remote parent-PR exactness remain separate. |
| `INST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | INST-002 remains correct after the persistence or parity step and final wording matches evidence. | PARTIAL 2026-07-22; complete local inventory and public-safety review pass. Corrected LibreChat is locally and hosted green and pinned; the final parent suite passes, while parent publication exactness remains required. |
| `INST-UC-004` | Run an Easy Install or upgrade-shaped install path and inspect the resulting nightly workflow defaults. | `39_Installer_and_Config_Compiler.md` / `INST-003` | `./install.sh` or `bin/viventium install/upgrade` harness, generated env, preflight, install summary, Workbench synthetic seed | Source, docs, config diff, preflight items, generated env keys, Workbench schedule row, focused release tests, and public-safety scan. | Easy Install reaches first chat without worker authentication; a user can activate the nightly workflow later; existing explicit state survives upgrade; no private identity is hardcoded. | PARTIAL 2026-07-19; public preset/VM core defer worker/nightly surfaces and automation preserves explicit disables; later activation and established-user live upgrade remain open |
| `INST-UC-005` | Run Easy Install and Custom Settings Install simulations, then inspect status/readiness for every brain surface. | `39_Installer_and_Config_Compiler.md` / `INST-004` | `./install.sh` or wizard harness, generated env, `bin/viventium status`, feature-owner QA surfaces | Registry rows, wizard choices, generated env keys, scheduler DB summary, install/status table, feature-owner cases, public-safety scan. | The core spine is installed; guided surfaces clearly say ready/pending/degraded/disabled/not available with next action; no private defaults or fake integrations appear. | PARTIAL 2026-07-21; labels, front-door mapping, minimal preset, configured-versus-ready truth, and four-provider browser lifecycles pass in their scoped lanes. One shared cross-surface readiness model and every remaining provider/channel/feature-owner live journey remain open. |
| `INST-UC-006` | Before a risky install/configure/upgrade/reset/uninstall, create and independently restore the promised backup. | `39_Installer_and_Config_Compiler.md` / `INST-005` | Public CLI/helper snapshot, disposable restore, browser, Recall, scheduler, status | Inventory, manifest, logical exports, counts/hashes, browser-visible continuity, logs, versions, public-safety scan | Only a complete independently restored payload is called a recoverable backup; metadata-only audit and reauth-required state are explicit. | PARTIAL 2026-07-21; a pristine no-tools VM created a complete provisional-payload backup, independently restored it, recovered the synthetic browser account, and preserved Connected Accounts/Feelings across refresh and full restart. Exact rebuilt artifact, helper interaction, provider/channel reconnect, and Recall rebuild remain open. |
| `INST-UC-007` | Change one setting on an established installation, cancel/retry/fail stages, and confirm all unrelated state survives. | `39_Installer_and_Config_Compiler.md` / `INST-006` | CLI/helper configure, candidate diff, compiler, reload, rollback, restart | Before/candidate/after structural diff, backup, generated output, health, persistence | Configure is transactional, idempotent, secret-redacted, and preserves explicit/unknown user fields. | PARTIAL 2026-07-19; Easy Install reconfigure succeeds and missing-secret Custom Settings Install fails without traceback or canonical drift; interactive helper/crash/wider reload coverage remains open |
| `INST-UC-008` | Run the public bootstrap against empty, valid, unrelated, dirty, offline, corrupt, and interrupted targets. | `39_Installer_and_Config_Compiler.md` / `INST-007` | Public one-command entrypoint, release manifest, component checkout, helper/installed runtime | Target before/after, identity verification, signature/digest, journal, pins/build/install versions | Only verified Viventium targets mutate; exact immutable release installs or resumes safely. | PARTIAL 2026-07-19; wrong-origin, tracked-dirty, and clean local-ahead targets are rejected; relocatable local assembly/install plus deterministic compressed build and verified activation pass; unprovisioned Native hand-off refuses fallback; exact dual-arch build, signed/notarized public bootstrap, live download/interruption, and installed-artifact alignment remain blocked |
| `INST-UC-009` | As a novice on a clean supported Mac, complete one command through first answer, optional channel, Feelings, restart, and restore. | `39_Installer_and_Config_Compiler.md` / `INST-008` | Terminal installer, helper, browser account/provider/chat, Telegram, Feelings, restart/restore | Timestamped UX ledger, visible output/details, logs, DB/state, config, pins/artifacts, persistence, final wording | Minimal truthful choices produce a useful persistent result; every failure/recovery preserves progress. | PARTIAL 2026-07-21; isolated source-candidate install and four-provider browser lifecycles now include persistent useful answers, while account-menu Feelings, restart/reinstall/recovery, preserve-data uninstall, and independent provisional restore pass in their scoped lanes. Optional channel, right-control Feelings, exact signed artifact, and one uninterrupted end-to-end novice run remain open. |
| `INST-UC-010` | Inspect setup/status before config, after config, after live success, and across each failure class. | `39_Installer_and_Config_Compiler.md` / `INST-009` | Install summary, Brain Setup, CLI status, helper, integration UI | Shared structured state, self-test, visible cards, logs, refresh/restart | Configured is distinct from Ready; exact failure and one repair action agree everywhere. | PARTIAL 2026-07-19; configured-only states no longer claim Ready; live error taxonomy/timestamps and every cross-surface state remain open |
| `INST-UC-011` | Connect/test/reauth/repair/disconnect/revoke/delete each supported provider or channel using synthetic accounts. | `39_Installer_and_Config_Compiler.md` / `INST-010` | Browser connected accounts/channels, Keychain, Telegram, Slack, WhatsApp, Google, Microsoft, status/diagnostics | Adapter manifest, least scopes, live requests, pairing, inbound/outbound delivery, failure states, secret scan, restart | Secure capability-scoped lifecycle works; provider activation and worker states are truthful; Groq and xAI/Grok are unambiguous. | PARTIAL 2026-07-22; headed Chromium previously passed OpenAI, Anthropic, Groq, and Grok API-key lifecycles. Channel source implementation is under combined browser/runtime QA; native Keychain/TCC, provider-side revoke, real synthetic Telegram/Slack/WhatsApp delivery, and Google/Microsoft remain open. |
| `INST-UC-012` | Exercise every supported platform/prerequisite/resource/network/interruption/recovery combination in isolation. | `39_Installer_and_Config_Compiler.md` / `INST-011` | Disposable macOS matrix, optional Linux subsystem harness, install journal, rollback/uninstall | Environment policy, checkpoints, visible errors, stage ledger, filesystem/services/artifacts | Failures are bounded, specific, resumable, and preserve prior good state. | PARTIAL 2026-07-21; disposable Native/Docker lanes and a 300-case synthetic fault/native slice cover important install, restart, rollback, ownership, concurrency, daemon, and preserve-data paths. Wider resources/network, signed helper/Keychain/TCC, Intel, physical power/sleep, headed Docker Desktop, and exact artifact remain open. |
| `INST-UC-013` | From ordinary chat, discover Feelings in the right control panel and recover signed-out/missing/degraded setup states. | `54_Emotional_Cortex_And_Feeling_State.md` / `INST-012` | Built/installed LibreChat in real browser, side panel, login, connected accounts, Feelings | Browser/a11y evidence, startup config, provider state, persistence, logs/DB, nested pin/artifact | Feelings is discoverable without a URL; guidance preserves place/draft and gives one clear connection action. | PARTIAL 2026-07-21; authenticated account-menu keyboard discovery, nine-band UI, refresh/restart persistence, provider-free load, 320 px/reduced-motion behavior, and failure/retry pass. The ordinary-chat right-control link is source-tested but has not run on the real browser surface; operator-disabled/degraded setup, signed artifact, and installed identity remain open. |
| `INST-UC-014` | Confirm local-only services work on loopback but are unreachable on non-loopback interfaces without remote access. | local privacy contract / `INST-013` | Exact built/installed runtime, socket table, host and second-LAN-machine probes, firewall states | Launcher args, generated config, helper/status, access logs, restart, remote-access mode | Explicit loopback binding is independent of firewall; remote modes expose only their declared authenticated ingress. | PARTIAL 2026-07-19; disposable Easy Install API/web/Mongo/scheduler sockets and non-loopback probes plus localhost-only status wording pass; second-host/firewall/optional-service/remote-mode coverage remains open |
| `INST-UC-015` | Install Easy Install Native without Docker/developer tools, connect OpenAI, and get a persistent optimized first answer; separately run the planned Easy Install Docker profile on isolated hardware. | `39_Installer_and_Config_Compiler.md` / `INST-014` | Exact Native candidate bootstrap/payload in Tart, browser setup/chat, helper/status, restart/restore; later isolated physical-Mac Easy Docker delta | Manifest/digests, journal, visible UI, provider probe, logs/DB/config, process/resource/listener matrix, installed artifact | Native is a useful immutable product; the separately consented Docker profile uses the same lifecycle and adds only declared capability adapters. | FAIL 2026-07-20 for the provisional exact local-QA payload: install completed and MongoDB started, but the API failed before registration on a pruned direct dependency. The clean-copy structural regression passes; replacement Native payload, optimized first answer, restart/restore, shipped Docker artifact, and physical Docker proof remain pending. |
| `INST-UC-016` | Install with no Node present, then build/start/restart and inspect which Node executable actually owns each step. | `39_Installer_and_Config_Compiler.md` / `INST-024` | Clean Native installer/payload, preflight, doctor, launcher, process table, status | Version contract, installed formulas/files, resolved PATH/executable, process environment, build/start logs, artifact digest | One supported pinned Node runtime owns every stage; no second major is downloaded or silently forced. | PARTIAL 2026-07-19; source contract, full parent suite, helper rebuild, and VM Node 24 production build/start/restart pass, while exact-payload process provenance remains unrun |
| `INST-UC-017` | Force a failed start, stop with Telegram disabled, restart after Docker-daemon loss, and uninstall from a new shell. | `39_Installer_and_Config_Compiler.md` / `INST-019`, `TR-010` | isolated CLI install/start/stop/preflight/uninstall, process table, Docker endpoint/volume | process group and pid records, receipt mode/decision, launchctl recorder, ports, Docker health, recoverable backup | Only exact target-owned processes/jobs are drained; outage is honest; retry works; uninstall preserves state and never infers helper ownership from transient environment. | PARTIAL 2026-07-21; the expanded 300-case synthetic fault/native slice and disposable source-candidate paths cover failure/recovery/removal ownership. Exact signed artifact and wider physical fault matrix remain open. |
| `INST-UC-018` | Freeze one candidate, run its clean-machine matrix through the storage guard, then remove the only disposable VM. | `39_Installer_and_Config_Compiler.md` / `INST-032` | QA host guard, Tart, Docker baseline, candidate VM and private evidence | persistent receipt, exact argv/events, host/Docker before/peak/after metrics, baseline resource sets, final QA-VM inventory | The run cannot start beside another QA VM, stops at budget limits, preserves unrelated state, and releases its lease only after exact cleanup. | PARTIAL 2026-07-21; fake-tool automation passed, while the real frozen-candidate run remains blocked pending an exact candidate and isolated machine. |
| `INST-UC-019` | Run the supported non-Docker source Easy Install from one command through first chat, providers, Channels, restart, reinstall, upgrade, and owned uninstall. | `39_Installer_and_Config_Compiler.md` / `INST-033` | Isolated public source entrypoint, headed browser, generated config, local DB/state, CLI lifecycle | Sanitized timings, visible setup/chat/Channels results, loopback request ledger, counts/hashes, agent baseline, component pins, listeners, uninstall receipt | A novice immediately gets the optimized public Viventium configuration without owner data; failures recover; continuity holds; cleanup touches only the isolated install. | PASS 2026-07-23; complete isolated source-path acceptance recorded in the dated report. |

## Release Test Traceability

- `tests/release/test_config_compiler.py`
- `tests/release/test_config_transaction.py`
- `tests/release/test_connected_accounts_onboarding_contract.py`
- `tests/release/test_directory_link.py`
- `tests/release/test_doctor_sh.py`
- `tests/release/test_express_launcher_summary.py`
- `tests/release/test_install_summary.py`
- `tests/release/test_install_experience_labels.py`
- `tests/release/test_installer_ui.py`
- `tests/release/test_preflight.py`
- `tests/release/test_default_nightly_routines.py`
- `tests/release/test_brain_readiness.py`
- `tests/release/test_bootstrap_components.py`
- `tests/release/test_cli_upgrade.py`
- `tests/release/test_continuity_audit.py`
- `tests/release/test_feelings_contract.py`
- `tests/release/test_feelings_navigation_contract.py`
- `tests/release/test_macos_helper_install.py`
- `tests/release/test_native_stack_helpers.py`
- `tests/release/test_native_candidate_transport.py`
- `tests/release/test_native_component_manifest.py`
- `tests/release/test_native_component_staging.py`
- `tests/release/test_native_macos_compatibility.py`
- `tests/release/test_native_payload.py`
- `tests/release/test_native_release_sequence.py`
- `tests/release/test_native_payload_builder.py`
- `tests/release/test_native_payload_assembler.py`
- `tests/release/test_native_public_safety.py`
- `tests/release/test_ci_release_workflows.py`
- `tests/release/test_openai_connected_account_lifecycle_qa.py`
- `tests/release/test_prompt_workbench.py`
- `tests/release/test_public_bootstrap_manifests.py`
- `tests/release/test_playground_loopback_contract.py`
- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_storage_guard.py`
- `tests/release/test_qa_results_public_safety.py`
- `tests/release/test_sandpack_runtime_contract.py`
- `tests/release/test_shell_init.py`
- `tests/release/test_wizard.py`
