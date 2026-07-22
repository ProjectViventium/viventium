# Easy Install And Onboarding Remediation Plan

Status: **PARTIAL.** Execution is in progress and release gates remain open.\
Audit baseline: 2026-07-18\
Delivery rule: local changes only until explicitly authorized; nested repositories, parent pins,
compiled artifacts, installed artifacts, and cloud publication remain separate approval gates.

## Goal

A nontechnical user can run one supported command on a clean Mac, understand the small number of
real prerequisites, obtain a useful and private local Viventium experience, connect preferred
accounts or channels when needed, discover Feelings, and recover from interruption without losing
data. An existing user can configure, upgrade, repair, and roll back with zero unintended drift.

## Current Execution Status — Updated 2026-07-21

This is the ordered action plan and current stop/go state. `PARTIAL` means source work or supporting
automation exists but the user-grade or shipped-artifact gate is still open.

| Order | Slice | Status | Completed evidence | Next release gate |
| --- | --- | --- | --- | --- |
| 0 | Freeze claims and establish contract | PASS | lifecycle inventory, evidence-backed audit, open-source research, case matrix | keep claims synchronized with later proof |
| 0.5 | Immediate truth and mutation safety | PARTIAL | metadata-only capture truth plus fail-closed restore selection, headless config transaction, existing-origin refusal, loopback source bind, truthful Easy Install copy | installed/live and interactive-path proof |
| 1 | Full-payload backup and restore | PARTIAL | a pristine no-tools VM created a complete provisional-payload backup, restored it to an independent target, recovered the synthetic browser user, and preserved Connected Accounts/Feelings across refresh and full restart | replacement exact artifact, helper interaction, provider/channel reconnect, Recall rebuild, and the remaining promised continuity domains |
| 2 | Transactional reconfigure | PARTIAL | headless merge/validate/atomic apply/rollback tests | interactive/helper, staged Keychain commit, derived-output/process compensation, cancel/crash/reload/restart parity |
| 3 | Verified bootstrap and install journal | PARTIAL | wrong origin, dirty tracked tree, and clean local-ahead revision are rejected; signed manifest/payload verification, immutable activation, journal, schema gate, and health rollback have reference automation | integrate the verified payload into a signed public bootstrap and prove resume/rollback on the installed artifact |
| 4 | Minimal account-first Easy Install journey | PARTIAL | disposable source-candidate VM reaches healthy loopback API/web, local registration, automatic Connected Accounts, and persistent useful answers through headed OpenAI, Anthropic, Groq, and Grok lifecycles with repair, Disconnect, and re-add | exact signed packaged candidate and one uninterrupted novice run from public command through first answer |
| 5 | Unified setup and connection health | PARTIAL | configured-versus-ready wording and provider-specific invalid/quota/outage/network browser states pass in scoped source-candidate lanes | one shared cross-surface state model, current self-test timestamps, remaining providers/channels, and installed-artifact proof |
| 6 | Feelings flagship discovery | PARTIAL | account-menu keyboard discovery, startup gate, focused tests, Node 24 production build, provider-free load, refresh/restart persistence, narrow/reduced-motion behavior, and local source-to-pin alignment | ordinary-chat right-control user path, operator-disabled/degraded setup, stopped-helper continuation, signed shipped/installed artifact, and native assistive technology |
| 7 | Telegram first-class onboarding | BLOCKED | research and lifecycle cases documented | synthetic connect/test/retry/revoke journey |
| 8 | Slack and WhatsApp boundaries | BLOCKED | staged product boundary documented | adapter decisions, scopes, lifecycle UX, synthetic acceptance |
| 9 | Clean and existing-user acceptance | PARTIAL | isolated source-candidate/provider lanes and provisional-payload independent restore ran with synthetic state; the first pristine payload exposed four blocking defects whose source regressions now pass | rebuilt signed no-developer-tools payload, one full pristine lifecycle, existing-user parity, wider fault/accessibility, helper/Keychain/Gatekeeper, exact delivery alignment, and physical Docker Mac |
| 10 | Runtime toolchain alignment | PARTIAL | failing contracts reproduced the Node 20/24 split across the main launcher and then the optional Skyvern/helper surfaces; six source layers now align on Node 24; 90 focused tests, both shell syntax checks, and helper build pass | prove exact-artifact clean install, build/start/restart, and PATH/process provenance |

### Approved Easy Install Architecture — 2026-07-18

The user approved implementation of the following product contract:

