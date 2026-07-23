# Installer And New-User Lifecycle Inventory — 2026-07-18

## Purpose And Method

This is the reproducible, public-safe history inventory for the installer, configuration compiler,
runtime handoff, continuity, helper, and new-user delivery boundary. It distinguishes four things
that must never be collapsed into one claim:

1. parent source history;
2. nested component history;
3. component versions pinned for a fresh public install;
4. the current established development/runtime state.

The original parent-history snapshot spans 2026-04-02 through 2026-07-19. At
2026-07-19 18:39:51 -0400, `git rev-list --count --all` returned 223 parent commits and the
path-filtered installer/delivery query below identified 118 commits that touched an audited
installer surface. A 2026-07-21 candidate recheck reports 226 locally available parent commits and
121 matching the same path filter. The three additional local candidate commits are intentionally
not treated as shipped history: their changes must be recommitted from a clean public base after
privacy, author-identity, nested-pin, artifact, and QA review.

```bash
git log --all --reverse --date=short --pretty=format:'%ad|%h|%s' -- \
  install.sh bin/viventium scripts/viventium apps/macos/ViventiumHelper \
  config.schema.yaml config.minimal.example.yaml components.lock.json \
  qa/installer-resilience qa/installer-piped-bootstrap qa/installer-wait-taglines \
  docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md \
  docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md \
  docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md \
  docs/requirements_and_learnings/50_Stable_Dev_Runtime.md
```

Nested histories are inventoried by their Viventium-owned commits and configured manifest pins, not
by raw keyword counts across upstream histories. That avoids treating unrelated upstream commits as
Viventium installer work.

## Lifecycle Phases

| Phase | Dates | Outcome added | Representative commits |
| --- | --- | --- | --- |
| Public bootstrap | Apr 2–7 | Installer, CLI, wizard, compiler, preflight, doctor, helper, wait copy, directory and remote-access scaffolding | `60127a8`, `8d14db8`, `1ad8c9e`, `51febe7` |
| First-run resilience | Apr 7–12 | Recovery, Recall install, readiness contracts, local search repair, voice defaults, public-safe QA | `2c64267`, `b26bc44`, `cae2dc4`, `66bf1fd` |
| Piped/fresh/startup hardening | Apr 13 | Freshness guards, piped input fallback and verification, runtime readiness, detached startup ownership | `26b220f`, `19074f0`, `e6fb1d5`, `26251bd`, `8d39393`, `fec91eb` |
| Upgrade and continuity | Apr 14–20 | Stale bundle rebuilds, dirty component reporting, backup/restore, continuity audits, recovery | `b0c092b`, `0ea3353`, `1a97f27`, `0cd31b7` |
| Runtime and cognitive features | Apr 21–May 12 | Scheduling, memory hardening, GlassHive callbacks, Telegram startup, voice/xAI, prompt and transcript work | `fcf730d`, `a5b9a6a`, `1dc0ea3`, `eee85fd`, `a39028b`, `7f82ee9` |
| Stable runtime and public QA | May 14–29 | Active-checkout runtime model, GlassHive workflow controls, QA operating contract, public release synchronization | `cea7cff`, `56d5c04`, `8c427b0`, `dd05126` |
| Early Easy Install cognitive spine | Jun 6–23 | Initial Brain Readiness, preserved explicit nightly disables, default GlassHive for presets, repeated pin hardening | `87ecc8c`, `ffc8d76`, `aba876c`, `2e46432` |
| Emotional-state release | Jul 9–19 | Feelings/emotional state, Telegram/GlassHive QA updates, public component repins, and native Feelings navigation/parity truth | `c68b464`, `b02005b`, `7312bba`, `5adc99c` |

## Parent Installer/Delivery Commit Ledger

Every locally available path-matching parent commit is listed here in chronological order.

