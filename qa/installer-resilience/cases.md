# Installer Resilience QA Cases

## Case ID Convention

Use stable `INST-NNN` IDs for installer resilience cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `INST-001` | Install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | User-visible behavior matches source, docs, persisted state, and logs | installer/CLI/helper, generated env, status output | `tests/release/test_config_compiler.py` plus user-grade QA when visible | PARTIAL 2026-07-19; isolated Easy Install source-candidate install/rerun/restart, current-attempt build failure, dependency retry, failed-upgrade recovery, Custom Settings Install rollback, full-tree uninstall preservation, OAuth cancel/retry, doctor, compiler, helper, and authenticated browser paths ran; exact artifact, public restore workflow, and wider recovery matrix remain open |
| `INST-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | PASS 2026-07-19; the full parent release suite passed its QA template, ownership, and public-safety gates with 1,072 passed and 7 skipped |
| `INST-003` | Supported installs and upgrades include the nightly workflow without owner-specific setup, while new Easy Install Native core readiness defers its activation until worker setup. | A new user reaches chat without Codex/Claude CLI auth, can activate nightly work later, and an existing user's explicit active/disabled posture survives upgrade. | installer/CLI, preflight, config compiler, generated env, install summary, Workbench seed | `test_default_nightly_routines.py`, `test_wizard.py`, `test_preflight.py`, `test_config_compiler.py`, `test_cli_upgrade.py`, `test_install_summary.py`, `test_prompt_workbench.py` | PARTIAL 2026-07-19; the public Easy Install preset and VM core defer nightly/Workbench/GlassHive, and automated upgrade contracts preserve explicit disables, but later activation and an established-user live upgrade remain unproved |
| `INST-004` | Easy Install Brain Readiness aligns the installer with the cognitive-system runtime inventory without pretending user-owned integrations are ready. | A new or upgrading user gets the core brain spine automatically, guided setup for user-owned pieces, honest status/readiness rows, and no developer-private defaults. | wizard, preflight, config compiler, install/status summary, generated env, QA map, public examples | `test_brain_readiness.py`, `test_wizard.py`, `test_install_summary.py`, `test_config_compiler.py`, `test_preflight.py`, feature-owner suites as applicable | PARTIAL 2026-07-19; public copy now uses Easy Install/Custom Settings Install and configuration-only Brain Setup states no longer report `Ready`; decisive live-provider and clean-artifact journeys remain open |
| `INST-005` | A backup is called successful only when the complete promised payload is independently restorable. | Existing users can recover chats, saved memory, Recall/RAG, schedules, auth status, channels, config, and runtime selection after failure. | CLI/helper snapshot, manifest, databases, state, restore, browser | Snapshot/restore contract tests plus disposable full-payload restore QA | PARTIAL 2026-07-19; restore requires a positive v1 producer marker plus complete bounded domain/artifact/hash/content validation and rejects marker-less/corrupt/overlap/expansion inputs before target mutation. Standard-library validation-only is side-effect-free, returns `recoverable: false`, and unavailable apply exits `4` without partial mutation; complete capture/apply and browser-visible independent recovery remain open |
| `INST-006` | Configure/reconfigure is transactional and preserves existing user-managed state. | A user can change one setting without silently replacing unrelated configuration or losing a reliable setup. | CLI/helper/wizard, candidate config, compiler, semantic diff, reload, rollback | Candidate/merge/atomic-swap tests plus disposable existing-user QA | PARTIAL 2026-07-19; Easy Install reconfigure backed up and reapplied successfully, and a missing-secret Custom Settings Install attempt failed clearly with no traceback while preserving the canonical config; interactive helper preview, crash journal, and wider reload proof remain |
| `INST-007` | Bootstrap validates its destination and installs a verified immutable release. | One command never mutates an unrelated repository and every installed component matches the selected release. | bootstrap, target directory, release manifest, signatures/digests, component pins, installed artifacts | Bootstrap identity/signature/interruption tests plus fresh public-entrypoint QA | PARTIAL 2026-07-19; destination-identity and reference payload verifier tests pass, but the public source bootstrap is not an immutable signed/notarized payload and fresh exact-artifact QA remains unproved |
| `INST-008` | The exact public artifact completes the decisive Easy Install journey on a clean supported Mac. | A novice reaches a useful answer, optional integration, Feelings, and restart persistence with minimal truthful choices. | terminal installer, helper, browser onboarding/chat, channel, Feelings, restart | Cross-surface clean-Mac E2E ledger; automation supports but does not replace it | PARTIAL 2026-07-19; disposable source-candidate install/restart, account handoff, provider start/cancel/retry, Feelings, failed-upgrade recovery, reinstall, and uninstall/manual recovery pass; first answer/channel/public restore/exact artifact remain open |
| `INST-009` | Setup/status distinguishes configured values from live-tested readiness. | Users know exactly what works, what is pending, why it failed, and how to repair it. | install summary, Brain Setup, status, helper, provider/channel self-tests | Shared-state contract tests plus live failure matrix | PARTIAL 2026-07-19; configuration-only Brain Setup surfaces now say `Configured` and request a live/self-test rather than claiming `Ready`; the complete provider/channel failure matrix and cross-surface timestamps remain open |
| `INST-010` | Provider and channel onboarding is truthful, secure, recoverable, and capability-scoped. | Users can connect, test, reauth, repair, disconnect, revoke, and delete local secrets without exposing credentials. | connected accounts, Keychain, Telegram, Google, Microsoft, future Slack/WhatsApp, diagnostics | Adapter-state tests plus real synthetic account/channel QA | PARTIAL 2026-07-19; Connected Accounts handoff, disconnected state, OpenAI authorization start/cancel, and chat repair wording pass; completed provider lifecycle and fresh Telegram setup remain open, Slack is absent, and WhatsApp is unavailable |
| `INST-011` | Supported platform, prerequisite, resource, interruption, and recovery matrices are run in isolated environments. | Installer failures are bounded, specific, resumable, and never drift host state. | disposable macOS, optional isolated Linux/container harness, install journal, restart/rollback | Matrix automation plus real clean Apple Silicon and Intel when supported | PARTIAL 2026-07-19; a no-share Apple Silicon Tart lane covered install, rerun, restart, missing secret, dirty-upgrade recovery, uninstall preservation, and manual recovery; vanilla base, low-resource/network/interruption breadth, signed helper/Keychain, Intel decision, and physical Docker remain open |
| `INST-012` | Flagship features are discoverable from ordinary product navigation and guide missing setup. | A normal chat user can open Feelings without knowing a URL or inferring where provider setup lives. | LibreChat side panel, account menu, Feelings, auth/setup states, narrow/a11y layouts | Real Playwright/browser navigation, provider-state, refresh, persistence, and config/log checks | PARTIAL 2026-07-20; the isolated browser matrix now passes keyboard account-menu discovery, provider-free Feelings, refresh, 320px reflow, reduced motion, backend failure/retry, and signed-out redirect. Right-control parity, high-contrast acceptance, screen-reader/native UI, parent pin, and shipped-artifact alignment remain open ([report](reports/2026-07-20-inclusive-easy-install-browser-qa.md)) |
| `INST-013` | Local-only mode explicitly binds every user-facing service to loopback unless a declared remote-access mode owns exposure. | A new install is not accidentally reachable from the LAN because a framework default changed. | launcher, playground, LibreChat, helper/status, socket table, firewall/network matrix | Bind-host contract tests plus clean-Mac loopback/LAN probes | PARTIAL 2026-07-19; disposable Easy Install API, web, Mongo, and scheduler listeners were loopback-only, non-loopback probes failed, Playground was deferred, and status used localhost; second-host, firewall, remote-mode, and every optional-service matrix remain open |
| `INST-014` | Easy Install Native and Easy Install Docker use one profile-aware installer/onboarding/readiness/rollback contract, and optional capability prerequisites never block Native first chat. | A novice installs without Docker or developer tools, connects one provider, receives a persistent answer, and can add heavy capabilities later without reinstalling. | schema/wizard, preflight/compiler, native services, manifest/bootstrap, browser setup/chat, status, restart/restore | Profile contract tests, exact-payload tests, and disposable Tart browser/install matrix | PARTIAL 2026-07-19; source-candidate Tart install/restart/reinstall, browser account handoff, provider authorization start/cancel/retry, Feelings, failed-upgrade recovery, uninstall preservation/manual recovery, and full parent automation pass; signed no-developer-tools payload, completed provider answer, public restore, full fault matrix, and Docker delta remain open |
| `INST-015` | The public bootstrap installs an immutable, signed, notarized Native payload rather than compiling a mutable source checkout. | A clean Mac installs without Git, Homebrew, Xcode/CLT, npm, pnpm, uv, Python, or system Node. | bootstrap, release manifest, app/helper/runtime bundles, Gatekeeper | Signature/notarization/tamper tests plus exact-artifact clean-Mac install | BLOCKED 2026-07-19; verifier/activation reference tooling, tamper/rollback tests, matching source+binary sidecars, and universal architecture checks pass, but adjacent sidecars do not prove publisher provenance and the public bootstrap is not wired to a signed/notarized payload |
| `INST-016` | The exact payload works on a truly vanilla supported Mac with the published CPU/macOS/RAM/disk matrix. | A novice is not surprised by hidden developer dependencies or unsupported hardware. | macOS first run, helper, Keychain, runtime, resource monitor | Pristine VM/physical-Mac matrix | BLOCKED 2026-07-19; a no-share Apple Silicon Tart source-candidate lane passed install/build/start/restart, but the guest had dormant developer-tool state and no exact payload was available, so the required pristine no-developer-tools path could not run |
| `INST-017` | Provider onboarding completes the full lifecycle and proves a useful persistent answer. | Connect, deny, retry, expire, reauth, disconnect, revoke, and first/second chat are understandable and recoverable. | Connected Accounts, provider OAuth, chat, persistence, status | Real synthetic provider lifecycle browser QA | PARTIAL 2026-07-19; registration, setup handoff, disconnected guidance, OpenAI start/cancel recovery, Feelings, and persistence pass; no grant, self-test, answer, expiry, reauth, disconnect, or revoke was completed |
| `INST-018` | A complete synthetic installation can be backed up and independently restored across every promised continuity domain. | Existing users can prove recovery before relying on a snapshot. | chat/memory/RAG/schedules/auth/channels/config/runtime selection, helper/CLI/browser | Full-payload capture/restore ledger | PARTIAL 2026-07-19; the schema requires every promised domain exactly once with typed, hashed, bounded artifacts and explicit rebuild/reauth policy; stock-Python, overlap, archive-expansion and no-mutation regressions pass. Public capture remains metadata-only and the complete independent-target apply/browser ledger does not yet exist |
| `INST-019` | Interrupted, constrained, concurrent, rollback, upgrade, downgrade, and uninstall paths preserve a recoverable state. | Failures are bounded and retryable without corrupting the previous install. | journal, disk/network/process faults, ports, reboot, rollback, uninstall | Fault-injection matrix on disposable targets | PARTIAL 2026-07-19; dependency/build retry, restart, missing-secret configure rollback, preserve-data uninstall/manual recovery, and structured upgrade safety automation pass. A synthetic stray untracked parent file is preserved and blocks before state/source mutation with explicit preserve/remove or local-only guidance. The earlier dirty-upgrade VM run proved availability recovery but did not prove rollback; post-change live upgrade, low-resource/network/crash/reboot/downgrade/concurrency/delete breadth remain open |
| `INST-020` | The signed helper, SMAppService, Keychain, Gatekeeper, login startup, and user-visible repair actions work together. | macOS security prompts are minimal, truthful, and recoverable. | app/helper GUI, LaunchAgent, Keychain, Gatekeeper/notarization | Physical/headed macOS acceptance | PARTIAL 2026-07-19; source and binary sidecars match the exact universal raw helper and an installer-assembled app bundle verifies ad hoc; adjacent sidecars are not publisher provenance, the raw x86_64 slice is unsigned, and signed immutable manifest, Developer ID/notarization, headed permission prompts, login startup, and Keychain lifecycle remain blocked |
| `INST-021` | Easy Install Docker changes only declared capability adapters and preserves the Native onboarding/readiness/rollback contract. | A user can choose Docker without receiving a different or more brittle core product. | physical Mac, Docker Desktop, capability services, browser/status | Native-versus-Docker delta matrix | BLOCKED 2026-07-19; strict SSH identity and Viventium-scoped absence inventory pass, but full install is blocked inside the shared personal Mac's existing personal login pending a no-share VM or separate Standard QA user |
| `INST-022` | Every nested component commit, parent pin, compiled artifact, and installed artifact under test is identical. | A clean install receives the behavior that QA approved. | nested repos, `components.lock.json`, built client, public payload, installed runtime | Commit/pin/hash and runtime artifact alignment checks | FAIL 2026-07-19; the checker now distinguishes two blocking dirty selected checkouts from seven safe refresh-required clean checkouts and fails closed with structured status, but no pins or dirty nested work were changed. Built/payload/installed hashes remain unaligned |
| `INST-023` | Onboarding and recovery remain usable with keyboard, screen reader, narrow/mobile layout, localization, reduced motion, and high contrast. | Nontechnical users are not excluded by presentation or input mode. | installer/helper/browser dialogs and controls | Accessibility/localization browser and native UI matrix | PARTIAL 2026-07-20; browser scope passes ten-session/fresh-registration handoff stress, keyboard focus/activation, desktop/320/390 settled Axe with zero serious/critical findings, forced colors, zero horizontal overflow, German fallback, reduced motion, provider save/delete fault recovery, Feelings degraded recovery, refresh, and runtime-restart credential persistence. VoiceOver/native helper/Keychain/TCC and Intel remain unrun ([report](reports/2026-07-20-inclusive-easy-install-browser-qa.md)) |
| `INST-024` | Preflight, doctor, build, launchers, helper, packaged runtime, and diagnostics select one supported Node major. | A first install or upgrade does not download two runtimes, build under one runtime, launch under another, or resurrect an obsolete runtime through an optional feature. | preflight/common/doctor, LibreChat and optional launchers, macOS helper, dependency install, client build, packaged runtime | Cross-layer version contract plus clean-install process/path provenance and exact-artifact build/start QA | PARTIAL 2026-07-19; six source surfaces align on Node 24, the full parent suite and helper rebuild pass, and the VM built/started/restarted under Node 24; exact-payload process-path provenance remains unrun |

These are umbrella installer cases. Feature owners retain detailed authority: `INST-005` links to
`qa/continuity-ops/`; `INST-007` incorporates rather than replaces `PIPE-001` under
`qa/installer-piped-bootstrap/`; `INST-010` links to Telegram and MCP/OAuth owners; `INST-008` is the
decisive cross-surface journey and does not replace the platform matrix in `INST-011`. `INST-014`
owns shared-profile parity and consumes rather than duplicates `INST-003`, `INST-007`–`INST-011`,
and `INST-013`.

## Discrete Easy Install Release Gates

These cases are intentionally separate so one broad `PARTIAL` cannot hide a missing release proof.

| Gate | Expected result | Forbidden result | Evidence required | Current status |
| --- | --- | --- | --- | --- |
| `INST-015` signed payload | The one command verifies and activates a notarized immutable payload. | Mutable branch checkout, source build, or package registry resolution is presented as Easy Install. | Signature/notarization/tamper ledger and exact payload digest. | BLOCKED |
| `INST-016` vanilla Mac | No undeclared developer tools are used before first answer. | Dormant or host-installed tools silently make the run pass. | Pristine-image inventory, installer trace, and process/file provenance. | BLOCKED |
| `INST-017` provider lifecycle | One synthetic grant produces an answer that survives refresh/restart; every failure state has a repair action. | OAuth start alone is called a connected account or usable chat. | Browser video/screens, sanitized provider state, answer persistence, API/log confirmation. | PARTIAL |
| `INST-018` restore | Every promised continuity domain is restored into an independent target. | Metadata, source inspection, or DB copy alone is called recoverable. | Before/after browser ledger, manifest hashes/counts, auth re-login truth. | PARTIAL |
| `INST-019` fault matrix | Every interruption retains either the previous healthy version or a resumable journal. | Partial install overwrites the last healthy state. | Stage-by-stage fault ledger and rollback state. | PARTIAL |
| `INST-020` macOS integration | Helper/login/Keychain/Gatekeeper behavior passes on a headed supported Mac. | Source build or universal architecture alone substitutes for user interaction. | Visible native UI, system registration, Keychain and process evidence. | PARTIAL |
| `INST-021` Docker delta | Docker adds only selected adapters; core onboarding remains equivalent. | Docker masks a Native defect or becomes an undeclared prerequisite. | Side-by-side physical-Mac comparison. | BLOCKED |
| `INST-022` delivery alignment | Nested commit, pin, build, payload and installed runtime hashes agree. | A dirty source candidate is treated as the public artifact. | Commit/hash ledger at all five surfaces. | FAIL |
| `INST-023` inclusive UX | All critical steps remain perceivable and operable across the declared matrix. | Pointer-only, English-only, or desktop-width success is generalized. | Accessibility tree, keyboard, viewport and localization ledger. | PARTIAL: browser setup stress, keyboard, desktop/320/390, forced colors, locale fallback, reduced motion, refresh/restart, and injected fault/retry pass; native assistive-technology rows remain open. |
| `INST-024` Node runtime alignment | Every install/build/start/status layer uses the same supported Node major carried by the exact payload. | Preflight passes under one major while startup installs or forces another. | Version-contract test, clean-install PATH/process provenance, production build and restart on the exact artifact. | PARTIAL |

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
- Last run: PARTIAL 2026-07-19. A no-share disposable VM ran the Easy Install source candidate
  through install, rerun, stop/restart, authenticated registration and account handoff, OAuth popup
  cancel/retry, disconnected-provider guidance, Feelings discovery and persistence, missing-secret
  Custom Settings Install rollback, failed-upgrade service recovery, idempotent reinstall,
  preserve-data uninstall, and manual recovery of the tested synthetic state. The tested core installed in 32.15
  seconds and reran in 18.66 seconds. No personal state was used. The exact signed artifact, public
  restore workflow, provider answer, headed helper/Keychain/Gatekeeper path, and wider fault matrix
  remain open.

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
- Last run: PASS 2026-07-19. The dated lifecycle report uses synthetic values and public-safe
  placeholders, and the complete parent release suite passed its QA-template, ownership, and
  public-safety gates with 1,072 passed, 7 environment/opt-in skips, and 0 failures.

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
| Scheduler | Installed | service health, DB ledger count, due item, callback proof, restart | `qa/scheduling-cortex/` |
| GlassHive | Capability installed; worker setup pending in new Easy Install Native | no-worker first-chat pass, Codex-ready, Claude-ready, explicit activation failure, worker profile preservation | `qa/glasshive_host_workers/` |
| Prompt Workbench | Capability installed; schedules deferred in new Easy Install Native | pending state, activation, health, visible schedule, completed run detail, restart | `qa/prompt-workbench/` |
| Nightly reflection | Deferred until worker setup in new Easy Install Native | pending state, activation, scheduled prompt -> filled placeholders -> GlassHive run -> callback -> scheduler ledger -> Workbench shows completed | `qa/prompt-workbench/`, `qa/scheduling-cortex/` |
| Memory hardening | Deferred until provider/worker setup in new Easy Install Native | pending state, activation, dry-run-first, eligible-user count, disabled-memory skip, power/thermal skip, run state | `qa/memory-hardening/` |
| Transcript ingest | Guided | no folder pending, folder set, missing folder, catch-up/manual ingest, privacy scan | `qa/meeting-transcript-memory/` |
| Conversation Recall/RAG | Guided opt-in | skipped by default, Docker/Ollama missing, enabled health, browser recall answer | `qa/conversation-recall-rag/` |
| Web search | Guided | local Docker path, hosted-key path, missing keys, SearXNG degraded, Firecrawl degraded | `qa/web-search/` |
| Groq activation | Optional post-ready provider | skipped/pending, invalid/revoked/quota/network/model rejection, live self-test, xAI fallback, Groq versus Grok wording | `qa/installer-resilience/` |
| Primary AI | Guided required for brain-ready | connected account pending, API-key fallback, post-account connected route | `qa/connected-accounts-handoff/` |
| Secondary/fallback AI | Guided optional | skipped visible state, fallback configured, provider failure wording | `qa/connected-accounts-handoff/` |
| Voice | Post-ready guided capability | local Apple Silicon path, hosted guided path, disabled/setup-pending state, provider auth missing | `qa/modern-playground-voice/` |
| Telegram | Guided | token validation, Keychain-only storage, polling conflict, self-test | `qa/telegram-runtime/` |
| Telegram Codex | Guided separate token | separate token, missing token pending, polling conflict | `qa/telegram-runtime/` |
| Google Workspace MCP | Guided OAuth | pending OAuth, configured endpoint, expired token/action required | `qa/mcp-oauth/` |
| Microsoft 365 MCP | Guided OAuth/Docker | pending OAuth, Docker/prereq missing, endpoint/action required | `qa/mcp-oauth/` |
| WhatsApp | Not available | unavailable wording; no generated config or fake status | `qa/installer-resilience/` |
| Code Interpreter | Off by default | disabled by choice, Custom Settings Install or later configure opt-in only, no public default-on example | `qa/installer-resilience/` until a dedicated owner exists |
| Skyvern | Off by default | disabled by choice, Custom Settings Install or later configure opt-in only, no public default-on example | `qa/installer-resilience/` |
| OpenClaw | Off by default | disabled by choice, Custom Settings Install or later configure opt-in only, no public default-on example | `qa/installer-resilience/` |
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
- Expected result: Easy Install gives the full installed core spine plus honest guided setup for
  user-owned pieces; Custom Settings Install exposes the same registry earlier; upgrades preserve user choices; no
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
  4. Interrupt download and component/bootstrap stages, then rerun.
  5. Compare selected release, component pins, compiled artifacts, helper bundle, and installed
     runtime versions.
- Expected result: unrelated/ambiguous targets fail without mutation; valid targets resume/repair;
  every delivery surface matches a verified immutable release.
- Forbidden result: any `.git` directory is trusted, mutable `main` is release truth, verification is
  skipped, failed downloads execute, or doctor accepts delivery skew as a clean-install pass.
- Evidence to capture: before/after target hashes/status, verified release metadata, journal stages,
  component/pin/artifact comparison, visible error/recovery, and public-safety scan.
- Automation: target-identity, signature/checksum, partial-download, resume, dirty-tree, and artifact-
  alignment tests plus fresh public-entrypoint QA.
- Last run: PARTIAL 2026-07-19. Destination-identity tests reject an unrelated origin, tracked-dirty
  state, and a clean local-ahead commit before CLI execution while accepting the supported SSH
  identity form; signed-manifest/payload reference tests also cover verification, hostile archives,
  immutable activation, journal/lock behavior, and health rollback. The public entrypoint still
  installs mutable source rather than an exact signed/notarized payload, and hostile existing-repo,
  hook-safe staging, interruption/resume, and installed-artifact alignment remain unaccepted.

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
  5. Skip and later add optional Telegram; confirm honest unsupported Slack/WhatsApp states.
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
- Last run: PARTIAL 2026-07-19. An isolated Tart VM passed source-candidate install, rerun, restart,
  synthetic registration/login, Connected Accounts handoff, provider start/cancel/retry,
  disconnected-chat repair wording, Feelings discovery/toggle/refresh/restart persistence, dirty-
  component upgrade refusal with service recovery, idempotent reinstall, full-tree uninstall
  preservation, and manual recovery. A completed provider answer, optional channel, public restore,
  exact signed artifact, and full platform matrix remain open.

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
- Last run: PARTIAL 2026-07-19. The shared install summary now renders configuration-only enabled
  surfaces as `Configured` with a live/self-test action and never as `Ready`; the regression contract
  covers every Brain Setup row. The complete live provider/channel error matrix, last-tested expiry,
  and cross-surface helper parity remain open.

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
  6. Verify Groq API and xAI API/Grok wording; verify unsupported Slack/WhatsApp is not configurable.
- Expected result: user sees privacy/cost/data destination, current capabilities, live state, and a
  specific recovery action; raw secrets exist only in approved secret storage.
- Forbidden result: consumer subscription presented as API entitlement, plaintext secret, embedded
  webview OAuth, overbroad scopes, fake unavailable integration, or disconnect silently retaining/
  deleting credentials.
- Evidence to capture: capability manifest, least-scope grant, live self-test, failure/recovery UI,
  Keychain/reference audit, restart, revoke/delete result, and diagnostics redaction.
- Automation: adapter schema/state/error/redaction tests plus real synthetic account/channel QA.
- Last run: PARTIAL 2026-07-19. The real browser passed registration-to-Connected-Accounts handoff,
  disconnected OpenAI/Anthropic cards, OpenAI authorization start/cancel recovery, and precise
  disconnected-chat guidance. No provider grant, test, expiry, reauth, disconnect, or revoke was
  completed. Telegram clean setup remains unproved; Slack is future Custom Settings Install work;
  official WhatsApp remains unavailable.

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
- Last run: PARTIAL 2026-07-19. A no-share Tart VM ran the real source-candidate installer,
  authenticated browser path, rerun/restart, missing-secret rollback, failed-upgrade service
  recovery, uninstall preservation, and manual recovery of the tested synthetic state. Its base already contains
  dormant developer-tool state, and the wider low-resource, offline/network, interruption, OS,
  architecture, signed helper, Keychain, public restore, accessibility, and physical-Docker matrix
  remains open. The exact real-hardware
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
- Last run: PARTIAL 2026-07-20. In a no-share disposable VM, a real Chromium user passed keyboard
  account-menu navigation to Feelings, provider-free loading, refresh persistence, 320px reflow,
  reduced-motion behavior, injected backend failure plus visible retry, and signed-out redirect.
  Normal 320/390 axe scans had no serious/critical findings. Forced-colors contrast, the separate
  right-control route, actual screen-reader/native UI, parent pin, signed shipped bundle, and
  release-installed artifact remain unproved. See the
  [inclusive browser report](reports/2026-07-20-inclusive-easy-install-browser-qa.md).

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
- Last run: PARTIAL 2026-07-19. Profile-aware wizard/compiler/preflight/native startup and status,
  exact Mongo vendor acquisition, a Node 24 production build, current-attempt failure detection,
  signed-manifest payload reference automation, isolated Tart install/restart/reinstall, synthetic
  local account, Connected Accounts authorization start/cancel/retry, disconnected guidance,
  right-control Feelings, failed-upgrade recovery, Custom Settings Install rollback, uninstall
  preservation, and manual recovery pass. The VM still used a source candidate and a base with
  dormant developer tooling;
  the Node 24 source layers still lack exact-payload process provenance, and no signed public
  payload, completed provider answer, restore, full fault matrix, or physical-Mac Docker delta has
  passed.

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

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Installer Resilience. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `INST-UC-001` | On installer/CLI/helper, generated env, status output, verify that install, preflight, doctor, configure, and generated runtime outputs fail honestly and recover cleanly. | owning requirement for `INST-001` / `INST-001` | installer/CLI/helper, generated env, status output | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-001. | User-visible behavior matches source, docs, persisted state, and logs | PARTIAL 2026-07-19; disposable source-candidate install/rerun/restart, build/dependency recovery, Custom Settings Install rollback, failed-upgrade service recovery, uninstall preservation/manual recovery, OAuth cancel, doctor/compiler, and browser paths ran; exact artifact, public restore, and wider recovery remain open |
| `INST-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | The user sees an honest setup, retry, or degraded-state result for INST-002; no fake success is accepted. | PASS 2026-07-19; full parent QA-template, ownership, and public-safety checks pass |
| `INST-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `INST-002` / `INST-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to INST-002. | INST-002 remains correct after the persistence or parity step and final wording matches evidence. | PASS 2026-07-19; full parent release suite passed after report and owner reconciliation |
| `INST-UC-004` | Run an Easy Install or upgrade-shaped install path and inspect the resulting nightly workflow defaults. | `39_Installer_and_Config_Compiler.md` / `INST-003` | `./install.sh` or `bin/viventium install/upgrade` harness, generated env, preflight, install summary, Workbench synthetic seed | Source, docs, config diff, preflight items, generated env keys, Workbench schedule row, focused release tests, and public-safety scan. | Easy Install reaches first chat without worker authentication; a user can activate the nightly workflow later; existing explicit state survives upgrade; no private identity is hardcoded. | PARTIAL 2026-07-19; public preset/VM core defer worker/nightly surfaces and automation preserves explicit disables; later activation and established-user live upgrade remain open |
| `INST-UC-005` | Run Easy Install and Custom Settings Install simulations, then inspect status/readiness for every brain surface. | `39_Installer_and_Config_Compiler.md` / `INST-004` | `./install.sh` or wizard harness, generated env, `bin/viventium status`, feature-owner QA surfaces | Registry rows, wizard choices, generated env keys, scheduler DB summary, install/status table, feature-owner cases, public-safety scan. | The core spine is installed; guided surfaces clearly say ready/pending/degraded/disabled/not available with next action; no private defaults or fake integrations appear. | PARTIAL 2026-07-19; labels, front-door mapping, minimal preset, and configured-versus-ready truth pass; completed-provider and every feature-owner live journey remain open |
| `INST-UC-006` | Before a risky install/configure/upgrade/reset/uninstall, create and independently restore the promised backup. | `39_Installer_and_Config_Compiler.md` / `INST-005` | Public CLI/helper snapshot, disposable restore, browser, Recall, scheduler, status | Inventory, manifest, logical exports, counts/hashes, browser-visible continuity, logs, versions, public-safety scan | Only a complete independently restored payload is called a recoverable backup; metadata-only audit and reauth-required state are explicit. | PARTIAL 2026-07-19; metadata-only and marker-less restore are refused; positive schema/hash/content structural validation and no-mutation validation-only pass while reporting `recoverable: false`; full-tree uninstall/manual recovery remain supporting evidence. Public complete capture/apply and browser-visible independent restore remain open |
| `INST-UC-007` | Change one setting on an established installation, cancel/retry/fail stages, and confirm all unrelated state survives. | `39_Installer_and_Config_Compiler.md` / `INST-006` | CLI/helper configure, candidate diff, compiler, reload, rollback, restart | Before/candidate/after structural diff, backup, generated output, health, persistence | Configure is transactional, idempotent, secret-redacted, and preserves explicit/unknown user fields. | PARTIAL 2026-07-19; Easy Install reconfigure succeeds and missing-secret Custom Settings Install fails without traceback or canonical drift; interactive helper/crash/wider reload coverage remains open |
| `INST-UC-008` | Run the public bootstrap against empty, valid, unrelated, dirty, offline, corrupt, and interrupted targets. | `39_Installer_and_Config_Compiler.md` / `INST-007` | Public one-command entrypoint, release manifest, component checkout, helper/installed runtime | Target before/after, identity verification, signature/digest, journal, pins/build/install versions | Only verified Viventium targets mutate; exact immutable release installs or resumes safely. | PARTIAL 2026-07-19; wrong-origin, tracked-dirty, and clean local-ahead targets are rejected; reference manifest/signature/archive/rollback automation passes; exact immutable public bootstrap, hostile-repo staging, interruption/resume, and installed-artifact alignment remain open |
| `INST-UC-009` | As a novice on a clean supported Mac, complete one command through first answer, optional channel, Feelings, restart, and restore. | `39_Installer_and_Config_Compiler.md` / `INST-008` | Terminal installer, helper, browser account/provider/chat, Telegram, Feelings, restart/restore | Timestamped UX ledger, visible output/details, logs, DB/state, config, pins/artifacts, persistence, final wording | Minimal truthful choices produce a useful persistent result; every failure/recovery preserves progress. | PARTIAL 2026-07-19; isolated source-candidate install, account handoff, provider start/cancel/retry, disconnected guidance, Feelings, restart/reinstall/failed-upgrade recovery, uninstall preservation, and manual recovery pass; provider answer/channel/public restore/exact artifact remain open |
| `INST-UC-010` | Inspect setup/status before config, after config, after live success, and across each failure class. | `39_Installer_and_Config_Compiler.md` / `INST-009` | Install summary, Brain Setup, CLI status, helper, integration UI | Shared structured state, self-test, visible cards, logs, refresh/restart | Configured is distinct from Ready; exact failure and one repair action agree everywhere. | PARTIAL 2026-07-19; configured-only states no longer claim Ready; live error taxonomy/timestamps and every cross-surface state remain open |
| `INST-UC-011` | Connect/test/reauth/repair/disconnect/revoke/delete each supported provider or channel using synthetic accounts. | `39_Installer_and_Config_Compiler.md` / `INST-010` | Browser connected accounts, Keychain, Telegram, Google, Microsoft, status/diagnostics | Adapter manifest, least scopes, live requests, failure states, secret scan, restart | Secure capability-scoped lifecycle works; unsupported channels remain honest; Groq and xAI/Grok are unambiguous. | PARTIAL 2026-07-19; real Chromium passed automatic Connected Accounts handoff, visible OpenAI/Anthropic disconnected states, OpenAI authorization start/cancel recovery, and exact disconnected-chat repair guidance; grants, live tests, expiry/reauth/disconnect/revoke, Telegram clean setup, and future channels remain open |
| `INST-UC-012` | Exercise every supported platform/prerequisite/resource/network/interruption/recovery combination in isolation. | `39_Installer_and_Config_Compiler.md` / `INST-011` | Disposable macOS matrix, optional Linux subsystem harness, install journal, rollback/uninstall | Environment policy, checkpoints, visible errors, stage ledger, filesystem/services/artifacts | Failures are bounded, specific, resumable, and preserve prior good state. | PARTIAL 2026-07-19; no-share Apple Silicon Tart install/restart/config/upgrade/uninstall recovery lane ran; vanilla base, wider faults, signed helper/Keychain, Intel decision, public restore, and physical Docker remain open |
| `INST-UC-013` | From ordinary chat, discover Feelings in the right control panel and recover signed-out/missing/degraded setup states. | `54_Emotional_Cortex_And_Feeling_State.md` / `INST-012` | Built/installed LibreChat in real browser, side panel, login, connected accounts, Feelings | Browser/a11y evidence, startup config, provider state, persistence, logs/DB, nested pin/artifact | Feelings is discoverable without a URL; guidance preserves place/draft and gives one clear connection action. | PARTIAL 2026-07-19; right-control discovery, nine-band UI, toggle and persistence across refresh/restart/reinstall/manual recovery pass; completed/degraded provider, keyboard/mobile/a11y, pin and signed artifact remain open |
| `INST-UC-014` | Confirm local-only services work on loopback but are unreachable on non-loopback interfaces without remote access. | local privacy contract / `INST-013` | Exact built/installed runtime, socket table, host and second-LAN-machine probes, firewall states | Launcher args, generated config, helper/status, access logs, restart, remote-access mode | Explicit loopback binding is independent of firewall; remote modes expose only their declared authenticated ingress. | PARTIAL 2026-07-19; disposable Easy Install API/web/Mongo/scheduler sockets and non-loopback probes plus localhost-only status wording pass; second-host/firewall/optional-service/remote-mode coverage remains open |
| `INST-UC-015` | Install Easy Install Native without Docker/developer tools, connect one provider, get a persistent first answer, then add an optional capability without reinstalling. | `39_Installer_and_Config_Compiler.md` / `INST-014` | Exact candidate bootstrap/payload in Tart, browser setup/chat, helper/status, restart/restore; later physical-Mac Docker delta | Manifest/digests, journal, visible UI, provider probe, logs/DB/config, process/resource/listener matrix, installed artifact | One shared lifecycle gives a useful Native core and truthful progressive setup; Docker-only state is an isolated capability delta. | PARTIAL 2026-07-19; source-candidate Native core/account/provider-start/Feelings/restart/reinstall/recovery pass; no-developer-tools payload, completed provider answer, optional capability/public restore and Docker delta remain open |
| `INST-UC-016` | Install with no Node present, then build/start/restart and inspect which Node executable actually owns each step. | `39_Installer_and_Config_Compiler.md` / `INST-024` | Clean Native installer/payload, preflight, doctor, launcher, process table, status | Version contract, installed formulas/files, resolved PATH/executable, process environment, build/start logs, artifact digest | One supported pinned Node runtime owns every stage; no second major is downloaded or silently forced. | PARTIAL 2026-07-19; source contract, full parent suite, helper rebuild, and VM Node 24 production build/start/restart pass, while exact-payload process provenance remains unrun |

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
- `tests/release/test_native_payload.py`
- `tests/release/test_prompt_workbench.py`
- `tests/release/test_public_bootstrap_manifests.py`
- `tests/release/test_playground_loopback_contract.py`
- `tests/release/test_qa_operating_contract.py`
- `tests/release/test_qa_results_public_safety.py`
- `tests/release/test_shell_init.py`
- `tests/release/test_wizard.py`