- one shared installer/onboarding/readiness/rollback state machine;
- `Easy Install Native` as a real useful non-Docker product and disposable-VM acceptance lane;
- `Easy Install Docker` as the same flow plus container-backed capability adapters;
- no Docker, Homebrew, Git, Xcode, pnpm, uv, Python, or system Node prerequisite before the Native
  first answer in the final packaged path;
- account-first browser setup with a live provider request, followed by optional progressive setup;
- physical MacBook Air QA only after the Native VM lane has closed the installer/onboarding core;
- local-only implementation and QA until separate cloud/publication approval.

The normative detail lives in
`docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md` under “Easy Install Native And
Easy Install Docker Product Contract.” The old decision table below is retained as audit lineage; the
items resolved by this approved contract are no longer open.

No activation, restart, account mutation, DB mutation, or cloud publication is part of this
checkpoint. However, the current local-prod frontend is a Vite source server watching the shared
checkout, and read-only inspection confirms it already serves the modified Feelings hook. Further
UI work must use a disposable worktree/dev runtime so source edits cannot drift the established
user-facing process even without a restart.

## Immediate Action Queue From This Checkpoint

1. Promote the successful Tart source-candidate lane to a truly vanilla Apple Silicon image and the
   exact signed Native payload; keep personal state out of every destructive test.
2. Finish Slice 1 from the successful provisional independent restore through provider/channel
   reconnect, Recall rebuild, helper interaction, every remaining promised continuity domain, and a
   rerun on the replacement exact artifact.
3. Finish Slice 2 across interactive/helper entrypoints, staged Keychain writes, generated outputs,
   schedules, helper state, processes, crash recovery, and rollback.
4. Close Slice 3 and the full `INST-013` network contract: hook-safe immutable bootstrap, journal and
   resume, fail-closed loopback defaults, wildcard-listener rejection, truthful endpoint banners,
   and behavioral socket/LAN denial tests.
5. Finish Slices 4–5 by carrying the proven source-candidate provider lifecycle onto the exact signed
   artifact and implementing one shared configured/ready/degraded/repair state model across setup,
   status, helper, and provider/channel surfaces.
6. Complete Feelings in delivery order: reviewed-tree-to-merged-pin identity now agrees, so the next
   gates are rebuilt client/payload, installed artifact, authenticated ordinary-chat right-control
   QA, and stopped-helper continuation.
7. Complete Telegram lifecycle QA, then treat Slack and WhatsApp as separately approved adapters;
   do not let roadmap channels block the secure core Easy Install path.
8. Close the discrete `INST-015`–`INST-024` release gates. In particular, do not confuse proven
   merged source-to-pin agreement with a signed installed payload.
9. Finish `INST-024` under the exact packaged runtime. Six source surfaces now align on Node 24 and a
   contract test prevents the Node 20/24 split from recurring; clean-install build/start/restart and
   PATH/process provenance are still required before runtime acceptance.

## Definition Of Done

The implementation is not complete until the exact shipped artifact passes:

`verified command → read-only preflight → recovery checkpoint → install journal → exact pins → live health → first local account → provider test → first useful answer → optional channel → Feelings discovery → refresh/restart → full restore`

Both paths must independently meet Quality + Performance:

- fresh clean supported macOS target with synthetic accounts/data;
- existing-user continuity from a disposable restored clone of state.

Source, mocks, logs, DB rows, tests, mature-runtime success, and model review support this result but
cannot replace either user path.

## Decisions Required Before Coding

Resolution: the Easy Install architecture, Groq role, GlassHive deferral, progressive web-search setup,
immutable bootstrap direction, and full-versus-metadata backup truth were approved on 2026-07-18.
Intel support, public signing identity, MongoDB redistribution, and hosted Slack/WhatsApp product
boundaries remain explicit release decisions and do not block the local Native VM implementation.

| Decision | Recommended default | Why it matters |
| --- | --- | --- |
| Easy Install primary model | Useful local default when viable; otherwise browser-connected OpenAI/Anthropic choice | Determines whether a developer API key is truly mandatory. |
| Groq role | Optional or clearly disclosed activation provider with live self-test and fallback | Current mandatory hidden gate is brittle. |
| GlassHive role | Install core, defer activation until Codex/Claude auth unless parity requires blocking | Avoids terminal auth becoming a surprise after “Easy.” |
| Web search | Off until first-use prompt or auto-local only after explicit privacy/resource consent | Current docs conflict. |
| Intel support | Publish exact supported matrix or retire Intel | A release gate cannot remain conditional/undefined. |
| WhatsApp | `unsupported` until official Business Cloud boundary exists | Prevents unsafe consumer-library shortcuts. |
| Slack | Custom Settings Install with Socket Mode first | Works locally but is not one-click without a hosted public app. |
| Bootstrap trust | Signed/versioned bootstrap plus exact manifest pins | Mutable `main` is not a secure release boundary. |
| Backup scope | Full payload and independently restorable, or explicitly “metadata audit only” | Prevents false recovery assurances. |