| Date | Commit | Recorded outcome |
| --- | --- | --- |
| 2026-04-02 | `60127a8` | Initial public-safe snapshot |
| 2026-04-02 | `8d5b991` | Refresh public component pins |
| 2026-04-02 | `5099872` | Add Telegram media processing infrastructure and QA framework |
| 2026-04-02 | `8d14db8` | Polish installer wait taglines |
| 2026-04-04 | `dcabc27` | Add private-mesh remote access support |
| 2026-04-05 | `671b666` | Compile runtime memory defaults and remote access updates |
| 2026-04-05 | `1ad8c9e` | Add Viventium directory link registration flow |
| 2026-04-06 | `51febe7` | Harden directory registration QA and CLI |
| 2026-04-06 | `eee8cd9` | Clarify remote access guidance and public QA evidence |
| 2026-04-06 | `7ffd95e` | Renew leased public edge router mappings |
| 2026-04-07 | `dfd5bac` | Simplify remote access setup and public auth posture |
| 2026-04-07 | `5deda13` | Save Telegram runtime parity and live QA progress |
| 2026-04-07 | `5d83ce1` | Add managed local Telegram Bot API scaffolding |
| 2026-04-07 | `2c64267` | Improve installer resilience and first-run startup recovery |
| 2026-04-08 | `55a7b78` | Fail closed on remote-access helper exit and tighten public QA |
| 2026-04-10 | `b26bc44` | Harden Recall install and memory continuity |
| 2026-04-10 | `c49d8d0` | Archive MLX endpoint benchmarks and compiler path |
| 2026-04-12 | `958b9a6` | Harden publish-safe activation review |
| 2026-04-12 | `cae2dc4` | Harden install readiness and public QA contracts |
| 2026-04-12 | `3df43b7` | Restore local web search and launcher resilience |
| 2026-04-12 | `34ae209` | Codify voice install defaults and publish-safe QA |
| 2026-04-12 | `66bf1fd` | Package Recall continuity/install readiness/activation hardening |
| 2026-04-12 | `92db897` | Merge Telegram review work with public main |
| 2026-04-12 | `051dd4d` | Package local Telegram Bot API support |
| 2026-04-13 | `26b220f` | Harden clean-install runtime and public-safe docs |
| 2026-04-13 | `19074f0` | Fix installer freshness and continuity release guards |
| 2026-04-13 | `e6fb1d5` | Fix piped installer prompt fallback |
| 2026-04-13 | `26251bd` | Document published piped install verification |
| 2026-04-13 | `8d39393` | Fix runtime readiness and startup recovery |
| 2026-04-13 | `fec91eb` | Fix detached startup ownership and watchdog timing |
| 2026-04-14 | `46f344b` | Fix Codex memory continuity contract |
| 2026-04-14 | `b0c092b` | Rebuild stale LibreChat package bundles on upgrade |
| 2026-04-14 | `8e751db` | Bump LibreChat memory writer fix |
| 2026-04-14 | `7e3cf2b` | Correct LibreChat memory pin |
| 2026-04-14 | `6f9bc9b` | Fix connected-account memory continuity |
| 2026-04-14 | `0ea3353` | Fix dirty component upgrade-drift reporting |
| 2026-04-14 | `1c4bc62` | Fix LibreChat component pin for memory upgrade |
| 2026-04-14 | `1a97f27` | Add continuity-aware backup, restore, and release guardrails |
| 2026-04-14 | `a27fef6` | Ship modern playground public voice launch fixes |
| 2026-04-16 | `ddb366d` | Document Telegram attachment parity and pin LibreChat fix |
| 2026-04-20 | `ed1d2e2` | Merge public recovery review work |
| 2026-04-20 | `0cd31b7` | Recover installer, continuity, and QA work for review |
| 2026-04-20 | `00e06f4` | Update component refs for published releases |
| 2026-04-21 | `d08f3c6` | Pin LibreChat and ship voice memory hardening |
| 2026-04-24 | `8169095` | Fix scheduled Telegram fallback delivery |
| 2026-04-25 | `061b4c4` | Enforce scheduled live-fact truthfulness |
| 2026-04-25 | `9fa9e86` | Repair agent tool preservation for web search |
| 2026-04-25 | `fcf730d` | Add memory-hardening operator workflow |
| 2026-04-25 | `a4312d0` | Pin scheduler misfire catch-up fix |
| 2026-04-25 | `38f74fc` | Finalize memory-hardening scheduling |
| 2026-04-26 | `a5b9a6a` | Harden native prerequisite drift checks |
| 2026-04-28 | `a6c38d9` | Harden voice calls and Cartesia Sonic 3 |
| 2026-04-28 | `f383dce` | Document and pin voice fallback model support |
| 2026-04-29 | `1d571ae` | Wire GlassHive host-worker delivery |
| 2026-04-29 | `48e8cc1` | Fail closed on GlassHive callback preflight |
| 2026-04-29 | `3b8ac60` | Record GlassHive host-worker callback contract |
| 2026-04-30 | `1dc0ea3` | Wire GlassHive callback delivery across surfaces |
| 2026-04-30 | `dfcddec` | Capture GlassHive callback UX requirements |
| 2026-04-30 | `eee85fd` | Harden Telegram bridge runtime startup |
| 2026-05-04 | `a39028b` | Harden voice runtime and installer resilience |
| 2026-05-06 | `7f82ee9` | Synchronize local public release state |
| 2026-05-07 | `1b81d25` | Add xAI voice route and continuity hardening |
| 2026-05-12 | `92ac68e` | Add prompt-architecture QA and component pins |
| 2026-05-12 | `ec75194` | Update LibreChat pin after CI formatting |
| 2026-05-12 | `92664f2` | Update LibreChat pin for CI fixes |
| 2026-05-12 | `ecb08ed` | Update LibreChat pin for Redis stream fix |
| 2026-05-12 | `59c4c76` | Update LibreChat pin for annotated stream fix |
| 2026-05-12 | `7f09d72` | Update LibreChat pin for connected-account CI fix |
| 2026-05-12 | `e165455` | Document meeting transcript inventory Recall |
| 2026-05-12 | `9da24b1` | Publish voice and background QA hardening |
| 2026-05-12 | `29f1597` | Update LibreChat inventory-source pin |
| 2026-05-12 | `d3d9f5c` | Pin transcript Recall QA fixes |
| 2026-05-12 | `320dde9` | Add transcript chronological Recall QA |
| 2026-05-14 | `cea7cff` | Add stable runtime and GlassHive workflow controls |
| 2026-05-18 | `56d5c04` | Harden QA and runtime publishing |
| 2026-05-18 | `c7a03e6` | Prepare public voice runtime release |
| 2026-05-19 | `8192e1d` | Pin merged voice components |
| 2026-05-24 | `8c427b0` | Prepare sanitized enterprise release |
| 2026-05-24 | `3b18a35` | Record GlassHive enterprise release QA |
| 2026-05-24 | `46825fd` | Merge GlassHive enterprise release QA |
| 2026-05-24 | `f034aed` | Update GlassHive component pin |
| 2026-05-26 | `dd05126` | Harden runtime QA and GlassHive MCP contracts |
| 2026-05-26 | `95a3fdc` | Document GlassHive recovery QA and pins |
| 2026-05-28 | `e4d09f8` | Checkpoint GlassHive broker and activation work |
| 2026-05-29 | `ab88dee` | Add config-driven default GlassHive worker profile |
| 2026-06-06 | `87ecc8c` | Ship public runtime updates |
| 2026-06-16 | `26b7170` | Publish runtime hardening |
| 2026-06-16 | `06d750c` | Update LibreChat component pin |
| 2026-06-16 | `91c1a9d` | Update LibreChat component pin |
| 2026-06-16 | `ffc8d76` | Preserve explicit nightly disables on upgrade |
| 2026-06-16 | `2de8626` | Update final nested component pins |
| 2026-06-16 | `212e103` | Align model-readiness docs |
| 2026-06-16 | `9ad801d` | Align runtime requirements schema |
| 2026-06-16 | `41bdb5c` | Pin public component fixes |
| 2026-06-16 | `40d50bb` | Repin final public component heads |
| 2026-06-16 | `3b7d3b8` | Pin updated GlassHive component |
| 2026-06-16 | `551c54c` | Repin final nested components |
| 2026-06-16 | `50b99fd` | Repin GlassHive sanitizer fix |
| 2026-06-16 | `2257ea9` | Repin final GlassHive cache-bust fix |
| 2026-06-16 | `a4cec68` | Pin GlassHive workstation-status fix |
| 2026-06-20 | `206d853` | Align GlassHive worker config and Telegram dedupe |
| 2026-06-20 | `aba876c` | Default GlassHive for preset installs |
| 2026-06-20 | `fe91b6c` | Repin merged GlassHive components |
| 2026-06-20 | `0714511` | Repin LibreChat scheduler-date fix |
| 2026-06-21 | `2e46432` | Document and pin GlassHive production QA hardening |
| 2026-06-22 | `e263d4f` | Publish GlassHive release hardening |
| 2026-06-22 | `f4bd76f` | Publish additional GlassHive release hardening |
| 2026-06-23 | `73f4924` | Publish GlassHive workspace-link hardening |
| 2026-06-23 | `c1f213b` | Publish additional GlassHive workspace-link hardening |
| 2026-06-27 | `64a0794` | Publish runtime and QA updates |
| 2026-07-09 | `c68b464` | Publish Telegram, GlassHive, and emotion QA updates |
| 2026-07-09 | `fc5fc9a` | Preserve an index before branch integration |
| 2026-07-09 | `e7e1527` | Preserve a branch-switch backup reference |
| 2026-07-09 | `b02005b` | Pin LibreChat to merged Telegram upload fix |
| 2026-07-11 | `7312bba` | Ship emotional state and runtime reliability updates |
| 2026-07-19 | `5adc99c` | Add native Feelings navigation and parity source of truth |
| 2026-07-19 | `7c1ddde` | Pin corrected Feelings reaction default |
| 2026-07-19 | `e19a319` | Calibrate full-platform Feelings reaction potency |

## Nested Repository Delivery Inventory

There is no `.gitmodules`; managed components are ordinary nested repositories pinned by
`components.lock.json`. All configured pin objects were present locally during the audit.

### Original 2026-07-18 Snapshot

The table below preserves the delivery mismatch that motivated the audit. It is historical evidence,
not the current candidate ledger.

| Component | Original audit checkout versus configured pin | Viventium role | Fresh-install risk at that snapshot |
| --- | --- | --- | --- |
| LibreChat | Tested HEAD `a55efcdc4cfc0847877e30c90f76d693ba31cb25` is one commit behind configured pin `f051e431524e394f18cebcd0dda7df1685d328aa`, and the tree is heavily dirty | Main web/API, connected accounts, agent UX, Feelings | The VM-tested onboarding/Feelings tree is neither the clean configured pin nor a publishable artifact. Fresh manifest checkout behavior can differ in both directions. |
| agents-playground | One commit behind; clean | Classic playground/fallback boundary | Current checkout is not exact delivery. |
| LiveKit agents | Four commits behind; clean | Voice/runtime provenance | Current checkout is not exact delivery. |
| Cartesia voice agent | Three commits behind; clean | Voice fallback/provider path | Current checkout is not exact delivery. |
| agent-starter-react | Exact; clean | Modern playground | Current checkout matches configured pin. |
| GlassHive | One commit behind; dirty | General worker delegation/workflows | Owner worker behavior/state can differ materially. |
| Microsoft 365 MCP | One commit behind; clean | Microsoft connected-account tools | Current checkout is not exact delivery. |
| Google Workspace MCP | Exact; clean | Google connected-account tools | Current checkout matches configured pin. |
| YouTube transcript MCP | Three commits behind; clean | Transcript tool | Current checkout is not exact delivery. |
| OpenClaw | Three commits behind; clean | Lab/experimental capabilities | Must not be treated as supported Slack/WhatsApp onboarding. |
| Skyvern source | Four commits behind; clean | Lab browser automation | Current checkout is not exact delivery. |