## Slice 0 — Freeze Claims And Establish The Contract (S)

Deliverables:

- Mark current Easy Install release status `PARTIAL` in release-facing acceptance wording.
- Reconcile current normative behavior across installer docs; move dated history below the current
  contract.
- Reconcile metadata-audit versus recoverable-snapshot truth across
  `39_Installer_and_Config_Compiler.md`, `qa/continuity-ops/`, the snapshot implementation, helper
  wording, and `test_continuity_audit.py`; today they intentionally permit the unsafe ambiguity.
- Fix missing QA-owner links in readiness/QA maps.
- Declare umbrella versus feature-owner responsibility for overlapping installer, continuity,
  piped-bootstrap, Telegram/MCP, and clean-Mac cases.
- Publish one supported macOS/architecture/resource matrix.
- Adopt the shared connection state vocabulary from the research document.

Acceptance:

- No release artifact or helper says “Ready,” “Backup created,” “one command,” or “only asks…” unless
  the corresponding live evidence exists.
- `qa/installer-resilience/cases.md` is the umbrella matrix and links every feature owner.
- Release tests enforce that all referenced QA owner paths exist.

Dependencies: product decisions above.\
Risk: low implementation risk; high wording/release-value impact.

## Slice 0.5 — Same-Week Truth And Mutation-Safety Patches (S)

Ship narrow, independently reviewable fixes before the larger architecture work:

- make helper/CLI wording distinguish a metadata audit from a recoverable snapshot;
- stop metadata fallback from rewriting the latest snapshot manifest in place;
- replace the inaccurate Easy-profile promise with the real prerequisite chain;
- validate the existing destination's Viventium origin before any git mutation;
- bind the modern playground explicitly to loopback in local mode;
- stop `--config-input` from bypassing candidate validation, backup, and atomic replacement.

Acceptance:

- wording cannot imply payload recoverability when only metadata exists;
- repeated fallback attempts never alter a prior snapshot directory or manifest;
- an unrelated repository at the default destination is byte-for-byte unchanged;
- local mode has no wildcard listener and a non-loopback probe fails without relying on a firewall;
- a failed headless configure leaves canonical config and generated outputs unchanged.

Dependencies: Slice 0 claim/contract decisions.\
Risk: medium; these are small surfaces with high safety value.

## Slice 1 — Truthful Full-Payload Backup And Restore (M)

Owning path:

`helper/CLI trigger → snapshot planner → quiesce or logical export → encrypted payload → manifest → independent verification → restore planner → disposable restore → visible continuity`

Requirements:

- Distinguish `metadata audit` from `recoverable snapshot` in API, CLI, helper, logs, and UX.
- Detect or fail closed on legacy marker-less metadata attempts using manifest/payload evidence;
  never assume an old directory is recoverable merely because it lacks the new marker.
- Allocate a new immutable snapshot-attempt directory before writing any manifest; never discover
  the latest snapshot and rewrite it as a fallback target.
- Inventory chat history, saved memory, Recall/RAG corpus, schedules/background tasks, auth/provider
  references, Telegram mapping/config, helper/runtime selection, and component versions.
- Use explicit private output directories; fail if resolved inside a public source tree.
- Quiesce safely or use supported logical exports; never copy live database files blindly.
- Encrypt the payload or store it in an access-restricted local target with a clear threat model.
- Record schema/version, counts, sanitized hashes, completion status, and warnings.
- Restore into a disposable target before the snapshot is called verified.
- Make Keychain-backed accounts explicitly reauth-required when secret export is intentionally not
  supported.

Acceptance:

- Metadata-only fallback cannot produce success wording for a payload backup.
- Interrupted snapshot leaves the prior verified snapshot intact.
- Restore proves browser-visible chats/memory, Recall result, schedule state, and honest auth status.
- Helper, CLI, logs, and manifest report the same state.
- Search/database dump paths are never inside source by default.

Tests:

- empty install, mature synthetic install, DB unavailable, low disk, permission denied, interrupted
  export, repeated metadata fallback after a real snapshot, checksum mismatch, version mismatch,
  partial payload, restore retry, reauth-required, uninstall-preserve, explicit delete.