GlassHive also contains many ignored runtime-created git directories under worker sandbox state.
They are not managed components and will not exist on a clean install. This is another reason the
established machine cannot substitute for clean-pin acceptance.

### Current Isolated Candidate Reconciliation — 2026-07-22

After the component pull requests merged, a reconciliation fetched each current `origin/main`, compared
the hosted merge commit with the captured GitHub result, and compared the merged tree with the
previously audited review tree. All 11 current component trees are byte-for-byte identical to their reviewed
heads, every isolated review worktree remains clean, and the parent lock now records the real merged
`main` commits:

| Component | Current ref | Local source state | Delivery evidence |
| --- | --- | --- | --- |
| LibreChat | `85a2e326cd5672f00c927984f00a92c9b3f07f9c` | merged tree exact; review worktree clean | PR 72 merged reviewed head `b0ee2394...`; provider handoff, responsive Channels navigation, complete client/backend/package suites, six headed channel cases, privacy scans, and all 14 exact-head hosted checks pass. PR 73 then added explicit opt-in gates for unprovisioned Docker Hub/Locize publishing, and its post-merge Locize workflow skipped cleanly. Signed/notarized release and installed-runtime identity remain separate gates. |
| agents-playground | `f7ea19564bd062e82aed775b7c8932b70fb8984e` | merged tree exact; review worktree clean | PR 1 merged reviewed head `112f646c...`; classic fallback only. Artifact identity remains open. |
| livekit | `c20e96166726565f026f894ccca6f1cff2480741` | merged tree exact; review worktree clean | PR 1 merged reviewed head `8839980c...`; the locked Docker runtime is a separate delivery artifact. |
| cartesia-voice-agent | `a37250ac2c2de1827853cdc2b2eebee4164b6c69` | merged tree exact; review worktree clean | PR 1 merged reviewed head `df2f0248...`; artifact identity remains open. |
| agent-starter-react | `f196cd5837fe6044543c50f5912f63e976d9d7b1` | merged tree exact; review worktree clean | PR 8 merged reviewed head `fd778562...`, the current modern-playground source. Its hosted test passes; final installed identity remains open. |
| GlassHive | `1cf868e0218262328700085df38ec0ae2196cc2a` | merged tree exact; review worktree clean | PR 41 merged reviewed head `464f97f0...`; artifact identity remains open. |
| ms-365-mcp-server | `c4c6f33b5e395a96780576cf0b55e5c420309e31` | merged tree exact; review worktree clean | PR 1 merged reviewed head `61f4b88e...`; runtime identity remains open. |
| google_workspace_mcp | `070aee1fc34b2eb6e32237e81f3333a71a7e75bb` | merged tree exact; review worktree clean | PR 2 squash-merged reviewed head `c99e0e8d...`; shipped DXT/runtime identity remains open. |
| mcp-youtube-transcript | `60d6bbb38e9c8e1db6dfa0bed03e6834e759f1cd` | merged tree exact; review worktree clean | PR 1 merged reviewed head `b12ec877...`; runtime identity remains open. |
| openclaw | `841336aa05beae35df3c907e0a5b8d40d6350652` | merged tree exact; review worktree clean | PR 1 merged reviewed head `ea9923db...`; optional lab-only component, not supported Slack or WhatsApp onboarding. |
| skyvern-source | `7c0a4ac1364ff30c880ba791be0ef3d487b70370` | merged tree exact; review worktree clean | PR 1 merged reviewed head `ea7c8106...`; runtime identity remains open. |

This closes review-head-to-merge-pin drift. It does not claim that these sources have been built
into the final immutable payload, signed, shipped, or proven as the installed runtime; those
delivery gates remain separate.

## Nested Feature Evolution

### LibreChat overlay

- Initial Viventium overlay and operator account recovery.
- Activation, OAuth, user-level agent synchronization, and voice series.
- Clean-install authentication/onboarding.
- Memory, Recall, and restore continuity.
- Telegram attachment/audio/upload parity and recovery.
- Connected Accounts for Google and Microsoft handoff.
- Emotional-state/Feelings route and runtime workflows.

### GlassHive

- Public worker snapshot, workspace/watch UX, steering, and callback delivery.
- Safeguards, tenant isolation, workspace recovery, capability discovery, preflight/redaction, and UI
  hardening.
- Run links, status, evidence, worker-profile hardening, and historical July work that was once
  beyond the configured public pin before the 2026-07-22 review-head reconciliation.

### Voice and playground components

- Voice settings, startup/signaling, Cartesia/fallback UX, sessions, listen-only mode, transcript
  routing, local Whisper labels, citation sanitation, and modern playground pinning.
- Classic playground and other LiveKit components remain fallback/provenance boundaries.

## Original 2026-07-18 Documentation Contradiction Register

This table preserves the contradictions found by the initial audit; it is historical input, not a
claim that every row remains open. Current dispositions and release evidence live in
[`cases.md`](cases.md), [`README.md`](README.md), and the dated reports under [`reports/`](reports/).