Dependencies: disposable state fixture and macOS VM.\
Risk: high; must land before any destructive host QA.

## Slice 2 — Transactional Configure/Reconfigure (M)

Owning path:

`existing config → parse/migrate → candidate copy → guided edits → structural diff → validate/compile → backup → atomic swap → reload → health check → rollback`

Requirements:

- Load and preserve existing user-managed and unknown forward-compatible fields.
- Never write wizard output directly to canonical config.
- Reuse the existing backup + temporary-file + `os.replace` pattern in
  `scripts/viventium/config_settings.py` instead of inventing a second write primitive.
- Present a public-safe semantic diff before applying.
- Validate schema, component prerequisites, compiler output, and secret references on the candidate.
- Create a verified recovery point before replacement.
- Atomically swap only after all preconditions pass.
- Roll back config and generated outputs if reload/health fails.
- Stage Keychain writes until validation succeeds; journal prior secret presence/value locally and
  compensate on failure without logging or persisting raw values in public artifacts.
- Compensate schedules, helper state, generated runtime files, and partially started processes;
  restoring canonical YAML while those side effects remain changed is not a transaction.
- Apply identical safety to interactive configure, recovery reconfigure, headless config input,
  upgrade reconciliation, and helper UI.

Acceptance:

- Idempotent no-op configure produces no drift.
- Explicit disables, agent/user fields, schedules, providers, channels, memory settings, and unknown
  fields survive unrelated edits.
- Cancel, terminal close, crash, and compiler failure keep the canonical config unchanged.
- Candidate diff contains no secret values.

Dependencies: Slice 1 recovery semantics.\
Risk: high because configuration fans out into all runtime surfaces.

## Slice 3 — Verified Bootstrap And Install Journal (M)

Owning path:

`one command → bootstrap identity/version → destination validation → read-only preflight → journal → verified artifacts/pins → stage execution → rollback/resume`

Immediate requirements:

- Validate existing destination origin/manifest before any git mutation.
- Reject tracked changes before mutation and refuse to execute unless post-fetch local `HEAD`
  exactly equals `refs/remotes/origin/<branch>`.

Planned release-provenance scope:

- Use a versioned bootstrap and exact release manifest, not mutable `main`.
- Verify checksum/signature/provenance and retain SBOM/digest metadata.
- Define stable stage IDs and a durable local journal with sanitized errors and resume metadata.
- Put all system/package/helper mutations after explicit preflight and snapshot boundaries.
- Make cancel/retry semantics visible per stage.
- Keep logs detailed but collapsed by default; show elapsed and measurable download progress.

Acceptance:

- Unrelated repository at the default path is never mutated.
- Corrupt/missing signature or partial artifact fails before execution.
- Repeated command resumes or repairs without deleting good state.
- Offline, DNS, proxy/TLS, registry rate limit, and interrupted download are distinguished.
- Pinned component, compiled artifact, and installed artifact versions agree.

Dependencies: destination validation can land immediately; signing/provenance needs its release
boundary decision.\
Risk: medium-high; affects public entrypoint and upgrade.

## Slice 4 — Minimal Account-First Easy Install Journey (M)

Owning path:

`profile choice → prerequisites disclosure → minimal install → browser first admin → provider choice → OAuth/key flow → live test → first answer → optional setup`

Requirements:

- Replace misleading Easy copy with the complete prerequisite story and time/resource estimate.
- Ask only decisions required to reach the first useful result.
- Move optional search, Recall, transcripts, remote access, extra channels, and advanced providers to
  progressive browser setup or first-use activation.
- Clearly distinguish Groq API, xAI API/Grok, OpenAI, Anthropic, and local models.
- Store keys in Keychain; use system-browser OAuth with PKCE where supported.
- Run a real provider/model request before `ready`.
- Preserve the user's first draft while connection completes or fails.
- Finish with a synthetic first conversation and visible success based on the rendered answer.

Acceptance:

- No terminal/browser context-switch is surprising or undisclosed.
- Missing/denied/invalid/expired/quota/network states have one clear recovery action.
- A user can defer every optional integration without a dead end.
- First answer, refresh, service restart, and machine restart are proven.
- Data destination, cost, privacy, and local alternative are visible before connection.

Dependencies: shared connection state machine, product choice for default primary model.\
Risk: medium; broad UX impact.

## Slice 5 — Unified Setup And Connection Health (M)