| Topic | Contradiction or drift | Required resolution |
| --- | --- | --- |
| Easy scope | “Only Groq and optional Telegram” versus many additional prompts and later auth gates | One truthful profile description and progressive browser onboarding. |
| Web search | Automatic local/minimal behavior versus the earlier guided Easy-path behavior | Choose one current contract and retire superseded text. |
| Primary AI | Minimal preset selects a connected account before browser account creation | Model the state as pending and finish in browser. |
| GlassHive | Previously mandatory in the easy profile, but Codex/Claude login was not disclosed at profile choice | Preflight disclosure plus optional deferred activation if product requirements permit. |
| Readiness | Config presence shown as `Ready` versus requirement for a successful live request | Shared connection/readiness state machine. |
| Playground network boundary | Docs describe localhost, but launcher omits Next's hostname flag and the framework defaults to a wildcard listener | Bind explicitly to loopback in local mode; test declared remote modes separately. |
| Telegram STT | Schema suggests hosted OpenAI fallback while compiler/docs require local Whisper inheritance | Remove silent provider remapping and align schema/tests/docs. |
| QA owners | Readiness registry points to missing generic owner paths | Point to actual feature owners or create deliberate new owners. |
| Version | Root `VERSION` and a public productization doc name different release versions | Establish one release version source of truth. |
| Legacy tree | Architecture/system docs still reference an absent older runtime tree | Mark historical topology explicitly or remove current-path implication. |
| Secret wording | Some systems text can imply shared `.env` authoring | Reaffirm config plus Keychain; generated env is output only. |
| Installer doc structure | Current contract and dated incident history are interleaved in a very long append-only file | Put current normative contract first and archive dated history below it. |

## Fresh-Machine Versus Established-Machine State Map

| State class | Fresh machine | Established machine | Acceptance implication |
| --- | --- | --- | --- |
| Source | Clone plus exact manifest pins | Active checkout, local branches, possible dirty overlays | Test both separately. |
| Prerequisites | Xcode tools/Homebrew/runtimes may be absent | Already installed and cached | Missing/degraded matrix is mandatory. |
| Models/images | None downloaded | Models, images, packages, and build caches present | Measure first-run time and interruption. |
| App config | No canonical config | Mature config with explicit user choices | Configure must merge/preserve. |
| Secrets | No Keychain references | Provider/channel/account references exist | Never export plaintext; test reauth/revoke. |
| Accounts | No local browser admin or OAuth connections | Existing accounts and provider routes | First-admin path must be run fresh. |
| Databases | Empty | Chats, saved memory, Recall corpus, schedules, auth state | Backup/restore must cover each class. |
| Workers | No CLI auth/profile/workspaces | Signed-in workers and accumulated sandboxes | Easy Install must defer these prerequisites or disclose and validate them before activation. |
| Channels | None connected | Telegram and other routes may be operational | Fresh token/self-test/allowlist required. |
| Helper | Not installed | Installed helper controls active runtime | Helper install/update/rollback must be tested cleanly. |

## Step-By-Step Persona Journeys

The state map above explains the engineering difference; these two journeys define what a person
must actually experience. They are acceptance narratives, not evidence that every step has passed.
The dated installer cases and reports remain authoritative for `PASS`, `PARTIAL`, `FAIL`, and
`BLOCKED` results.

### Persona A — New, Nontechnical Mac User

Assumptions: the person has never used Viventium, does not know Docker, Node, MongoDB, API-key
terminology, ports, or terminal recovery, and has no Viventium state to preserve.
Primary acceptance owners: `INST-008`, `INST-014`, `INST-017`, `INST-019`, and `INST-023` in
[`cases.md`](cases.md).

| Step | What the person does or sees | What Viventium must do without asking | Failure and recovery contract |
| ---: | --- | --- | --- |
| 1 | Runs the single published command. | Verify a versioned immutable payload, this Mac's compatibility, free space, network, and the local-only security posture before mutation. | Explain the exact blocker in plain language; do not leave a partial install or ask the person to debug package managers. |
| 2 | Chooses **Easy Install** (recommended) or deliberately opens **Custom Settings Install**. | Select the native lightweight profile by default; defer Docker, voice, workers, channels, search, and Recall when they are not required for the first useful answer. | Preserve the choice on retry; never silently remap it to a different runtime or provider. |
| 3 | Watches a short, truthful progress sequence. | Protect pre-existing target paths, install exact app-owned runtimes, compile configuration, start loopback-only services, and verify actual health through a transaction journal. | Offer Retry/Resume or safe rollback from the failed stage; never report success from config/process presence alone. |
| 4 | Viventium opens to local first-admin creation. | Keep first registration loopback-only, create the actual first administrator, seed only public defaults for that user, and avoid developer or synthetic owner leftovers. | If account creation is interrupted, resume without creating a hidden or duplicate owner. |
| 5 | Connected Accounts opens automatically and explains the recommended next action. | Lead with one OpenAI API-key action for Easy Install; keep optional Anthropic, Groq, and Grok/xAI cards available without implying they are required; store submitted credentials through the encrypted user-key boundary and disclose provider, billing, and data-routing implications. | Keep the dialog and typed value available for retry when storage/network fails; distinguish invalid credential, quota, outage, and offline states. |
| 6 | Connects the recommended OpenAI provider with one action and runs Test. | Make a live least-privilege provider request before showing `Ready`; keep other API-key cards optional and experimental subscription compatibility separate from supported setup. | Preserve configuration and offer Replace, Retry, or Disconnect without reinstalling or exposing a secret. |
| 7 | Sends a first ordinary message and receives a useful answer. | Persist both turns, refresh/restart successfully, and keep optional unavailable capabilities from blocking chat. | Never show a false success toast or lose the draft; point directly to the missing connection or degraded dependency. |
| 8 | Finds Feelings and optional capabilities from the normal sidebar/control surface. | Explain prerequisites only when the person selects the feature; preserve the current conversation and provide a return path. | Unsupported future integrations such as consumer WhatsApp must say `unsupported`, not display a fake setup form. |
| 9 | Closes and reopens Viventium later. | Start through the installed helper, reuse the correct local state, and show truthful health/recovery status. | Repair or roll back an interrupted update without deleting conversations, memory, files, schedules, or account configuration. |