Requirements:

- One adapter manifest per provider/channel: capabilities, auth method, scopes, data destinations,
  secret references, self-test, health state, migrations, disconnect/revoke.
- One state model across installer, Brain Setup, status, helper, and feature UI.
- A persistent Setup/Connections badge shows only actionable state.
- `Configured` is never rendered as `Ready`.
- Provider failures preserve user work and offer retry/fallback.

Acceptance:

- 401, 403, 429, network unavailable, dependency unhealthy, missing scope, unsupported, and update
  required are distinguishable in UI, structured status, and logs.
- Disconnect and local secret deletion are separate; revoke is offered where supported.
- Diagnostics are redacted and export no personal paths, IDs, prompts, or content.

Dependencies: Slice 4 browser shell.\
Risk: medium.

## Slice 6 — Feelings Flagship Discovery (S)

Owning nested repository: LibreChat. Parent pin and any built/installed artifact must be updated only
after the nested change is independently committed, reviewed, and accepted.

Requirements:

- Update `54_Emotional_Cortex_And_Feeling_State.md` first so the control-panel route becomes
  normative product truth rather than an undocumented implementation addition.
- Add Feelings to the right-side control panel near Agent Builder, Prompt Templates, and MCP Builder.
- Preserve the existing account-menu entry as a secondary route.
- Implement the entry as `onClick → navigate('/feelings')`, following the existing Hide Panel
  navigation precedent; it is not an embedded side-panel experience.
- Gate it with `startupConfig.viventiumFeelingsAvailable !== false`, matching the current default-on
  availability contract; do not branch on visible names or prompt text.
- Wrap all LibreChat fork changes with `VIVENTIUM START` / `VIVENTIUM END`, and repair the
  pre-existing unwrapped Feelings additions in Account Settings and routes within the same reviewed
  nested change.
- If signed out, preserve a return target.
- If provider/setup is missing, explain the missing item, data destination, one recommended Connect
  action, local alternative, and preserve the current draft/state.
- Match keyboard, tooltip, active state, narrow layout, reduced motion, and feature-disabled behavior.

Acceptance:

- Ordinary signed-in chat → control panel → Feelings works without direct URL knowledge.
- Signed-out direct and control-panel attempts route to login and return correctly.
- Disabled feature hides the entry consistently.
- Missing/degraded provider produces guidance, not an empty page or generic error.
- Refresh, back-to-chat, keyboard navigation, mobile/narrow layout, and two-tab state are tested.
- Browser-visible result agrees with startup config, logs, and persisted Feelings state.

Dependencies: product copy/design approval; a clean worktree from the configured delivery pin. The
target navigation files were clean during the audit, while adjacent Feelings feature files were
dirty, so current workspace state cannot be release evidence.\
Risk: low-medium.

## Slice 7 — Telegram First-Class Onboarding (M)

Requirements:

- Numbered BotFather guidance with optional QR/deep link.
- Hidden token written directly to Keychain.
- `getMe` validation, polling/webhook conflict detection, allowlist/pairing, groups/inline off.
- Synthetic send/receive test, restart proof, disconnect and revoke/delete semantics.
- Plain separation between main Telegram bot and Telegram Codex bot.

Acceptance:

- Valid, invalid, revoked, duplicate/polling-conflict, unreachable, and permission cases have distinct
  outcomes.
- No token appears in browser storage, config, generated reports, logs, or diagnostics.
- Fresh Easy journey can skip Telegram cleanly and add it later without reconfigure drift.

Dependencies: Slices 2 and 5.\
Risk: medium due to live external account behavior.

## Slice 8 — Slack And WhatsApp Product Boundaries (S for design; L for shipping)

Slack proposal:

- Custom Settings Install Socket Mode adapter first.
- App-level token, bot OAuth, granular scopes, live self-test, missing-scope recovery, disconnect/revoke.
- Do not call it one-click until a hosted public-app OAuth boundary exists.

WhatsApp proposal:

- Keep `unsupported` until official WhatsApp Business Cloud onboarding, hosted webhook ingress,
  business/app prerequisites, consent, retention, and real QA exist.
- Never support unofficial consumer-account automation as the public product path.

Acceptance before either is advertised:

- Adapter manifest, threat model, data-routing disclosure, installer/setup UI, live self-test, health
  states, disconnect/revoke, logs, persistence, docs, and owning QA all exist.

Dependencies: hosted-boundary/legal/security decisions.\
Risk: high and intentionally outside the initial Easy Install repair.

## Slice 9 — Complete Clean And Existing-User Acceptance (L)

### Test environments

- Disposable Apple Silicon macOS VM/sacrificial Mac with no writable host mounts and synthetic
  accounts/data.
- Begin VM procurement on day one in parallel with Slice 0. Apple Virtualization.framework is the
  preferred host boundary. Docker inside the macOS guest additionally needs supported nested
  virtualization, and microphone/WebRTC proof may still require a physical sacrificial Mac.
- Intel Mac only if still supported.
- Disposable restored clone of an established-user fixture.
- Optional named Colima profile for lower-level container isolation; never counted as macOS
  installer acceptance.

### Required matrix

- prerequisites absent/present/stopped/unhealthy;
- low disk/RAM, port conflict, permissions, disabled virtualization;
- offline/DNS/proxy/TLS/rate-limit/download interruption/checksum/signature;
- cancel/quit/crash/reboot at every journal stage;
- rerun/repair/update/migration/rollback/downgrade;
- account auth denial/wrong account/expiry/scope/quota/network;
- provider fallback and no-provider honest state;
- Telegram happy/error/conflict/restart;
- Google/Microsoft least-scope OAuth and reauth;
- Feelings discovery/disabled/missing-provider/degraded/reload/two-tab/a11y;
- full payload backup/restore and uninstall preserve/delete;
- telemetry consent/zero-network when opted out;
- visible UI, detail state, persistence, logs, DB/state, generated config, pins, installed artifacts,
  and final wording agreement.
- Gatekeeper/notarization/quarantine and first-launch permission prompts;
- forgotten local password with no SMTP recovery, second local user, and multiple local accounts;
- cross-machine restore and schema downgrade/forward-migration refusal;
- Safari/default-browser handoff, non-English macOS, terminal accessibility, and reduced motion;
- laptop sleep during install, concurrent double-install locking, and upgrade while a schedule runs;
- day-two disk exhaustion, MDM/no-admin restrictions, and recurring QA report generation safety.
- explicit loopback bind versus second-machine LAN probes with firewall on/off and remote-access
  modes enabled/disabled.

Acceptance:

- Every applicable case is `PASS`; unsupported cases are explicitly `N/A` with a published policy.
- No `PARTIAL` or `BLOCKED` case is hidden by a release-summary claim.
- Fresh clone/install is performed in a new directory from the public entrypoint.
- Public-safety scan passes on staged docs/reports/artifacts and git identity is approved before any
  later public commit/push.

Dependencies: all prior slices.\
Risk: high execution cost; mandatory release gate.

## Recommended Order

1. Freeze the approved shared-profile contract in the owning requirement and QA cases.
2. Establish a no-host-mount disposable Tart VM and capture a current-source Native baseline.
3. Implement the minimal Easy Install Native config/profile vertically: no terminal provider secret,
   optional capabilities deferred, and core readiness independent of worker/voice/Docker state.
4. Implement the prebuilt native payload and exact manifest boundary. Keep signing/notarization as
   a truthful public-release gate when local credentials/publication are not authorized.
5. Finish journaled install, recovery checkpoint, transactional activation, rollback, repair, and
   preserve-data uninstall/restore around that payload.
6. Build Slices 4–5 as one account-first browser journey with live provider probes and shared
   connection state.
7. Run the complete Native VM matrix continuously as each vertical slice becomes available.
8. Close Feelings discovery and other required core UI against the exact nested pin/build/artifact.
9. After Native acceptance, run the same state machine plus Docker/hardware capability delta on the
   disposable MacBook Air.
10. Telegram and later channels remain post-ready adapters; Slack/WhatsApp remain separately
    approved hosted-boundary work.

This order puts data safety and truthful failure semantics ahead of new convenience surfaces. It
also creates reusable foundations—transaction journal, adapter health, and browser setup—so later
channels do not become one-off flows.

## Implementation Workflow Per Slice

For each slice:

1. confirm requirement and decisions;
2. trace trigger → config/compiler → runtime → visible output;
3. add/update cases first;
4. implement one vertical slice;
5. run focused automation;
6. run real user-grade QA in the appropriate disposable environment;
7. inspect logs, DB/state, generated/shipped/installed artifacts;
8. perform an independent QA pass;
9. obtain Claude/Fable review-only challenge after the evidence-backed proposal/change exists;
10. update the owning requirement and dated public-safe report;
11. verify nested commit, parent pin, and built/installed artifact alignment;
12. stop for explicit approval before any cloud push, PR, account mutation, or public release.