### Persona B — Established User With A Reliable Local Setup

Assumptions: the person already has a working checkout/helper, mature configuration, provider and
channel references, chat history, saved memory, Recall/RAG content, schedules, uploads, and possibly
explicitly enabled or disabled optional capabilities.
Primary acceptance owners: `INST-001`, `INST-003`, `INST-006`, `INST-018`, `INST-022`, and the
transaction/restore cases in [`../continuity-ops/cases.md`](../continuity-ops/cases.md).

| Step | What the person does or sees | What Viventium must preserve automatically | Failure and recovery contract |
| ---: | --- | --- | --- |
| 1 | Runs the supported upgrade command. | Inventory active checkout/helper/runtime ownership and create a complete, owner-only recovery checkpoint before stopping or mutating anything. | Refuse the upgrade if the checkpoint cannot be proven complete; keep the healthy old runtime running. |
| 2 | Reviews a concise change and continuity summary. | Preserve unknown and user-managed config fields, Keychain references, explicit feature choices, agent edits, provider state, schedules, uploads, chat, memory, and Recall rebuild obligations. | Do not overwrite mature state with Easy Install defaults or generated files from another checkout. |
| 3 | Approves the upgrade. | Stage and validate the candidate separately, pin exact nested components/artifacts, journal the mutation, and switch only after preflight succeeds. | On interruption or failed health, restore the exact previous checkout/config/runtime/database identity and quarantine the failed candidate. |
| 4 | Viventium restarts. | Bind the intended database, ports, state paths, and helper checkout; run migrations safely; verify all promised surfaces before reporting success. | Distinguish optional degraded services from core failure and give one recovery action per failed surface. |
| 5 | Opens existing conversations, memories, files, schedules, providers, and Feelings. | Prove content parity, refresh/restart persistence, excluded auth/secret boundaries, and any required Recall reindex or reauthentication ledger. | Never substitute source inspection or collection counts for the visible existing-user path. |
| 6 | Changes one setting or reconnects one provider. | Apply an atomic config transaction and reload only the affected surface while preserving unrelated state. | A failed save/reload retains the prior live configuration and the person's input for retry. |
| 7 | Uninstalls only if deliberately requested. | Stop owned processes and remove only owned application artifacts while retaining or explicitly offering a recoverable data backup. | Never follow symlinks, delete by filename alone, or touch unrelated apps and personal files. |

The decisive parity rule is: a clean user must not depend on the established machine's caches or
leftovers, and an established user must not be reset to clean-user defaults. Both journeys must
produce the same truthful, useful product on their own state boundary.

## Inventory Conclusion

The project has invested heavily in installer mechanics, resilience, continuity, cognitive defaults,
voice, Telegram, GlassHive, connected accounts, and Feelings. The missing work is not a lack of
individual features. It is a single truthful, transactional, secure new-user system that binds those
features together on the exact shipped artifact and proves the same system preserves an established
user's state. The audit and remediation plan use that end-to-end boundary as the release gate.
The current disposable-VM result is therefore a **source-candidate proof**, not delivery proof. The
11 audited component trees, merged commits, and parent pins now agree, but rebuilt client and
payload bytes, signed/notarized distribution, and installed-artifact reruns remain required
before `INST-022` can pass.
