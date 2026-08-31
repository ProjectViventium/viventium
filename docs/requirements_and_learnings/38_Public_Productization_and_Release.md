# 38. Activation and Public Release

**Status:** Active working single source of truth; proposed product changes remain open until their
owning docs, schema, runtime and QA agree

**Product target:** Viventium `v0.5.0`

**First public platform:** Apple Silicon Mac, macOS 13 or later

**Decision baseline:** 2026-08-22

**Owner:** Viventium Core

## 1. Purpose and authority

This document owns the complete activation and public-release outcome, the locked product decisions,
the delivery order, and the final release gates. It answers one question:

> How does a new person install the complete Viventium product, connect an AI account, get a useful
> answer, and keep an always-on, reliable Viventium without developer work?

The detailed implementation contracts remain in their feature owners. In particular:

- [Installer and Config Compiler](39_Installer_and_Config_Compiler.md) owns installer mechanics,
  generated config, security, update, rollback, and restore.
- [GlassHive Workstation and Worker Runtime](48_GlassHive_Workstation_Sandbox_Runtime.md) owns worker,
  project, sandbox, callback, and takeover behavior.
- [Prompt Architecture and Token Efficiency](49_Prompt_Architecture_and_Token_Efficiency.md) owns
  Prompt Workbench, prompt lineage, drift, traces, and exact-model evaluation.
- [Main Continuity Kernel](56_Main_Continuity_Kernel.md) owns one admitted context and capability
  snapshot across Web, calls, channels, fallbacks, schedules, and workers.
- [Remote Access and Tunneling](47_Remote_Access_and_Tunneling.md) owns the existing local,
  Tailscale, NetBird, Cloudflare experiment, and custom-edge modes.
- [Runtime Feature QA Map](45_Runtime_Feature_QA_Map.md) maps features to their acceptance suites.
- [Public/Private and License Matrix](40_Public_Private_Boundaries_and_License_Matrix.md) owns
  redistribution, notices, and public-safety decisions.
- [V0.5 High-Level Architecture](../../viventium_v0_5/docs/03_High_Level_Architecture.md) and
  [V0.5 Product Experience](../../viventium_v0_5/docs/04_Product_Experience.md) are proposed design
  inputs, not runtime truth. This release plan wins where they imply an unapproved replacement UI.

For planning and release decisions, this document wins when an older plan conflicts. That does not
make a conflicting runtime or owner document conform. Phase 0 must reconcile each conflict in its
owning doc, schema/default, runtime and QA before implementation may claim the decision is active.
Until then, the conflict is an open release blocker. Historical QA reports remain evidence of what
was true when they were written; they are not active product policy.

No one may silently change this plan. The rows in section 15 establish the initial baseline. Every
later material change must add a dated correction row with:

1. the exact old and new decision;
2. the new evidence and source date;
3. the effect on product completeness, Quality, Performance, risk, time, data, and migration;
4. a red-team argument against the change;
5. the affected requirement and QA IDs.

### 1.1 Product-owner vision lock

The approved 2026-08-23 direction is retained in the authorized private source ledger. Its
public-safe product outcome is:

- Viventium is the complete product layer above replaceable chat clients, providers, native agent
  bodies, connectors and channels. It does not compete by rebuilding those commodity layers.
- Keep the full Viventium capability set. LibreChat remains the hidden chat and Agent Builder
  substrate for `v0.5.0`; GlassHive remains the main worker plane; Prompt Workbench is mandatory;
  calls, voice and remote access remain first-class always-on capabilities.
- The activation promise is one signed Apple Silicon app, one easy subscription connection, an
  Advanced API-key path, a real first answer, start at login, and app-owned update, repair, backup,
  restore and rollback. A later container profile may serve other systems.
- Product readiness, user surfaces, independent reliability, Quality and Performance take priority.
  Repository size and implementation novelty do not.
- Reuse proven open-source work before writing replacement machinery. Hermes is the primary
  activation donor and reference. Selective reuse is required when it is safer and shorter; a
  wholesale Hermes host/runtime merge remains forbidden.
- No copied module may weaken Viventium, expose Hermes as the installed product, create a floating
  runtime dependency, lose user state, or bypass license, security, exact-artifact and real-user QA.

This section and the stable `AR-*` / `CAP-*` rows are the fixed success criteria. A later summary or
implementation plan may not silently narrow them.

## 2. Final verdict

Package and stabilize the Viventium that already works. Do **not** rebuild it on Hermes, OpenClaw,
or a new chat client for `v0.5.0`.

Here, `v0.5.0` means the first packaged public release of the complete current Viventium product.
It does not mean that the proposed MIND / CONNECT / CHARACTER / AUTOMATIONS shell is approved or
implemented. This release keeps the existing branded LibreChat surface while preserving those
proposals for a later owner-approved product-experience decision.

- Viventium is the product and the layer above replaceable AI bodies, providers, tools, and channels.
- LibreChat remains the hidden, pinned chat and Agent Builder compatibility substrate for this
  release. A user installs Viventium, not LibreChat.
- GlassHive is the main worker plane for agents and long-running work.
- Prompt Workbench is a required product surface and release component, not an optional developer
  tool.
- The existing SwiftUI Viventium helper is the starting point for the signed app-owned setup,
  control, status, and update shell. For `v0.5.0`, it opens the already-branded chat in the user's
  normal browser. An embedded WebKit chat is a later option after full parity QA, not an activation
  dependency.
- Apple Silicon native packaging is first. Docker is on-demand for sandboxed capabilities and a
  later portability profile; it is not a prerequisite for the first Mac answer.
- Keep every Viventium capability. Reduce user-visible complexity through profiles, lazy startup,
  stable component boundaries, and truthful health—not by deleting the product.

This is less work and less risk than a port. A port would still require the same installer, account
connection, migration, supervision, update, and clean-machine work, plus a rewrite of Viventium's
conversation, Agent Builder, continuity, Feelings, calls, scheduling, Workbench, and GlassHive seams.

## 3. Fixed user outcome

A nontechnical new user must be able to:

1. Download one signed and notarized `Viventium.dmg`.
2. Drag `Viventium.app` to Applications and open it.
3. Choose **Continue with ChatGPT/Codex** or **Continue with Claude** when an approved subscription
   route is available; choose **Use an API key** only under Advanced settings.
4. Complete the provider's own browser authorization.
5. See a live provider check, send a first prompt, receive a real answer, and find the same answer
   after an app restart.
6. Leave Viventium running at login without keeping Terminal, a source checkout, or Docker open.
7. See one plain readiness screen for chat, workers, prompts, memory, calls, channels, and connected
   services, with one repair action for each failure.
8. Add calls, messaging channels, MCPs, sandboxes, remote access, and other accounts when wanted.
   Telegram is one option, never a requirement.

The release must not require Git, Homebrew, Xcode or Command Line Tools, npm, pnpm, uv, Python, a
system Node, source compilation, or Docker before the first useful answer.

The public install is called **Easy Install**. It is one signed-app journey, not a Native-versus-
Docker choice. The internal `install.experience: express` value remains only as a compatibility
mapping for the existing browser setup and migrations. **Custom Settings** maps to `custom` under
Advanced; `legacy` remains an existing-install state and is never shown as an onboarding choice.

## 4. Non-negotiable requirements

These IDs are stable. A later plan may refine them but must not remove or weaken them silently.

| ID | Requirement |
| --- | --- |
| `AR-001` | Activation is the release blocker: download, open, connect, first answer, persistence, and always-on startup must work without developer help. |
| `AR-002` | The launch product is complete Viventium. Do not remove a capability merely to reduce repository size, payload size, or engineering scope. |
| `AR-003` | Every path is judged by **Quality** (intelligence, relevance, usefulness, alignment) plus **Performance** (fast, smooth, reliable). |
| `AR-004` | Viventium is above providers and native agent bodies. It must not rebuild their models, chat products, connector catalogs, browsers, or generic agent loops. |
| `AR-005` | LibreChat remains the `v0.5.0` chat UI, conversation store, streaming/tool UI, and Agent Builder substrate behind a Viventium boundary. |
| `AR-006` | GlassHive is the required main worker plane. It owns host-native and sandbox workers, projects, runs, evidence, watch/steer/takeover, callbacks, and recovery. |
| `AR-007` | Prompt Workbench is installed, visible, healthy, and release-tested. It owns factory/user/compiled/live prompt lineage, drift, drafts, schedules, traces, and exact-model evals; Developer mode also preserves source lineage. |
| `AR-008` | One immutable Main context/capability snapshot serves Web, calls, channels, fallback, schedules, and GlassHive. A faster degraded path may not become a worse AI. |
| `AR-009` | Telegram, Slack, WhatsApp, email, and future channels are modular choices. No channel is mandatory and no channel owns Main. |
| `AR-010` | Subscription connection is the recommended UX only where the provider permits and supports it. API-key connection is the Advanced path. Never present consumer and API billing as interchangeable. |
| `AR-011` | “Configured” is not “Ready.” Readiness requires a current live test and a specific failure class and repair action. |
| `AR-012` | Apple Silicon Mac is the only initial public acceptance target. The signed `v0.5.0` app is not offered for Intel. Existing Intel/source installs remain untouched and get export/migration guidance; their data-preservation contract remains, but Intel runtime acceptance does not block this release. Other systems may use a later containerized or hosted profile. |
| `AR-013` | Docker is not required for native chat. Docker failure degrades only declared sandbox/container capabilities. |
| `AR-014` | All shipped code is prebuilt, versioned, pinned, signed where applicable, integrity checked, and installed into immutable release directories. |
| `AR-015` | User state is separate from code and upgrades: canonical config in Application Support, secrets in Keychain, component data in declared paths, and no private state in the public repo. |
| `AR-016` | Install, start, stop, repair, update, rollback, backup, restore, and uninstall are app-owned product actions, not shell knowledge. |
| `AR-017` | Components fail and restart independently. An optional connector, Docker, voice, or wider worker-plane problem must not take down chat or produce a false global failure. Failure of the selected core conversation-provider/body path may stop new answers, but history and drafts remain available with a specific repair state; it is never mislabeled optional. |
| `AR-018` | The app preserves existing Viventium users, conversations, agents, prompts, memories, Feelings, schedules, worker projects, artifacts, connections, and recovery data. |
| `AR-019` | Calls and voice stay first-class surfaces. They use the same Main identity and continuity contract; they are not sacrificed by packaging or host isolation. |
| `AR-020` | Stable typed contracts, IDs, metadata, capabilities, ACLs, and health states own routing. Runtime keyword or provider-name heuristics are forbidden. |
| `AR-021` | Reuse mature upstreams and official native bodies when they reduce work without weakening Viventium. Import no alternative host wholesale. |
| `AR-022` | External facts must be rechecked against current primary sources before implementation decisions and again before release freeze. Popularity is evidence, not architecture. |
| `AR-023` | A clean-machine release claim requires the exact public artifact and a real provider answer. Source, mocks, local owner state, or unit tests cannot substitute. |
| `AR-024` | The product must be understandable without internal names such as “R3,” process ports, worker IDs, substrate names, or startup scripts. |
| `AR-025` | Viventium must remain modular enough that a future host, provider, worker body, channel, or persistence component can be replaced without losing Viventium's identity or user state. |
| `AR-026` | Remote use remains a product capability, but local activation comes first. `v0.5.0` reuses the existing Tailscale private-device mode as the recommended release path; NetBird is Advanced and Cloudflare Quick Tunnel remains experimental. It does not create or require a Viventium-hosted relay or ask a normal user to own a domain. |
| `AR-027` | Parallel Work remains dark until its isolation, lifecycle, security, quality, and user-control gates pass. Presence in source is not release readiness. |
| `AR-028` | GlassHive's normal-user worker runs in an app-owned workspace with least privilege. Reading host files, using browser/app sessions, persistent host changes, broader folders, or unrestricted execution requires a clear capability grant; unrestricted no-approval host mode is Advanced-only. |
| `AR-029` | Prompt Workbench ships signed read-only factory prompts plus versioned user drafts/overrides in Application Support. Public runtime editing must not write into an app bundle or source checkout; updates must preserve and safely reconcile user changes. |
| `AR-030` | The public app and helper supervise the signed runtime directly through an app-owned interface and `SMAppService`. They must not depend on `repoRoot`, `bin/viventium`, Git, hand-written LaunchAgents, or AppleScript for the normal user path. |
| `AR-031` | Local administrative surfaces must not put durable bearer or launch credentials in URLs or browser local storage. Use an app-mediated or short-lived loopback session; keep durable secrets in Keychain or the owning server. |
| `AR-032` | Existing connected-account secrets must migrate away from legacy fixed-IV or unauthenticated encryption and plaintext generated root keys. Use versioned authenticated encryption with random nonces and a Keychain-owned root key; prove rotation, recovery and reauthorization behavior. |
| `AR-033` | Reuse commodity release plumbing where it is safer: a pinned Sparkle 2 lane for the app, publisher artifacts for runtimes, and an existing tunnel/relay for remote access. Keep V-owned logic to compatibility, migration, health, permissions and product state. |
| `AR-034` | V API v1 is a control plane for component registry, lifecycle, readiness, navigation, update and recovery. It must not proxy or recreate LibreChat authentication, chat streaming, uploads, files, tools or conversation persistence. |
| `AR-035` | Only the final signed, notarized, stapled and digest-fixed app/runtime candidate can produce release evidence. Signing or repackaging after acceptance invalidates the affected evidence. |
| `AR-036` | The LibreChat fork needs a clean upstream base, V overlay inventory, reproducible build, replay CI and an owner-set maintenance budget. Host extraction is reconsidered only after measured budget failure, not by preference. |
| `AR-037` | Mandatory capability does not mean mandatory resident process. After a successful activation probe, heavy services may hibernate and become Ready on demand while supervisor, chat spine and minimal scheduler remain resident. |
| `AR-038` | Every executable, model, image, library and embedded asset needs a recorded license, redistribution route, notice, provenance and update owner before it enters the signed artifact or downloadable pack. An unresolved license blocks that component and any release claim that requires it. |
| `AR-039` | Easy Install uses the one approved primary account for all required inference that it can serve. Background-cortex activation classification must not require Groq, xAI or any second credential/billing account; a separate classifier is Advanced-only. Product activation and cortex activation are distinct terms. |
| `AR-040` | `v0.5.0` provides local, redacted diagnostics export and a named support policy. It sends no automatic telemetry or crash data and exposes no remote disable switch; any later consented transport is a separate privacy-reviewed decision. |
| `AR-041` | The selected official native agent body is a first-answer runtime dependency with its own pinned version, allowed-use decision, distribution/install route, license/notices, publisher provenance, quarantine/signing treatment, compatibility tests, maintenance budget and update owner. Permission to use a subscription does not by itself permit Viventium to bundle or install the body. |
| `AR-042` | The exact app must spawn every nested Node, Python, MongoDB, helper and native-body executable under its hardened-runtime design. Minimal entitlements, nested signing order, library validation/JIT decisions, quarantine handling and notarization must be proved before payload architecture freezes. |
| `AR-043` | Subscription quota and rate limits are product states. Foreground conversation is protected from background cortices/schedules where the provider permits; exhaustion pauses eligible background work, preserves the draft, shows reset/reconnect guidance and never silently switches to a paid API or second account. |
| `AR-044` | The first-answer route preserves real incremental answer streaming. A progress event or a completed answer split into fake chunks is not streaming. The exact LibreChat route must show answer-text deltas before completion, preserve tool/cancel/error behavior, and measure first-visible answer content plus completion honestly; otherwise release is held. |
| `AR-045` | No-feature-loss is fail-closed. Every declared capability has a stable `CAP-*` identity and must map to a delivery state, natural use case, QA case, exact artifact and dated evidence. A missing, renamed, deferred or deleted capability ID blocks release until section 1 change control resolves it. |
| `AR-046` | Hermes is the primary activation donor for `v0.5.0`. Before creating an installer, onboarding, update, backup, restore, migration, uninstall, service-lifecycle or diagnostics mechanism, compare the pinned Hermes implementation and prefer bounded copy/adaptation when it reduces total work. Preserve upstream notices and file provenance, audit dependencies and assets separately, integrate through Viventium-owned contracts, and import no Hermes agent host, desktop product, identity, state root or floating source checkout. |

## 5. Readiness model

Fast activation and full product completeness are both required. They are different gates.

| User-visible state | What it means | What may still be pending |
| --- | --- | --- |
| **Installed** | The exact signed base payload registers every required market surface and contains the core; any declared large pack is identified by its exact manifest. | No service, pack-download or account claim yet. |
| **Core running** | App supervisor/control registry, LibreChat API/UI, and required persistence pass local health. | Provider connection and first answer. |
| **Ready to chat** | A local user exists, one approved provider route passed a live request, a real answer rendered, chat history/saved memory are available, and persistence passed. | Background warm-up and unselected capabilities. |
| **Viventium activated** | Main continuity, Prompt Workbench, scheduler, GlassHive control plane and one usable worker body, Life bootstrap, memory/Feelings owners, recall's honest state, update/recovery, backup metadata, status and repair pass. | Third-party services the user did not select. |
| **Ready on demand** | A heavy component or signed pack passed activation and wake/recovery probes, then hibernated under the supervisor. | Its process is not resident; selection wakes and rechecks it. |
| **Connected by you** | One selected call, channel, MCP, sandbox, health source, remote path, or account passed its own end-to-end probe. | Other unselected capabilities. |
| **Not released** | A present capability is intentionally hidden because its release gates have not passed. | Parallel Work is in this state until qualified. |
| **Release ready** | The exact public artifact passes the clean-machine, migration, update/rollback, security, performance, and full-product gates in this document. | Nothing required for the declared release scope. |

Rules:

- The user gets **Ready to chat** as early as safely possible.
- Prompt Workbench and wider GlassHive worker/control processes may finish starting after the first
  answer, but the subscription provider/body role must already pass and the app must not say
  **Viventium activated** until the full mandatory spine passes.
- For the planned subscription route, the GlassHive provider role, body auth and live probe are part
  of Ready to chat; wider-worker readiness is not. Phase 0 must prove whether that role runs as a new
  provider-only profile or inside the current full GlassHive process; this document does not assume
  a separately startable slice already exists. The Advanced API route uses its approved direct
  provider endpoint. The release must qualify a fallback architecture, but a person's activation
  never requires a second account, credential or billing system. An unconfigured fallback is shown
  honestly and is not used silently.
- On the subscription route, the GlassHive conversation-provider role and selected native body are
  **core provider dependencies**, not optional workers. If either fails, existing chat/history still
  opens, the drafted prompt persists, and status says **AI connection needs repair** with restart or
  reconnect. New inference may be unavailable; Viventium must not claim chat is Ready or silently
  spend through an API fallback. A wider GlassHive worker/project fault must degrade only delegated
  work and not stop the active provider role; if the selected full-process topology cannot prove that
  isolation, Phase 0 must split the profile before release.
- A feature that needs an account or permission can be **Available — connect to use**. That is not a
  product defect if the artifact and setup path are healthy and the user did not select it.
- A selected capability that fails is **Needs attention**, not “unavailable,” “empty,” or a global
  Viventium failure.
- A hibernated component may say **Ready on demand** only while its last successful probe is inside
  the declared freshness window. Selection wakes and rechecks it; an expired result says
  **Rechecking**, never Ready.
- “Lazy” means the product surface, manifest and activation path are installed and discoverable, but
  the process starts only when needed. Large executable or container payloads may be exact signed
  downloads on first use. The capability and its setup path are never silently omitted.

### 5.1 Delivery state is separate from readiness

| Delivery state | Plain meaning |
| --- | --- |
| **Bundled core** | Code is locally present inside the signed base payload; no later executable download is needed for that surface. |
| **Signed pack — download needed** | The product card and contract ship in the app; a large exact executable, model or image is downloaded, verified and cached when selected. No app reinstall is needed. |
| **Available — connect to use** | The implementation is shipped, but the user has not supplied the account, permission or external product it needs. |
| **Catalog only — not shipped** | Viventium knows the possible integration but does not claim support. It cannot affect readiness. |
| **Preserved — not released** | Source exists but the user surface stays dark because its own gates are open. Parallel Work currently has this state. |

A previously released capability cannot move to a weaker state without the change-control record,
migration and user notice required by section 1.

## 6. Complete product inventory and launch treatment

This is the no-loss launch checklist. The `CAP-*` families are stable and every named item in a row
is an atomic baseline member of that family. In Phase 0, the generated capability manifest must give
each named item a permanent child ID such as `CAP-CHAT-001`, merge additional discoveries from source
and the installed product, and commit the resulting baseline. Deleting code or a UI route must never
delete its baseline ID; it changes that ID's delivery state and opens its gate. Until the child
manifest exists, each complete family row and its literal member list is indivisible and release is
blocked. The inventory must remain synchronized with the generated manifest after that point.

| Stable family | Product area | Capabilities that must be preserved | Launch treatment |
| --- | --- | --- | --- |
| `CAP-APP` | App and control | Install, transactional setup, open, status, start at login, stop, repair, update, rollback, backup, restore, preserve-data uninstall, diagnostics | Required app surface |
| `CAP-CHAT` | Chat | Branded Web chat, persistent sessions/history, streaming, files, artifacts, bookmarks, prompts, prompt templates, tool rows, model/fallback handling | Required before Ready to chat |
| `CAP-CHATSEARCH` | Conversation search | Message/conversation search, private scoped indexing, index refresh/rebuild, result navigation and truthful degraded state | Required chat surface; index may wake/build on demand and must not block the first answer |
| `CAP-AGENT` | Agent creation | LibreChat Agent Builder, built-in agents, models, instructions, files, tools, MCPs, actions, chains, permissions | Required product surface |
| `CAP-MAIN` | Conscious Main | Identity, current Agent Builder configuration, context admission, immutable turn snapshot, fallback parity, final authorship, follow-up/silence judgment | Required before Viventium activated |
| `CAP-CHARACTER` | Character | Character surface, Feelings UI/state, Emotional Reaction, Emotional Resonance, voice expression, state injection and traceability | Installed; Feelings starts off; reaction work must not block chat |
| `CAP-MEMORY` | Memory and Life | Saved memory, Recall/RAG, continuity, deep memory, transcripts, Life bootstrap, Brain Pack direction, governed proposals, restore | Chat memory required; recall may build/degrade; unshipped Brain Pack claims stay unmarketed until proved |
| `CAP-HEALTH` | Health and wellness context | Viventium-Health runtime, provider acquisition/archive, bounded health context, schedules, consent, revocation and truthful degraded-auth state | Installed product capability; provider connection is user-selected and never required for first chat |
| `CAP-COGNITION` | Cognition | Background cortices, anti-sycophancy/reality check, Red Team, research, Phase B, scheduling, periphery/nightly insight flow | Definitions installed; nonblocking work starts by declared config |
| `CAP-WORKBENCH` | Prompt Workbench | Flow, Prompt, Live Drift, Drafts, Evals, Schedules, Prompt Traces, factory/user/compiled/live sync, Developer source sync, exact-model comparisons | Mandatory product surface; prebuilt and openable; heavy evals may run later |
| `CAP-WORKER` | GlassHive worker plane | Projects, host workers, Docker workstations, Codex/Claude/OpenClaw profiles, pause/resume/interrupt/terminate, callbacks, evidence, artifacts, Watch/Steer/takeover | Control plane and one worker required; actual workers start on demand; host power requires consent |
| `CAP-PARALLEL` | Parallel Work | Multi-worker orchestration and isolation | Dark until all declared gates pass; single-worker GlassHive can release independently |
| `CAP-VOICE` | Calls and voice | Call UI, microphone, speech-to-text, text-to-speech, interruption, call continuity, modern playground/operator diagnostics | First-class selected capability; no voice dependency may block chat |
| `CAP-AUTOMATION` | Automations | Scheduled jobs, recurrence, catch-up, run/delivery ledgers, nightly reflection, memory hardening, completion callbacks | Scheduler required; user schedules and heavy jobs start later |
| `CAP-CHANNEL` | Channels | Web plus optional Telegram, Slack, WhatsApp, Signal, email, Discord, and future adapters through one gateway contract | Web required; every other channel user-selected; unsupported adapters stay honest |
| `CAP-ACCOUNT` | Connected accounts | Primary AI subscriptions, API keys, Google Workspace, Microsoft 365, MCP OAuth, multi-account and future adapters | Primary AI required; all other accounts user-selected |
| `CAP-TOOL` | Tools and integrations | MCP catalog/settings, browser/computer use, code interpreter, web search, SearXNG, Firecrawl, Skyvern, files and office artifacts | Discoverable catalog; only selected dependencies start |
| `CAP-REMOTE` | Remote access | Tailscale private-device link, revocation, NetBird/Cloudflare experiment and optional advanced custom domain | User-selected after local activation; Tailscale is the recommended no-domain path and needs its own account/consent and exact QA |
| `CAP-TRUST` | Reliability and trust | Component graph, live health, failure classes, audit/evidence, permissions, loopback defaults, Keychain, signed grants, redaction | Required release infrastructure |
| `CAP-RELEASE` | Release integrity | Component pins, compiled artifacts, installed-artifact identity, SBOM/notices, signing, notarization, upgrade compatibility and rollback | Required release gate |

The inventory must be regenerated from code, owning docs, `components.lock.json`, config schema,
launcher/service manifests, UI routes, QA inventories, and the installed runtime before each release
candidate. A manually remembered feature list is not sufficient.

## 7. Target product architecture

```text
Viventium.app
  ├─ setup, account connection, readiness, repair, updates, backup/restore
  ├─ existing branded browser setup, chat, Agent Builder and product surfaces
  └─ app-owned presentation over one signed supervisor and narrow local control contract
       ├─ V Core: config, authority, continuity, memory/Feelings contracts, gateway
       ├─ pinned LibreChat: chat UI, records, streaming/tool UI, Agent Builder
       ├─ Prompt Workbench: prompts, drift, traces, evals, schedules
       ├─ GlassHive: main worker plane, host workers, sandboxes, evidence, takeover
       ├─ calls/voice services
       ├─ scheduler, memory/recall, cortices and nightly work
       └─ optional account, MCP, channel, remote and container adapters

Replaceable native bodies and providers
  └─ Codex · Claude Code · provider APIs · future approved bodies
```

### 7.1 What “isolate V Core” means

Isolation is a component contract, not a rewrite and not a separate LibreChat product.

1. Define one stable local Viventium **control** contract and component registry beside existing
   services. For `v0.5.0`, this is implemented by the signed supervisor over authenticated XPC or a
   Unix socket; it is not a new chat proxy or a second general-purpose server.
2. Keep current working implementations in place for `v0.5.0`.
3. Make each component declare its version, dependencies, start/stop command, health probe, data
   paths, permissions, resource budget, repair action, and required readiness level.
4. Make Viventium.app the only user-facing lifecycle owner. The existing `scripts/viventium`
   lifecycle logic remains the single implementation, packaged behind the signed supervisor rather
   than rewritten in Swift or invoked from a checkout. The user never starts LibreChat, MongoDB,
   Workbench, GlassHive, or a Python service directly.
5. Move code out of LibreChat only when the boundary is proven and extraction gives a measured
   reliability, portability, upgrade, or product benefit.

V API v1 is intentionally narrow: component inventory, start/stop/drain, readiness, permissions,
navigation, diagnostics, update, backup and recovery. App-to-supervisor control uses authenticated
XPC or a local Unix socket. LibreChat remains the chat data plane; V API must not duplicate its
login, cookies, streaming, uploads, files, tools, Agent Builder or conversation database.

The initial ownership is:

| Owner | Keeps for `v0.5.0` | Boundary Viventium adds |
| --- | --- | --- |
| Viventium.app | Existing SwiftUI status UI and browser-open behavior | Signed setup/control window, bundle-owned helper/supervisor, updater and readiness graph; it opens rather than rebuilds browser onboarding/chat |
| LibreChat fork | Existing branded account setup, local user/auth implementation, conversations/messages, chat UI, streams, tools/MCP UI and Agent Builder | Hidden pinned service; reuse the tested `setup=accounts` browser flow under Viventium branding; stable control boundary, not a second setup implementation |
| V Core | Existing config compiler, gateway, continuity, memory, Feelings, scheduler and brokerage logic | Typed contracts and one component/readiness registry |
| Prompt Workbench | Existing standalone Workbench and source-of-truth prompt registry | Mandatory service manifest, product navigation, health and release gate |
| GlassHive | Existing standalone control plane, worker profiles, host/Docker execution, callbacks and operator UI | Mandatory service manifest, one-click worker login/readiness, V product navigation |
| Native agent bodies | Their own models, tools, browsers, connectors, auth and execution | Bounded V context/result envelope; no reimplementation |

### 7.2 Independent reliability

- Replace the current “start many things because flags default true” behavior with a generated
  component graph. Preserve the launchers as adapters first; do not rewrite every service at once.
- Split the monolithic launcher behind idempotent per-component start, drain, stop and live-health
  adapters with singleton leases. A restart must not duplicate a schedule, callback, worker or call,
  rebuild source, or restart an unrelated component.
- Start the chat spine first, then warm mandatory background components, then user-selected
  capabilities.
- Restart only the failed component when its contract permits. Keep chat available in a clear
  degraded state.
- Use durable queues and callbacks for GlassHive, schedules, channels, and long work. App or browser
  restart must not lose a run.
- Bind local services to loopback by default. Remote access is an explicit capability.
- One status model must distinguish not installed, setup pending, starting, ready, degraded,
  auth expired, quota/rate limited, network failure, dependency failure, unsupported config,
  update required, and failed.
- Each error shows one safe next action and keeps technical detail behind Diagnostics.
- Exact-candidate process provenance must contain no Git checkout, package registry, `npm`, `pnpm`,
  `uv`, Vite, nodemon, compiler or source-only path.

### 7.3 Consumer-safe execution boundary

GlassHive stays mandatory as the control and worker plane, but broad host access does not become a
mandatory permission:

- The default worker gets an app-owned workspace and only the capabilities selected for that run.
- Existing host credentials, browser sessions, personal folders, other applications, network access,
  and persistent system changes are not copied or exposed merely because GlassHive is installed.
- A capability grant names the resource, access level, duration, and visible effect. The user can
  revoke it. macOS permission dialogs remain truthful and are never bypassed.
- Docker or another proved isolation backend is materialized only for work that declares it. A
  missing sandbox reports that capability as unavailable without breaking chat.
- Existing unrestricted `danger-full-access` and no-approval modes are migration/developer features,
  not normal-user defaults. They require an explicit Advanced choice and separate security QA.

### 7.4 Prompt Workbench release boundary

The development Workbench treats repository prompt files as editable truth. A signed application
cannot safely work that way. The public model is:

1. Viventium ships a signed, read-only factory prompt bundle with an exact schema and version.
2. User drafts, accepted overrides, schedules, eval cases, traces, and provenance live in declared
   Application Support data, separate from code.
3. The compiler resolves `factory + user override` into the exact live prompt and records both
   versions. Workbench shows factory, override, compiled and live state without ambiguity.
4. An update stages prompt migrations on a copy, reports conflicts, preserves the old working
   version, and never silently discards a user change.
5. Repository write/publish remains available only in an explicit developer profile.
6. Opening Workbench creates an app-mediated or short-lived loopback session. A durable launch token
   must not travel in the URL or remain in browser local storage.

## 8. Account activation contract

The primary screen has two levels:

- **Recommended:** Continue with an approved subscription account.
- **Advanced:** Add an API key, custom endpoint, local model, or enterprise provider.

One Viventium account adapter owns the UI and the state machine:

`not connected -> authorizing -> connected -> live test -> ready -> expired/degraded -> reconnect`

Provider-specific code stays behind that adapter. The adapter must:

- open the provider's real authorization page in the system browser;
- use state, PKCE, exact callbacks, expiry, single-use attempts, and least scope;
- keep tokens in Keychain or an approved encrypted store, never logs or generated plaintext config;
- show the exact account and capability after consent without exposing private identifiers in public
  evidence;
- run a real provider request before saying Ready;
- keep a drafted first prompt across sign-in, failure, retry, app reload, and restart;
- support reconnect, disconnect, local credential deletion, and provider-side revocation guidance;
- never silently move from subscription usage to paid API usage.

The release must qualify one primary route plus an explicit parity-tested fallback architecture.
The person's activation requires only the route they selected. A fallback that needs another
credential remains **Available — connect to use** and is never invoked silently. Do not require a
Groq, xAI, or any other second account by brand.

### 8.1 Public-shipping authorization gate

The current fork contains working OpenAI Codex and Anthropic subscription OAuth paths. They use
provider-specific client IDs, endpoints, headers, and token refresh behavior. Local success does not
prove that a third-party public product may ship those flows.

Before release, each subscription adapter must have one recorded outcome:

1. **Approved direct adapter:** current provider documentation or written permission explicitly
   permits the public Viventium client and its requested use; or
2. **Official native-body adapter:** Viventium invokes the provider's supported Codex/Claude body
   and that body performs its own login in a V-owned credential home without copying or
   impersonating credentials from another installation; or
3. **Advanced API only:** the subscription button is not offered for that provider and the user
   supplies an API credential.

That decision covers account **usage** only. Phase 0 must separately record whether Viventium may
bundle, auto-download, or ask the user to install the exact native-body binary, and how its license,
notices, publisher provenance, quarantine, signing, update and removal work. A provider allowing its
own CLI to use a subscription is not evidence that a third-party commercial app may redistribute or
silently install that CLI.

Do not ship borrowed client IDs, endpoint impersonation, scraped browser sessions, or an unofficial
consumer token route as a public promise. This is a legal, security, support, and sudden-breakage
gate—not optional paperwork.

Official current facts support the intended UX but not every possible integration:

- OpenAI states that Codex can be used through an eligible ChatGPT plan after signing in with the
  ChatGPT account. A normal ChatGPT subscription does not fund ordinary OpenAI API usage.
- Anthropic states that Claude Code can use a Pro or Max subscription, while ordinary Claude API
  usage is a separate product and bill.

The shortest candidate is the official Codex CLI/body through the GlassHive profile boundary, not a
new model/provider stack. The current GlassHive auth-copy profile is **not** this safe route and
cannot ship as one. The current Codex app-server integration is also not the release default:
existing exact-version evidence found stale per-turn authority and append-not-replace behavior in
the methods GlassHive needed. The official CLI/body boundary and V-owned home remain the lowest-work
candidate, but its current `exec` transport emits completed answer events rather than real
incremental answer deltas. It therefore does **not** yet satisfy `AR-044`. Phase 0 must test the
exact supported transports and select one that proves both per-turn replacement authority and
incremental answer streaming through LibreChat. App-server remains disqualified unless a fresh
pinned contract test fixes its authority semantics and proves that stream. No transport is
release-selected merely because it can eventually return a complete answer.

### 8.2 First-answer route for `v0.5.0`

The planned subscription-first route is explicit:

`branded LibreChat UI -> existing GlassHive provider adapter -> provider's official native body`

That architecture is selected; its body transport is not frozen until `AR-044` passes. A status,
reasoning or tool event is not an answer-text delta, and Viventium must not replay a completed answer
as fake chunks.

GlassHive owns the V-managed body and its V-owned credential home; the native body owns its login.
This reuses the current GlassHive provider path and avoids publishing the fork's unofficial direct
consumer-token emulation. The provider/body role is therefore part of **Ready to chat**; the wider
GlassHive worker, project, callback and takeover readiness remains part of **Viventium activated**.
Those can be logical roles in one proven process or separate profiles; Phase 0 owns that measured
topology decision and its failure/update boundary.

The Advanced route is:

`branded LibreChat UI -> approved provider API/custom endpoint using the user's API credential`

An approved direct subscription adapter may replace the first route only after the section 8.1
gate and section 1 change-control test show that it is supported and lower risk. If no provider
permits either subscription route, the subscription button does not ship and `v0.5.0` does not meet
the fixed subscription-first outcome; API-key-only success cannot be relabeled as full activation.
The release is held. Moving subscription-first to a later release or shipping API-first requires a
new section 1 decision that explicitly changes the fixed outcome; it is not an automatic fallback.

The current `glasshive.provider.enabled: true` default is therefore intentional, but Phase 0 must
remove its auth-copy and unrestricted-execution assumptions. The existing Easy Install browser
account flow remains the UI. Viventium.app opens that route in the system browser and owns progress,
readiness and repair; it does not rebuild the provider forms in Swift or WebKit.

## 9. Packaging and distribution

### 9.1 Primary public artifact

The first public artifact is one Apple Silicon `Viventium.dmg` containing a Developer-ID-signed,
hardened, notarized and stapled `Viventium.app` plus an immutable manifest. The app may download a
matching runtime payload during setup if the download is exact, signed, resumable, and rollback
safe. The payload must not resolve package registries or compile source on the user's Mac.
Every nested executable must have a declared hardened-runtime/entitlement and quarantine treatment;
signing the outer app cannot make an unproved child process releasable.

The existing SwiftUI code is the presumptive least-work shell, not a production app as-is. Phase 0
time-boxes one build/sign/normal-window/`SMAppService` feasibility spike. Continue with a real Xcode
archive target if it passes; compare another shell only if a named requirement fails. Do not add a
second lifecycle application or embedded chat client by assumption.

### 9.2 Runtime payload

| Payload part | Release treatment |
| --- | --- |
| Viventium.app/helper | Signed native Apple Silicon app and bundle-owned helper/IPC; login item or LaunchAgent registered through `SMAppService`; packaged, signed internal `scripts/viventium` modules may remain the single lifecycle implementation behind the supervisor, but there is no source-checkout dependency, user-invoked shell step or second lifecycle owner |
| Viventium/LibreChat client and server | Pinned production build; no Vite, nodemon, `npm install`, or source build on the user machine |
| Node | One pinned supported official runtime shared by compatible Node services |
| MongoDB | Keep for `v0.5.0`; exact publisher archive downloaded, verified and cached after notice unless redistribution is formally accepted; loopback-only app-owned data and resource limit |
| Prompt Workbench | Parent-tracked in-tree component for `v0.5.0`; prebuilt client/server, source commit plus file-manifest stamp, signed factory prompt bundle, Application Support override store, migration rules, and short-lived local session in the release manifest |
| GlassHive and Python services | One selected relocatable Apple-Silicon CPython distribution plus offline-built locked wheels and signed native libraries; dependency sharing only after compatibility proof; app-owned least-privilege workspace; no system Python, `pip` or `uv` at install time |
| Official native agent body | Launch candidate: one pinned Apple-Silicon Codex CLI publisher artifact after separate usage and distribution/install approval; exact license/notices, digest, publisher provenance, quarantine/Gatekeeper treatment, V-owned credential home, compatibility tests, maintenance budget, update/removal owner and no floating `latest`. Claude is not release-required until it passes the same gate |
| Voice and other native services | Signed Voice Capability Pack with exact gateway/LiveKit/playground/model artifacts, licenses, microphone owner, task/speaker schema, restart and audible endurance contract |
| Docker workstation and container tools | Separate consent card; detect a supported engine or open its official installer; explain licensing/resources; never install or accept Docker Desktop terms silently; verify images only when enabled |
| Optional search/recall services | On-demand exact artifacts; no accidental startup dependency from the historical launcher |
| Secrets | Keychain-owned root keys or official-body secure stores; versioned authenticated ciphertext with random nonces; no durable secret in generated env/config |

Every nested component requires agreement among source commit, `components.lock.json`, compiled
artifact, release manifest, installed artifact, and runtime-reported version. Parent-tracked
components such as Prompt Workbench use the parent commit plus an exact source/build manifest stamp;
they must not be falsely required to appear as a nested `components.lock.json` entry.

When a delivery requires the latest local Viventium to be running, source changes are not delivery.
Start the candidate through the supported lifecycle path and prove that the active process,
configuration, build manifest, component pins, and visible version all identify that exact
candidate. This is the public owner for `GOV-014`; `INST-029` / `INST-UC-021` owns acceptance.

One machine-readable product/service registry must generate coverage and status; do not add another
hand-maintained master ledger. CI must compare source, component pins, built artifacts, installed
identity, and QA state. Split the launcher, public CLI, and compiler incrementally into a typed
supervisor and small service modules only when measured coordination or failure risk justifies the
split; never use this requirement to authorize a wholesale rewrite. This is the public owner for
`ONB-011`; `INST-033` / `INST-UC-025` owns acceptance.

### 9.3 State and upgrades

- Immutable code: versioned release directories.
- Mutable user state: declared directories under `~/Library/Application Support/Viventium/`.
- Secrets: macOS Keychain references. Migrate legacy fixed-IV/unauthenticated ciphertext and
  plaintext generated root keys before calling connected accounts release-ready.
- Reuse and harden `scripts/viventium/migrate_connected_account_keys.js` as the starting migration
  path for legacy connected-account records; add authenticated-encryption versioning, Keychain-root
  injection, rotation, corrupt-record rollback and explicit reauthorization cases rather than
  writing a second credential migrator.
- App update: use a pinned Sparkle 2 integration, Developer ID plus notarization, HTTPS, and EdDSA
  archive verification instead of inventing generic Mac update plumbing.
- Runtime-pack update remains V-owned because it must enforce one compatibility manifest and health
  graph across LibreChat, Workbench, GlassHive, voice, schemas and user state.
- Reuse `scripts/viventium/native_payload.py` as the verified archive/stage/activate/rollback
  starting point. Reconcile it with the existing public `origin/main` native payload builder,
  assembler, runtime/process guard, installer and protected workflow; extend and wire the proved
  pieces instead of creating a second updater. They do not yet prove the replacement exact payload,
  data migration, legacy-supervisor takeover, restore or the complete signed app path.
- Candidate update: download -> verify -> quiesce all writers -> consistent logical/snapshot backup
  -> stage -> migrate component-by-component with a journal -> semantic verification -> start ->
  live health -> atomic switch.
- Failed binary health: return to the last known-good compatible release.
- Data migration: declare N/N-1 compatibility per owner and restore data as well as binaries when
  necessary. Never raw-copy a live MongoDB directory or claim binary rollback reversed an
  incompatible migration.
- Existing source installs: detect, inventory, back up, migrate once, verify counts and sample
  records plus hashes and representative semantic reads, deactivate old login items/services, then
  leave the source checkout untouched. Credentials that cannot be backed up require explicit
  reauthorization, not a false restore claim.

### 9.4 Remote and optional substrate policy

Do not build a Viventium-hosted relay for `v0.5.0`. Reuse the existing remote adapter and modes:

- local-only is the default;
- `tailscale_tailnet_https` is the recommended **Use from anywhere** path for the user's own
  enrolled devices;
- `netbird_selfhosted_mesh` remains an Advanced self-hosted choice;
- `cloudflare_quick_tunnel` remains an explicit experiment, not the full-product public path;
- custom/public edge remains Advanced and may require a domain.

Phase 0 selects the exact Tailscale version and connection UX, source-dates its terms/privacy
review, and names its update owner. Viventium must not market remote readiness until the selected
mode passes connection, certificate, revocation, restart, outage and privacy gates. A future
Viventium-hosted relay is a separate product decision with cost, abuse, tenancy and uptime owners;
it is not hidden inside this release.

Tailscale Serve requires a tailnet account and HTTPS enablement. Its certificate flow can publish
the selected tailnet and device DNS name in a public certificate ledger. The connection card must
explain this before consent, use a non-personal app/device name, and offer local-only as the default.

Homebrew, npm, and clone-based install remain developer or later convenience surfaces. They are not
the primary activation answer and do not block the signed Mac release.

## 10. Minimal-effort execution plan

The rule is vertical delivery: each phase ends in a usable, testable user journey. Do not spend a
phase only moving code between repositories.

### Phase 0 — Freeze truth and release inputs

**Outcome:** one reproducible candidate can be named before packaging starts.

- Keep this document as the decision ledger and link every implementation issue to an `AR-*`,
  `CAP-*` and QA case.
- Reconcile the decisions here into every affected owner doc, schema/default, launcher, product
  label and QA catalog. Current “optional Workbench/GlassHive” and Telegram-required contracts are
  explicit conflicts, not harmless old wording. Reconcile the proposed V0.5 four-door shell as
  deferred, `Easy Install` as the public signed-app label, `express` as its internal compatibility
  value, and Intel as outside the initial runtime acceptance matrix.
- Create the generated `AR/CAP -> delivery state -> natural use case -> stable QA case -> exact
  artifact -> evidence -> status` ledger and a fail-closed zero-open release evaluator. Extract both
  ID sets from this document; compare the generated child-capability manifest with its committed
  baseline. A vanished ID, missing mapping or any `OPEN`, `NOT RUN`, `PARTIAL`, `BLOCKED` or `FAIL`
  required case blocks release.
- Generate the full feature/component/data/auth inventory from source, live runtime, docs, and QA;
  assign every named and newly discovered capability a permanent child `CAP-*` ID before release
  implementation begins.
- Freeze clean component commits and parent pins; create a per-component `ship / defer / discard`
  triage ledger for current dirty/unshipped work without discarding it. Record commit, owner,
  disposition, build hash and install hash for each entry.
- Preserve the active dirty checkout and reconcile it with `origin/main` before designing new
  packaging code. The 2026-08-22 graph audit found the active `HEAD` 205 commits behind and one
  two-line component-pin commit ahead of `origin/main`; the large local product delta is uncommitted,
  not evidence that the branch contains the missing public work. Create a clean release worktree from
  the freshly verified `origin/main`, record and replay every owner-approved local tracked/untracked
  delta onto that base, and resolve conflicts through the triage ledger. Do not reset or overwrite
  the active worktree. Use forensic per-file porting only for actual replay conflicts; do not
  reconstruct a selected subset of hundreds of newer public files into the stale base. Retain the
  recorded failed exact-payload cases as regressions. Use the arm64 lane for this release; the old
  x86_64 lane is reference, not a reason to reopen Intel acceptance.
- Freeze LibreChat's known upstream base, V overlay inventory, reproducible build and replay CI;
  record the maintenance budget that would trigger a future bounded extraction study.
- Freeze the native body's version, publisher source, compatibility suite and update cadence; record
  a maintenance budget and an emergency security-update path independent from the LibreChat budget.
- Record every third-party license, redistribution choice, account authorization decision, and
  exact upstream version. Unapproved MongoDB, Meilisearch, model, image or voice redistribution is
  a release blocker for any surface that requires it.
- Prove the selected first public subscription route now: the existing GlassHive provider adapter
  to a supported official native body in a V-owned credential home. If the provider does not permit
  it, stop and change the release decision; do not freeze onboarding copy or payload architecture
  around an assumed grant. Keep Advanced API as the separately tested route.
- Run a Phase-0 transport-parity spike through the exact LibreChat route. On declared long answers,
  require at least two answer-text deltas before the final completion event, plus correct tool,
  cancel, error and persistence behavior; post-completion chunking fails. Benchmark at least 20 cold
  and warm first turns on the selected subscription/body route and matched Advanced API route on the
  declared Mac/network profile. The timer begins when the user activates **Send** and includes
  LibreChat, GlassHive startup, authentication and body-session creation. Freeze acknowledgement,
  first-visible answer-content, completion and relative-overhead budgets before the candidate
  architecture; use `time-to-first-token` only when the transport exposes real incremental
  tokens/deltas. Do not loosen budgets after a failed run.
- Measure the exact Ready-to-chat DMG/runtime bytes, download, verification, installation and first
  start on the section 11 network/hardware profile. Freeze a byte ceiling that makes the setup
  budget physically possible. Move only noncritical large payloads to signed on-demand packs; keep
  every capability registered and discoverable and do not delete product scope to hit the number.
- Select and spike the real GlassHive process topology. The current runtime starts reconciliation,
  callback, scheduler, lease and isolation work together; a separately startable provider slice is
  not current evidence. Either prove a provider-only profile with its own lifecycle/update owner or
  prove the full process can serve first chat within budget while wider-worker faults remain isolated.
- Select and spike the default worker containment mechanism. Same-UID host policy is not isolation.
  Prove a signed macOS sandbox/separate identity or a supported container/VM boundary, including
  user grants, revocation and denied-host reads. If only a container engine passes, declare it as a
  worker-activation prerequisite and keep it outside Ready to chat; do not claim Viventium activated
  without a contained worker.
- Prefer one supported credential path for first chat and the required worker. Do not copy an
  existing CLI credential home or make a second account/billing route an activation requirement.
- Define the component manifest and readiness schema once.
- Define the state schema, compatibility epoch, factory/user prompt split, migrator interface,
  recovery point, old-supervisor deactivation and minimum rollback contract before choosing final
  release directories.
- Stamp Prompt Workbench through the parent commit plus exact source/build manifest and remove its
  optional/default-off product rules; do not invent a nested pin only to satisfy wording.
- Select and license the exact official native agent body, Node, MongoDB, relocatable
  CPython/locked-wheel, voice/native and optional container artifacts, including usage versus
  distribution permission, signing order, entitlements, quarantine and dependency-isolation policy.
- Select the pinned Sparkle 2 app-update lane and exact Tailscale private-device integration;
  Viventium owns only their product-specific compatibility, health and permission adapters.
- Name the DMG host, runtime-pack host, Sparkle feed/manifest location, signing/release owner,
  support-policy owner and human authority for pausing new downloads. The kill switch must never
  disable an installed working product remotely.
- Time-box the real Xcode archive/normal-window/helper/`SMAppService` feasibility spike and include
  spawning the exact nested signed Node, Python, MongoDB and native-body binaries under hardened
  runtime/notarization with the planned entitlements and quarantine state. Record the result before
  building the shell.
- Inventory every credential format and define the Keychain/authenticated-encryption migration,
  rotation, recovery and reauthorization path.

**Exit:** no unknown component, process topology, worker-containment mechanism, state directory,
credential class, user surface, license, distribution owner, support boundary or dirty release input
remains; both first-answer transports are selected only after their exact gates pass.

### Phase 1 — Package one persistent first answer

**Outcome:** a clean Apple Silicon Mac reaches Ready to chat from a local unsigned engineering DMG,
then from the signed candidate.

- Build a real Xcode archive target from the existing SwiftUI UI as the `Viventium.app` setup/control
  shell. Replace its current
  `repoRoot`/`bin/viventium`/hand-written LaunchAgent lifecycle with a bundle-owned signed helper,
  stable IPC and `SMAppService` before calling it a public app.
- Package the required `scripts/viventium` lifecycle modules inside the immutable runtime and invoke
  them only as a signed-supervisor implementation detail. This is the single lifecycle logic, not a
  user shell dependency; do not port it to Swift unless the Phase-0 signed-helper spike proves a
  named requirement cannot be met.
- Reuse the existing branded browser `setup=accounts` flow and its accessibility evidence. The app
  opens and observes that route; it does not build a second native or WebKit provider form.
- Package pinned Node, production Viventium/LibreChat builds, accepted MongoDB runtime, config
  compiler, and supervisor; remove all end-user source builds and package-manager work.
- Package the Phase-0-selected GlassHive provider topology and approved official body needed by the
  subscription route, including the transport that passed `AR-044`. If the current full process is
  retained, its wider worker functions remain idle/ungranted and must not add Ready-to-chat failure
  dependencies; do not claim a provider-only slice unless one was implemented and proved.
- Package the separate Advanced API/custom-endpoint setup through the same account, Keychain,
  readiness and failure-state contracts. Prove its exact-artifact journey in this phase; API-only
  proof still cannot replace the subscription-first release promise.
- Implement the component manifest through idempotent per-component start/drain/stop/health adapters,
  singleton leases and separate Ready-to-chat versus Viventium-activated probes. Current launchers
  (`viventium_v0_4/viventium-librechat-start.sh`, `scripts/viventium/native_stack.sh`, and
  `viventium_v0_4/viventium-start-all.sh`) may be source adapters only when they cannot build,
  install, duplicate or restart unrelated work in the exact release path.
- Add local account creation, both first-answer routes, live probes, first prompt preservation,
  real incremental answer streaming, stop/start, and start-at-login. Package the saved-memory owner
  and prove save, reload and restart persistence here because saved memory is part of Ready to chat;
  deeper Recall/RAG readiness remains Phase 2.
- Implement the minimum transactional install/update path, legacy source-install takeover and
  last-known-good binary rollback needed to prove that the new app does not race or strand the old
  helper and services. Port, wire and repair the existing public native-payload pipeline rather than
  starting a second runtime updater. Phase 4 completes the full data and fault matrix.
- Keep every nonessential service out of the first-answer critical path without removing it from the
  payload or product.

**Exit:** both exact-artifact routes pass `install -> connect -> incrementally streamed answer ->
quit -> reopen -> same answer and saved memory` on a truly clean Mac with no developer tools. The
subscription and Advanced API routes are recorded separately; neither borrows the other's evidence.

### Phase 2 — Make the complete V spine ready

**Outcome:** the same install reaches Viventium activated.

- Package and supervise Prompt Workbench as mandatory; expose it in product navigation.
- Complete and supervise the full GlassHive worker/control plane from the Phase-0-selected topology;
  connect at least one approved Codex or Claude worker body and prove a contained real run, callback,
  artifact, restart, and continuation.
- Implement Workbench's signed factory-prompt plus user-override model, update reconciliation, and
  short-lived local session before enabling public prompt editing.
- Make GlassHive's app-owned, least-privilege worker profile the default. Prove that host files,
  credentials, browser/app sessions, network, other folders, and persistent changes stay unavailable
  until the matching user grant exists.
- Enable scheduler, Main continuity around the Phase-1 saved-memory owner, Recall's truthful building/degraded behavior,
  Life bootstrap, Feelings owner, backup metadata, and truthful status/repair.
- Add one quota governor across foreground Main, cortices, schedules and GlassHive: protect the live
  conversation where supported, pause eligible background work on exhaustion, preserve ledgers and
  show only verified reset/reconnect guidance.
- After one activation probe, prove that Workbench, workers and other heavy services can hibernate and
  return Ready on demand without losing schedules, state or callbacks.
- Prove Workbench factory/user/compiled/live sync, Developer source sync, prompt trace, exact-model
  eval, and a schedule -> GlassHive -> callback -> ledger -> Workbench loop.
- Prove the fallback route independently meets the Main Quality and Performance contract.

**Exit:** every item in the Viventium-activated definition passes after install and restart; neither
Workbench nor GlassHive is marked optional or silently skipped.

### Phase 3 — Complete account and capability activation

**Outcome:** users add powers instead of editing config.

- Add further approved OpenAI, Anthropic and future subscription routes after the Phase 0 primary
  route. Do not delay the proven primary route for provider breadth.
- Add further API/custom-endpoint providers through the Phase-1 Advanced boundary; do not rebuild
  its setup, Keychain, readiness or failure-state machinery.
- Turn the existing MCP/integration inventory into install/connect cards driven by adapter manifests.
- Prove Google and Microsoft connected-account lifecycle, then add other adapters by reuse and user
  demand; do not block release on catalog size.
- Make Telegram, other channels, calls/voice, Docker sandboxes, browser/computer use, code
  interpreter, web search, health sources, and remote access independently installable, testable,
  recoverable, and removable.
- Prove channel-neutral Main continuity with a synthetic adapter. Run Telegram acceptance only when
  Telegram is enabled for that release; it must never be a hidden prerequisite for Web, GlassHive or
  full activation.
- Treat voice as its own signed capability pack and run its exact audible/endurance gates; do not
  reduce it to a generic connection-card smoke test.
- Package the existing Tailscale private-device mode behind **Use from anywhere** and prove its
  install/connect, certificate, revocation, restart, outage and privacy paths. Keep NetBird and
  custom edge Advanced and Cloudflare Quick Tunnel experimental. Do not build a V-hosted relay.

**Exit:** every shipped card truthfully reaches Ready or one specific Needs-attention state; an
optional failure never breaks chat.

### Phase 4 — Safe upgrade, migration, and recovery

**Outcome:** activation survives the second install, which is usually harder than the first.

- Wire signed manifests, staged activation, health-gated switching, schema compatibility, and
  last-known-good rollback into the public app.
- Implement and prove a real public restore apply engine; metadata-only snapshots are insufficient.
- Prove existing-user migration for every state item in the inventory.
- Prove interrupted install/update, disk pressure, corrupt payload, offline start, port collision,
  sleep/wake, killed processes, expired auth, rollback, restore, and preserve-data uninstall.
- Produce redacted diagnostics and one-click repair bundles that contain no secrets or personal data.
- Inject failures before, during and after each writer quiesce, backup, component migration,
  semantic verification, old-supervisor deactivation and graph start; prove compatible binary and
  data recovery rather than pointer rollback alone.

**Exit:** upgrade and recovery tests pass on the exact installed artifact with record-count and
sample-continuity evidence.

### Phase 5 — Release candidate and public launch

**Outcome:** the public artifact, not a checkout, satisfies the product claim.

- Produce the digest-final signed/notarized/stapled app and signed runtime packs before final
  acceptance; verify Gatekeeper on clean Macs. Unsigned engineering results are supporting evidence
  only.
- Publish immutable manifest, checksums, SBOM, notices, compatibility and support policy.
- Run the complete acceptance matrix below on that exact downloaded digest. Any later signing,
  repackaging, manifest or payload change invalidates affected evidence and requires a rerun.
- Stage rollout with a kill switch for new downloads, never a remote switch that silently disables
  an installed user's local product.
- Publish only the tested digest after the owner reviews the generated evidence ledger and every
  blocker is closed. A capability may be deferred or removed from declared public scope only through
  section 1 change control without violating any `AR-*` or baseline `CAP-*` contract; editing the
  release label or deleting its ID is not closure.

## 11. Acceptance and release gates

Each row needs: requirement -> natural use case -> QA case -> exact artifact -> expected result ->
actual dated evidence -> remaining gap.

Timing boundaries are normative here. **Setup** starts at the first launch after the app is copied to
Applications and ends when Ready to chat has rendered and persisted a real answer. It includes every
required runtime-payload download, verification, install, service start and V-managed transition.
Only time waiting for human input inside the provider's authorization/MFA UI is subtracted from the
product-latency sample; total wall time is also reported. DMG bytes/download time and optional-pack
bytes are reported separately. Section 11 owns the maximum product budgets; Phase 0 may freeze
stricter component budgets and byte ceilings but may not loosen these limits without section 1
change control. Stable installer case `INST-025` runs at least 20 independent cold clean-state
setups **per declared hardware/macOS lane**, never pooled across lanes. Before each run, restore the
declared clean standard-user snapshot with no Viventium Application Support state, Viventium
Keychain items, helper/service registration, runtime/download cache or provider-body credential
home; retain only the fixed network profile and the exact downloaded DMG. Compute p95 by the
nearest-rank method (`ceil(0.95 × n)`) over all completed attempts, publish every raw product-latency
and wall-time sample plus excluded human-auth intervals, and make any timeout/failure an independent
gate failure rather than dropping or disguising it in the distribution.

| Gate | Minimum proof |
| --- | --- |
| Clean install | Fresh standard/non-admin account on both the oldest supported macOS latest patch and current stable macOS; no Git/Homebrew/Xcode/npm/pnpm/uv/Python/system Node/Docker; exact signed DMG reaches setup |
| First answer | The approved subscription route and the Advanced API route are each tested; a real live probe and answer render and persist across app restart. API-only proof does not satisfy the subscription-first release promise |
| Answer streaming | On the exact subscription and Advanced API LibreChat routes, a declared long answer produces at least two user-visible answer-text deltas before final completion; progress/tool/status events and post-completion fake chunking do not count; cancel, tool, error and persistence behavior pass; first-visible answer-content and completion are timed separately |
| Provider permission | The selected public account route has current documented support or written approval; copied client IDs and unofficial consumer-token flows are absent |
| Native body packaging | The selected body has separate allowed-use and distribution/install decisions, exact publisher artifact/version/digest, license/notices, signature/quarantine proof, V-owned credential home, compatibility and update/removal owner; no package manager or floating latest is used |
| One-account activation | Easy Install needs no Groq, xAI, fallback or second billing account; required background activation uses the connected primary or remains honestly deferred; product and cortex activation labels are distinct |
| Full V activation | Workbench, GlassHive, scheduler, continuity, memory/Feelings owners, Life bootstrap, recall state, update/recovery, backup metadata, status and repair pass |
| Built-in agents | Clean install seeds every declared built-in agent once; restart/update preserve user edits and do not duplicate or silently reset agents |
| Agent Builder parity | Create, edit, save, reload, duplicate, export/import where currently supported, and run an agent with declared model, instructions, files, tools, MCPs, actions, chains and permissions; existing agents and user edits survive install, restart, update and rollback |
| Worker plane | Real Codex or Claude worker starts, reports active state, completes, returns evidence/artifact, survives UI restart, and can continue |
| Worker permission | The Phase-0-selected OS sandbox, separate identity, container or VM boundary—not same-UID policy alone—prevents the default worker from reading an ungranted host folder/session/credential, using ungranted network/application access, or making an ungranted persistent change; grant and revoke paths pass visibly; any required engine is disclosed before worker activation and does not block Ready to chat |
| Conversation-provider failure | Killing the selected GlassHive provider role/process or native body preserves history and the drafted prompt, blocks only new inference, shows **AI connection needs repair**, and offers restart/reconnect without silent API or second-account fallback; a wider-worker fault does not kill the role |
| Prompt safety | Factory/user/source as applicable -> compiled -> live lineage matches; drift fails closed; exact-model old/new eval and real surface QA both pass |
| Prompt packaging | Factory prompts stay signed/read-only; user overrides survive update/rollback; a conflict is visible and recoverable; no durable URL/local-storage launch credential exists |
| Main continuity | One admitted snapshot/digest and authority set serves primary, fallback, Web, calls, channels, schedules and workers without context inflation or identity drift |
| Calls | Real microphone permission, call start, interruption, spoken response, continuity and restart/reconnect on the selected route |
| Channel parity | Web plus each release-declared channel independently preserves Main identity, snapshot, files, completion and failure honesty |
| Remote | Existing Tailscale private-device mode works without a custom domain; connect, certificate, revocation, restart and outage behavior pass; loopback stays default when disabled; experimental/Advanced modes are labeled truthfully |
| Optional failure | Docker, channel, MCP, voice, recall/search, remote and wider worker/project dependency failures do not block or falsely fail the active conversation provider |
| Existing-user migration | Conversations, agents, prompts, memory, Feelings, schedules, worker state, connections and artifacts are counted and sampled before/after |
| Reliability | Kill each component; supervisor detects, classifies, restarts only the safe target, and preserves unrelated work |
| Update/rollback | Good update, corrupt update, interrupted update, incompatible migration and last-known-good recovery are separately proved |
| Backup/restore | Public backup contains the declared state and a clean install can apply it, restart, and prove representative records and secrets policy |
| Uninstall | Preserve-data and remove-data choices are distinct, truthful and recoverable; app, helper, services and selected packs are removed without deleting retained user state |
| Security | Signature/notarization, archive traversal, downgrade/replay, loopback/LAN, OAuth state/PKCE, Keychain, secret/process/log scan and least permission pass; every nested executable passes hardened-runtime spawn, minimal-entitlement, signing-order, library-validation/JIT decision and quarantine/Gatekeeper checks |
| License and redistribution | Every shipped or downloaded dependency has approved provenance, license/notice treatment, redistribution/download route and update owner; unresolved items fail closed |
| Credential migration | Legacy connected-account ciphertext/root keys migrate to Keychain-rooted authenticated encryption; rotation, corrupt record, rollback, reauthorization and no-plaintext scans pass |
| Runtime packaging | Relocatable Python/locked wheels/native libraries and every other runtime start with the network disabled; no package manager, compile, missing signature or nonrelocatable path appears |
| Fork maintenance | A clean LibreChat fork commit has a known upstream base, reproducible overlay/build, replay result and installed hash; an upstream security patch can be applied within the recorded budget |
| Performance | On base M1/8-GB/256-GB hardware and a current base Apple-Silicon Mac, with a controlled 100-Mbps down/20-Mbps up/40-ms RTT profile: setup p95 under 5 minutes; 20-run warm-core p95 under 20 seconds; UI acknowledgement p95 under 250 ms; separately measured subscription/API cold first-visible answer-content p95 under 15 seconds and warm p95 under 5 seconds; the timer starts when the user activates **Send** and includes LibreChat, GlassHive startup, authentication and body-session creation; subscription warm p95 is no more than 25% or 2 seconds slower than matched API, whichever allowance is larger; completion is timed separately; `time-to-first-token` is reported only for a real incremental stream; activated-idle steady state under 1.5 GB; fixed 10-turn normal chat under 3 GB. Download/disk/CPU/energy and completion-time budgets are frozen in Phase 0 |
| Quota and rate limits | Exhaust the selected subscription allowance with foreground and background work: drafts persist, eligible background work pauses, reset/reconnect guidance is specific, foreground work is prioritized where supported, and no paid API/second account is used silently |
| Quality | Frozen multi-domain Main bank, exact-model Workbench evals, worker parity cases and natural real-user tasks meet Intelligence, Relevance, Usefulness and Alignment |
| Accessibility | Keyboard, VoiceOver, contrast, zoom, reduced motion, error focus and nontechnical wording pass in setup and readiness UI |
| Public safety | No secret, private prompt/data, real account identity, username, home path, hostname, private URL or machine-specific evidence in repo/artifact/log bundle |
| Native app boundary | Normal install/start/status/update works after the source checkout is absent; the signed helper owns its runtime through stable IPC and `SMAppService` |
| Distribution and support | DMG/runtime hosts, update feed, signing owner, download-pause authority, compatibility/support policy and privacy-safe local diagnostics export are named and exercised; no remote kill switch can disable an installed product |

The final physical Mac lane is mandatory for Gatekeeper, Keychain, `SMAppService`, permissions,
microphone/audio, sleep/wake, Docker Desktop, and full resource behavior. Test both macOS ends above
with standard/non-admin accounts. A VM may cover clean-state, failure, migration, and repeatability
lanes but cannot replace those physical checks. Performance budget changes require section 1's full
decision process before testing; a missed target cannot be edited into a pass afterward.

Parallel Work is not part of the `v0.5.0` ready claim unless its separate isolation, lifecycle,
security, quality, performance, operator-control, and real-user gates all pass. Until then, its UI is
dark and status says **Not released**, not “broken.”

### 11.1 QA ownership map

Phase 0 must generate the complete owner map from `qa/release-test-owners.yaml`, the runtime QA map,
owning feature docs and the committed child-capability manifest, then fail if any `AR-*`, `CAP-*` or
acceptance gate has no owner. The table below is the minimum routing contract, not a hand-maintained
exhaustive substitute. This document owns the release decision; each linked catalog owns executable
cases and dated evidence. The V0.5 product-design suite remains proposal/decision evidence only; it
cannot satisfy a runtime gate, and its older Groq-required activation proposal must be reconciled
against `AR-039` rather than imported into the release.

| Requirement group | Existing QA owners |
| --- | --- |
| Install, signed payload, provider lifecycle, readiness, migration, update, restore and native app | [Installer resilience](../../qa/installer-resilience/cases.md), including stable `INST-025` setup performance and `INST-026` bounded Hermes activation reuse; [stable runtime](../../qa/stable-dev-runtime/cases.md); [release readiness](../../qa/release-readiness/cases.md) |
| LibreChat chat, full V product navigation and Agent Builder | [agent configuration continuity](../../qa/agent-config-continuity/cases.md), [configuration alignment](../../qa/config-alignment/cases.md), [release readiness](../../qa/release-readiness/cases.md) |
| GlassHive first-answer provider, incremental output, concurrency and exact route identity | [GlassHive core provider](../../qa/glasshive-core-provider/cases.md), [agent streaming usage](../../qa/agent-streaming-usage/cases.md), [agent configuration continuity](../../qa/agent-config-continuity/cases.md) |
| GlassHive worker, permissions, persistence, evidence and takeover | [host workers](../../qa/glasshive_host_workers/cases.md), [standard QA](../../qa/glasshive_standard_qa/cases.md), [workspaces](../../qa/glasshive_workspaces/cases.md), [Watch](../../qa/glasshive_watch_desktop/cases.md) |
| Prompt Workbench factory/override, drift, trace and exact-model evaluation | [Prompt Workbench](../../qa/prompt-workbench/cases.md), [prompt architecture](../../qa/prompt-architecture/cases.md) |
| Main identity, context, fallback and cross-surface parity | [Main continuity](../../qa/main-continuity/cases.md), [agent configuration continuity](../../qa/agent-config-continuity/cases.md) |
| Saved memory, Recall/RAG, transcript continuity, backup and restore | [memory continuity](../../qa/memory-continuity/cases.md), [memory hardening](../../qa/memory-hardening/cases.md), [conversation Recall/RAG](../../qa/conversation-recall-rag/cases.md), [continuity operations](../../qa/continuity-ops/cases.md), [meeting transcript memory](../../qa/meeting-transcript-memory/cases.md) |
| Cortices, scheduling, Feelings and health context | [background agents](../../qa/background_agents/cases.md), [anti-sycophancy](../../qa/anti-sycophancy/cases.md), [Red Team](../../qa/red-team-cortex/cases.md), [scheduling cortex](../../qa/scheduling-cortex/cases.md), [periphery insights](../../qa/periphery-nightly-insights/cases.md), [emotional cortex](../../qa/emotional-cortex/cases.md), [Viventium-Health](../../viventium_v0_4/Viventium-Health/qa/cases.md) |
| Calls and voice | [modern voice](../../qa/modern-playground-voice/cases.md), [call hardening](../../qa/voice-call-hardening/cases.md), [streaming voice](../../qa/voice-streaming-first/cases.md) |
| Channels and connected accounts | [Telegram runtime](../../qa/telegram-runtime/cases.md), [connected-account handoff](../../qa/connected-accounts-handoff/cases.md), [MCP OAuth](../../qa/mcp-oauth/cases.md) |
| Conversation search, local search services and MCP/tool availability | [local Docker services](../../qa/local-docker-services/cases.md), [conversation Recall/RAG](../../qa/conversation-recall-rag/cases.md), [MCP OAuth](../../qa/mcp-oauth/cases.md) |
| Remote access | [remote access](../../qa/remote-access/cases.md) |
| License, distribution, support and public safety | [release readiness](../../qa/release-readiness/cases.md), [documentation implementation audit](../../qa/documentation-implementation-audit/cases.md), [public/private boundary](../../qa/privacy_publish_audit.md) |
| Parallel Work dark/release gate | [parallel orchestrator](../../qa/parallel-orchestrator/cases.md), [release readiness](../../qa/release-readiness/cases.md) |

### 11.2 Fail-closed requirement and capability ledger contract

Every `AR-*` row in section 4 and `CAP-*` family/member in section 6 is **OPEN** at this baseline.
Existing evidence may support a case, but none proves the new exact public artifact. Phase 0 must
assign every AR and generated child capability to a delivery state, stable natural use case and QA
case, then generate the evidence ledger from those owners. The evaluator must extract both ID sets,
compare capability IDs with the committed baseline, and fail if an ID or mapping vanishes. A newly
added requirement or product capability therefore cannot be missed by a hand-maintained list.

```yaml
activation_release_gate:
  requirements_source: "section 4 AR-* rows"
  capability_sources: "section 6 CAP-* baseline plus generated child manifest"
  exact_case_mapping_complete: false
  capability_mapping_complete: false
  baseline_capability_ids_preserved: false
  exact_signed_artifact_tested: false
  open_required_cases_allowed: false
  release_allowed: false
```

This block changes to `true` only from generated evidence after all required cases pass. Editing the
words by hand without matching owner cases and exact-artifact evidence is a release-process failure.

## 12. Red-team findings and rejected shortcuts

| Tempting choice | Why it is rejected for `v0.5.0` | What is still worth reusing |
| --- | --- | --- |
| Port Viventium onto OpenClaw | Adds migration and parity work before activation is solved; Viventium has different authority, continuity, Agent Builder, Workbench, GlassHive, calls, memory and scheduling contracts. OpenClaw's CLI/gateway are comparatively mature, but its own scorecard reports 68% overall Alpha and mixed maturity across companion app, App SDK, voice and realtime surfaces. | Signed-app onboarding, managed user-space runtime, launchd supervision, doctor/repair, channel/plugin adapter patterns |
| Merge Hermes | Duplicates worker, memory, scheduling, tool and sandbox systems and creates conflicting ownership. Hermes's product claims do not prove Viventium continuity parity. | Clear download choices, one-line fallback, one subscription portal, connection cards, platform breadth, sandbox backend UX |
| Build a new chat client now | Recreates a working branded surface, conversation persistence, streams, files, tools, MCP UI and Agent Builder before solving install. | Keep the V shell boundary so a later replacement is possible without data loss |
| Expose LibreChat installation | Makes the user understand our implementation and its Node/Mongo/Docker choices. | Pin and package LibreChat as an internal service with upstream drift tests |
| Require Docker on Mac | Adds a large third-party install, permissions, startup and failure boundary before chat. | Use Docker on demand for GlassHive workstations and container-only tools |
| Silently install Docker Desktop | Viventium cannot accept another product's terms for the user; commercial licensing and large resource costs vary by user. | Detect a supported engine, explain the boundary, open the official installer, then verify the selected capability |
| Remove features to make the payload small | Violates the complete-product goal and moves complexity back to later reinstalls/migrations. | Lazy start, downloadable exact capability packs and resource budgets |
| Start every feature by default | Recreates today's intertwined health noise and makes an optional failure look like product failure. | Component profiles and user-selected activation while keeping features installed/discoverable |
| Ship working unofficial subscription OAuth | Can break without notice and creates provider, legal, security and support risk. | One-click V account UX over approved direct adapters or official native bodies |
| Copy an existing Codex/Claude credential home | Couples Viventium to another installation, expands secret exposure, and is not the official body performing its own login. | Give the pinned body a V-owned credential home and let its supported login own tokens |
| Put a new V proxy in every chat request | Reimplements LibreChat's login, streams, files and tools and creates a new single point of failure. | Keep V API control-plane-only and add typed contracts at existing seams |
| Ship current Workbench source mode | A signed app cannot safely edit its own bundle or require a repository, Git, npm or uv; its reusable browser token is not a public auth boundary. | Preserve full source mode under Developer; use factory prompts plus user overrides in Product mode |
| Make unrestricted GlassHive the default | A useful first chat must not grant the model the person's full computer, browser sessions and credentials with approvals bypassed. | Keep full host mode as explicit Advanced power; default to an app-owned restricted workspace and task grants |
| Invent an updater or remote tunnel | Commodity signing, update, private-network, certificate and outage problems already have maintained solutions. | Pin Sparkle 2 and reuse the existing Tailscale adapter; own only V compatibility, consent, state and health |
| Sign after acceptance | Signing, notarizing or repackaging changes the artifact under test. | Test and publish one digest-final candidate |
| Treat pointer rollback as recovery | It cannot reverse incompatible data, stop old supervisors, or restore a consistent live database. | Reuse staged pointer activation inside a quiesced, journaled, data-aware migration transaction |
| Wait for every provider/channel/platform | Delays the only non-negotiable outcome and expands QA without improving the first Mac user. | Ship the adapter contract, Web plus primary accounts, then add catalog entries independently |
| Treat a source-present feature as released | Hides incomplete security, continuity and user paths. | Preserve the code, mark it Not released, and finish its own gates independently |

### 12.1 Hermes selective-reuse lane

**Decision: yes, reuse it.** Hermes Agent is MIT-licensed and permits use, copying, modification and
distribution when its copyright and license notice are preserved. The reviewed donor is official
commit `13f4cfebfafbce8ac9d1bf29f66731858ed638b5` from 2026-08-22. Dependencies, bundled assets,
branding and external services keep their own terms and need separate review.

| Hermes activation capability | Viventium treatment |
| --- | --- |
| Installer stage/progress protocol, resumable steps and fresh/existing-install tests | Copy or adapt the small independent code and tests where dependencies fit. |
| First-run onboarding state, provider/model connection cards and live readiness progression | Port the behavior into the existing V app and branded browser setup; do not ship the Hermes Electron UI. |
| Config check, schema migration and post-install hooks | Adapt behind the V config compiler and transactional journal. |
| Coordinated app/backend update UX and compatibility checks | Reuse the state model and tests; keep Sparkle plus V's signed immutable runtime activation instead of Hermes's Git-pull/rebuild path. |
| Pre-update snapshot, failure rollback and gateway/service restart | Reuse algorithms and failure cases where safe; apply V's database-aware migration, health and rollback rules. |
| Full backup/import, safe live SQLite copy and profile export | Reuse archive and consistency patterns; include every V continuity domain and keep Keychain secrets under V rules. |
| Preserve-data uninstall and reinstall recovery | Copy the behavior contract and fault cases into the V app-owned lifecycle. |
| Doctor, redacted diagnostics and specific repair actions | Reuse redaction, collection and failure-taxonomy patterns with V component health. |
| Always-on service registration and automatic restart | Port the behavior; the public Mac implementation remains V-owned `SMAppService`. |
| Desktop installer, DMG, signing/notarization and update CI | Reuse build/test patterns after license and dependency review; produce V-signed artifacts and V evidence. |

Do not copy Hermes's agent loop, chat client, worker plane, memory, scheduling, tools, gateway,
profiles, product branding or Nous Portal into the V runtime. Those duplicate Viventium and turn the
shortcut into a migration. Do not add Hermes as a runtime submodule or follow `main` at install time.

Implementation starts with a file-level donor ledger: `copy`, `adapt`, or `reject`; source path and
commit; license/notice; dependencies; V owner; tests; security differences; and measured work saved.
Port the donor contract and regression tests before its implementation. A copied feature passes only
through the exact V app, user state and clean-machine release gates.

### Alternative-host watch rule

Hermes, OpenClaw, Codex, Claude, LibreChat and other serious projects remain tracked references. They
may replace or supply one bounded component only after a same-input proof shows:

- lower total implementation and migration work;
- no loss against every affected `AR-*` requirement and inventory row;
- equal or better Quality and Performance on exact Viventium use cases;
- stable public interfaces, license, security and release posture;
- reversible migration and preserved user state.

Stars, forum attention, a polished demo, or a smaller repository cannot pass this gate alone.

## 13. Current evidence and honest baseline

### 13.1 What exists now

- The live local product has a branded Viventium chat with sessions, Agent Builder, Prompts,
  Feelings, Memories, files, bookmarks, MCP settings, microphone and call controls.
- Prompt Workbench is a real working standalone product surface with prompt flow, source/live drift,
  drafts, evals, schedules and prompt traces.
- GlassHive is running as a standalone worker control plane with host and Docker execution contracts,
  durable projects/runs, callbacks, artifacts and operator controls.
- The source installer has meaningful preflight, config compiler, exact MongoDB candidate, helper,
  health, connected-account handoff, rollback reference code, and extensive QA.
- Public repository history on `origin/main` at verified remote commit `1ec45b143b8e` already
  contains a much broader native-payload builder, assembler, bundled runtime, process guard,
  installer, signing/notarization workflows and tests. Those foundations are absent from this
  behind active checkout and make the verified remote the shortest release base after provenance
  audit; the valuable local delta must be replayed onto it without sacrificing user work.
- The Viventium LibreChat fork already contains connected-account, continuity, memory, Feelings,
  calls/channels, scheduling, GlassHive brokerage, and Agent Builder changes. This makes a wholesale
  host port a large migration, not a shortcut.

### 13.2 What is not release-ready

- The current public path still uses a source checkout and developer-oriented startup instead of one
  signed/notarized immutable app/runtime payload.
- The prior native-payload candidate is not releasable as-is: its exact clean guest run failed before
  registration and exposed a missing production dependency plus recovery, CSP and account-capability
  defects. Later source guards exist in public history, but no replacement digest completed the
  full install -> registration -> account -> answer -> restart journey. Reuse the code and the
  failures; do not reuse its readiness claim.
- The live operator status contains more than twenty component rows and can report optional account
  or service failures while core chat works. The release UI needs readiness levels and component
  dependency truth, not a flat all-or-nothing list.
- Historical launcher defaults start many optional services. This increases coupling, time, noise
  and failure surface.
- The exact clean-machine provider grant -> live first answer -> persistence journey is not closed.
- Public authorization for the current subscription OAuth implementations is not recorded.
- Workbench and GlassHive are live on the development machine but not yet packaged as mandatory
  exact release artifacts. Their older optional/default-off documentation and config contradict the
  current product decision.
- Dirty-path and diff counts changed during this review while other work continued, which proves
  that hand-copied counts cannot be the release ledger. At the dated graph check,
  `git rev-list --left-right --count origin/main...HEAD` returned `205 1`; the one local-only commit
  changes two component pins, while the active parent and both major nested components contain large
  valuable uncommitted deltas. This is a stale branch plus local work, not two independently mature
  branches to blanket-merge. Phase 0 must remeasure, preserve the current checkout, create the clean
  release base from verified `origin/main`, and replay every accepted local delta through the triage
  ledger. Neither a reset nor selective reconstruction of only the native payload is safe.
  `INST-022` is correctly **FAIL** until each item has an owner-approved `ship / defer / discard`
  disposition and commit/build/pin/installed hashes agree.
- The exact first-answer owner already records an open performance failure:
  `qa/glasshive-core-provider/cases.md` has `GCP-018` **FAIL** after one independent Web turn waited
  about 75 seconds behind another Codex conversation. Its route parity (`GCP-016`) and exact
  source/build/install agreement (`GCP-017`) remain **Not run**, alongside other open cases. These
  are explicit Ready-to-chat and release blockers, not missing future QA.
- Owner docs, compiler defaults and QA still contain those optional/default-off rules, and some Main
  and GlassHive completion gates assume Telegram. The new plan is not implemented until those owners
  are reconciled and channel-neutral gates exist.
- The current SwiftUI helper opens the chat in a browser but invokes `bin/viventium` from a recorded
  repository root and manages a hand-written LaunchAgent. It is valuable UI/reference code, not yet
  an app-bundled public lifecycle owner. It contains no embedded WebKit chat today.
- The existing branded browser account setup is implemented and already has keyboard, narrow-width,
  forced-colors, reduced-motion and Axe evidence under `INST-023`. Rebuilding it natively or in
  WebKit would discard evidence and add work; the release plan explicitly reuses it.
- The current Workbench applies reviewed drafts to repository prompt files and accepts a launch token
  from a URL before keeping it in browser local storage. Public packaging needs the signed
  factory/user-override and short-lived-session boundary in sections 7.4 and 9.
- Current GlassHive Codex launch paths include default-on unrestricted execution and no-approval
  modes. These are powerful trusted-developer settings, not an acceptable novice default. The
  consumer permission profile and denial tests are release blockers.
- Current GlassHive also projects an existing Codex credential file into worker-local state. It has
  not yet proved the V-owned official-body login required by the public account contract.
- The selected Codex/native-body dependency is not yet pinned into the public payload, approved for
  Viventium usage plus distribution/install, assigned an update owner, or proved under Gatekeeper
  and quarantine. Current app-server authority-replacement evidence fails, while current `exec`
  output is completed-event granularity and fails `AR-044`; no body transport is release-selected.
- The subscription/body route has no accepted cold/warm Send-to-first-visible-content or completion
  baseline yet, and subscription exhaustion under simultaneous chat, cortices and schedules has not
  passed a real product recovery journey.
- Connected-account keys currently use a legacy fixed-IV AES-CBC path and generated root values in a
  plaintext mode-0600 runtime environment file. File permissions reduce exposure but do not satisfy
  authenticated encryption, random nonce and Keychain-root requirements.
- GlassHive and Workbench currently require a live Python/`uv` environment, and native voice adds its
  own binary/model dependencies. The relocatable, locked, signed Apple-Silicon runtime decision is
  still open.
- The historical launcher can install Docker Desktop through Homebrew. A public app may not install
  it silently or accept its terms; the capability needs an explicit consent/license/resource path.
- MongoDB remains the chat database, but its publisher-download versus redistribution decision and
  exact signing/notarization treatment are not closed.
- Voice is real and first-class, but its complete signed pack, current component inventory and exact
  audible/endurance acceptance are not yet release artifacts.
- Main continuity and performance remain partial; current evidence includes context inflation and
  slow connected-service paths that must be corrected before release.
- Remote access already has local, Tailscale, NetBird, experimental Cloudflare Quick Tunnel and
  custom-edge modes. The recommended Tailscale path still lacks the exact signed-app, real-tailnet
  public acceptance required here; a new V-hosted relay is not the gap.
- Current public restore evidence is not a complete apply-and-recover engine.
- Current signed-payload reference code verifies, stages, switches and restores a binary pointer, but
  it is not yet the complete app install, data-migration, legacy-supervisor takeover or restore
  engine described here.
- Recall and Microsoft 365 currently need attention, while core chat, Workbench and GlassHive run.
  This proves the global health label is too coarse, not that all of Viventium is down.
- Parallel Work is present but not qualified for release.
- Current component checkouts, pins, builds and installed artifacts are not one clean, publishable
  release identity, as the measured dirty-component ledger and `INST-022` failure show.
- The large LibreChat fork does not yet have the clean upstream base, overlay/replay ledger and
  maintenance budget required for a sustainable pinned substrate.
- Signed/notarized artifact, Gatekeeper/Keychain/SMAppService physical QA, full migration, and
  health-gated public update/rollback remain open.

The current release status is therefore **PARTIAL / NOT RELEASE READY**. The main gap is activation
and product packaging, not missing agent intelligence and not the choice of a new host.

## 14. External evidence policy and current sources

Before a task relies on an external project, re-open its official documentation and release/source
reference. Record the checked date, exact version or commit, URL, conclusion, and any uncertainty in
the relevant implementation or QA evidence. Recheck release-sensitive facts at release freeze even
if they were checked earlier. Use primary vendor/project sources for capability, security, license,
install and support claims; use forums and trends only to discover failure patterns.

Sources checked on 2026-08-22 and rechecked for the Hermes reuse decision on 2026-08-23:

- [Hermes Agent product and install page](https://hermes-agent.nousresearch.com/) and
  [Hermes Desktop guide](https://hermes-agent.nousresearch.com/docs/user-guide/desktop),
  [official repository and MIT license](https://github.com/NousResearch/hermes-agent), and
  [update/backup guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/updating.md) —
  desktop/terminal installation, current advertised platforms, connection, memory, scheduling,
  delegation, tools, sandbox backends, coordinated updates, snapshots, rollback, backup/import,
  export/uninstall, service restart and Nous Portal subscription. The reuse review pinned commit
  `13f4cfebfafbce8ac9d1bf29f66731858ed638b5`; Viventium must not float on “latest.”
- [LibreChat local installation](https://www.librechat.ai/docs/local) — official Docker bundle and
  direct Node/Mongo prerequisites.
- [LibreChat Agents](https://www.librechat.ai/docs/features/agents) and
  [LibreChat MCP](https://www.librechat.ai/docs/features/mcp) — Agent Builder, capabilities,
  permissions and OAuth-enabled MCP reuse.
- [OpenClaw macOS gateway setup](https://docs.openclaw.ai/platforms/mac/bundled-gateway) — signed app
  setup script, managed user-space runtime, LaunchAgent, version checks and repair path.
- [OpenClaw update guide](https://docs.openclaw.ai/install/updating),
  [backup guide](https://docs.openclaw.ai/install/backups), and
  [platforms](https://docs.openclaw.ai/platforms) — stage/swap/recovery patterns, Node/SQLite core,
  service installation and platform posture.
- [OpenClaw maturity scorecard](https://docs.openclaw.ai/maturity/scorecard) and
  [security guidance](https://docs.openclaw.ai/gateway/security) — current evidence-led maturity and its
  trusted-operator/host-execution boundary.
- [OpenAI: Codex with a ChatGPT plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
  and [ChatGPT versus API billing](https://help.openai.com/en/articles/8156019-is-api-usage-included-in-chatgpt-subscriptions-even-if-i-have-a-paid-chatgpt-account)
  — eligible ChatGPT plan sign-in for Codex and separate ordinary API billing; neither alone
  authorizes a third-party direct subscription client.
- [OpenAI Codex repository and install routes](https://github.com/openai/codex) — Apache-2.0 source,
  an official standalone Apple-Silicon release artifact, publisher installer, ChatGPT sign-in and
  API-key alternative. These make Codex the shortest native-body candidate, but Viventium still
  needs an explicit usage/distribution decision and exact publisher/signature/quarantine proof.
- [OpenAI Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
  — official browser/device authentication and API-key alternative; stable methods are the default
  generated surface, while named experimental methods require an explicit capability.
- [Anthropic: Claude Code with Pro or Max](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)
  and [Claude subscription versus API](https://support.claude.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
  — native Claude Code subscription use and separate general API billing.
- [Apple `SMAppService`](https://developer.apple.com/documentation/servicemanagement/smappservice) —
  app-bundled login items and LaunchAgents.
- [Apple notarization guidance](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
  — Developer ID, hardened runtime, notarization and stapling requirements.
- [Sparkle 2 documentation](https://sparkle-project.org/documentation/) — maintained macOS app
  updating, Xcode archive integration, Developer ID/notarization guidance and EdDSA update signing.
- [Docker Desktop license terms](https://docs.docker.com/subscription/desktop-license/) — the user
  must accept Docker's terms and larger commercial/government use can require a paid subscription.
- [MongoDB SSPL FAQ](https://www.mongodb.com/legal/licensing/server-side-public-license/faq) and
  [official Apple-Silicon tarball install](https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-os-x-tarball/)
  — Community Server license/redistribution facts and publisher archive path; Viventium still needs
  its own recorded distribution decision.
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve),
  [Serve command](https://tailscale.com/docs/reference/tailscale-cli/serve), and
  [HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates) — private
  tailnet HTTPS can front a loopback service without a user-owned domain, but needs a Tailscale
  account, access rules and HTTPS consent; certificate transparency can expose the selected tailnet
  and device DNS name, so onboarding and privacy QA are required.
- [Home Assistant installation-method decision](https://www.home-assistant.io/blog/2025/05/22/deprecating-core-and-supervised-installation-methods-and-32-bit-systems)
  — one supported appliance path, integrations after onboarding, and migration/backup discipline.

## 15. Decision log

| Date | Decision or correction | Evidence and effect | Contract / QA owner |
| --- | --- | --- | --- |
| 2026-08-22 | Keep LibreChat for `v0.5.0`; do not move to OpenClaw or Hermes. | Existing V product and fork inventory plus alternative-host evidence show packaging is the shorter path. Porting adds migration and parity risk. | `AR-004`, `AR-005`, `AR-021`, `AR-025`, `AR-034`, `AR-036`; V0.5 design, agent-config continuity, release readiness |
| 2026-08-23 | Prefer bounded Hermes activation code and test reuse before writing new V lifecycle machinery; do not merge the Hermes product or agent host. | The official repository is MIT and its pinned installer, onboarding, update, snapshot/rollback, backup/import, uninstall, service and diagnostics paths directly cover V's activation gap. Selective reuse reduces work while V keeps lifecycle, state and release authority. | `AR-001`, `AR-014`, `AR-016`, `AR-021`, `AR-038`, `AR-046`; installer resilience, release readiness and license matrix |
| 2026-08-22 | GlassHive is the required main worker plane. | It is first-party and independently running with durable work, callbacks and takeover. Older optional text is a Phase-0 conflict; workers may start lazily. | `AR-006`, `AR-017`, `AR-028`, `AR-037`; GlassHive owners |
| 2026-08-22 | Prompt Workbench is a mandatory product/release surface. | It owns prompt truth, drift, schedules, traces and exact-model evals. Older optional text is a Phase-0 conflict. | `AR-007`, `AR-029`, `AR-031`, `AR-037`; Prompt Workbench and prompt architecture |
| 2026-08-22 | Separate Ready to chat from Viventium activated. | This preserves a fast first answer without watering down the full product or hiding missing spine readiness. | `AR-001`, `AR-002`, `AR-003`, `AR-011`, `AR-017`, `AR-023`; installer resilience |
| 2026-08-22 | Telegram is optional; Web is the required first surface. | Channel-neutral tests preserve parity without forcing a niche account. Telegram runs only when release-enabled. | `AR-008`, `AR-009`; Main continuity and Telegram runtime |
| 2026-08-22 | Apple Silicon native app is the first public lane; Docker is on demand and other systems follow. | This narrows the supported release matrix without removing the later container portability path. | `AR-012`, `AR-013`, `AR-033`; installer resilience |
| 2026-08-22 | Signed DMG/app replaces Docker/Native parity as the primary release gate. | The old equal Docker/Native gate added first-use friction; only one digest-final signed candidate can release. | `AR-014`, `AR-023`, `AR-030`, `AR-035`; installer and release readiness |
| 2026-08-22 | Subscription-first uses the existing GlassHive provider adapter to an approved official native body. | Current direct OAuth works locally but public permission is unproved; current auth-copy worker is not safe. The selected route reuses GlassHive while the body owns login. No permission means the subscription-first release remains blocked. | `AR-010`, `AR-021`, `AR-028`, `AR-032`, `AR-039`; installer/provider lifecycle and GlassHive |
| 2026-08-22 | Do not prioritize size reduction. | Preserve the full product; use clear delivery states, prebuilds, hibernation and exact packs to control cost. | `AR-002`, `AR-013`, `AR-037`; V0.5 design and performance gate |
| 2026-08-22 | Remote remains optional and reuses the existing Tailscale path; no V-hosted relay is a `v0.5.0` requirement. | The owner already ships local, Tailscale, NetBird, experimental Cloudflare and custom-edge modes. Tailscale preserves a no-domain private-device route with less work, but still needs real-tailnet, consent, privacy and failure QA. | `AR-026`, `AR-033`; remote access |
| 2026-08-22 | Parallel Work is not a `v0.5.0` ready claim unless all separate gates pass. | Source presence and Docker execution do not prove safe multi-worker orchestration. Keep it dark. | `AR-027`; parallel orchestrator and release readiness |
| 2026-08-22 | Use the system browser for `v0.5.0` chat; do not make WebKit an activation dependency. | The helper already opens the branded product and has no WebKit. Embedding adds auth, files, audio, downloads, permissions and parity work. | `AR-005`, `AR-019`, `AR-030`; installer, chat and voice owners |
| 2026-08-22 | Treat the existing helper, Workbench write model and unrestricted GlassHive modes as development baselines. | Source inspection found checkout/shell coupling, source writes plus a local-storage launch token, auth copying and unrestricted/no-approval paths. | `AR-028`–`AR-032`; installer, Prompt Workbench, GlassHive and security gates |
| 2026-08-22 | Resolve primary provider, runtime, state, migration, update and permission contracts in Phase 0. | Deferring them would make the onboarding UI and payload layout depend on assumptions and cause rework. | `AR-010`, `AR-014`–`AR-018`, `AR-028`–`AR-035`; installer/release owners |
| 2026-08-22 | Keep V API v1 control-plane-only. | A new chat proxy would duplicate mature LibreChat behavior and become a single point of failure. | `AR-005`, `AR-020`, `AR-025`, `AR-034`; architecture and continuity owners |
| 2026-08-22 | Reuse Sparkle 2, publisher runtimes and the existing Tailscale remote mode; do not invent commodity plumbing. | Maintained solutions reduce security and lifecycle work while V keeps compatibility, state and health ownership. | `AR-021`, `AR-026`, `AR-033`; installer, remote and release readiness |
| 2026-08-22 | Use verified `origin/main` as the clean release base, then replay all accepted local deltas; do not reconstruct only the native-payload subset in the stale checkout. | The graph audit found 205 remote-only commits, one local-only two-line pin commit and a large uncommitted local delta. `origin/main` contains the newer builder/assembler/runtime/guard/installer/workflow foundations, but its prior exact payload failed before registration. Preserve those failures as regressions and never import its readiness claim. | `AR-001`, `AR-014`, `AR-018`, `AR-021`, `AR-023`, `AR-035`; installer resilience and release readiness |
| 2026-08-22 | Legacy credential storage must migrate before public release. | Current connected-account storage uses a fixed-IV legacy encryption path and plaintext generated root values; permissions alone are insufficient. | `AR-015`, `AR-018`, `AR-031`, `AR-032`; provider lifecycle and security gates |
| 2026-08-22 | Support starts with local redacted diagnostics and no automatic telemetry or remote disable control. | This preserves local ownership and privacy while still giving a supportable artifact; any upload path needs separate consent and review. | `AR-040`; release readiness, public safety |

### 15.1 Corrections from adversarial review

These records apply the section 1 change-control fields to the material gaps found after the first
draft. “Challenge” records the strongest argument against the corrected decision.

| Date | Exact old/uncertain state -> corrected decision | New evidence and source date | Product effect | Challenge and resolution | Requirement / QA |
| --- | --- | --- | --- | --- | --- |
| 2026-08-23 | All Hermes porting appeared forbidden -> only a wholesale host/runtime port is forbidden; bounded activation reuse is the preferred first option. | Official Hermes repository, MIT license, Desktop, install, update, backup/import, uninstall and diagnostics source at commit `13f4cfebfafbce8ac9d1bf29f66731858ed638b5`; checked 2026-08-23. | Shortens activation work without migrating chat, agents, memory, workers or user state. | Challenge: Hermes uses Electron plus source/Git update paths and cannot be dropped into the signed V app. Resolution: reuse small independent modules, contracts and tests; port UI/service behavior into SwiftUI, Sparkle, `SMAppService` and V's immutable runtime. | `AR-001`, `AR-014`, `AR-016`, `AR-021`, `AR-038`, `AR-046`; installer resilience and license matrix |
| 2026-08-22 | Target diagram implied the proposed four-door V0.5 shell -> `v0.5.0` is the packaging release of the existing branded LibreChat product; four-door shell remains proposed. | V0.5 architecture/product docs and QA label that shell proposed and not runtime truth; checked 2026-08-22. | Avoids an unplanned UI rewrite and preserves current surfaces. | Challenge: the newer shell may be a better product. Resolution: it needs a separate owner decision and parity plan; activation cannot assume it. | `AR-001`, `AR-002`, `AR-005`; V0.5 design, release readiness |
| 2026-08-22 | First-answer route was conditional -> subscription-first uses LibreChat -> GlassHive provider -> approved official native body; Advanced API is separate. | Current config enables the GlassHive Core provider; provider authorization remains unproved; checked 2026-08-22. | One account owns chat and worker login; full worker plane can warm later. | Challenge: direct provider is a smaller critical path. Resolution: current direct consumer OAuth is not approved and API-only fails the fixed subscription outcome; an approved direct route may replace it through change control. | `AR-001`, `AR-006`, `AR-010`, `AR-028`, `AR-039`; provider lifecycle, GlassHive |
| 2026-08-22 | Provider approval appeared after dependent build work -> permission/native-body method proof is a Phase 0 exit. | OAuth route inspection and current official provider docs; checked 2026-08-22. | Prevents building onboarding around a route that cannot ship. | Challenge: approval can run in parallel. Resolution: research can, but no dependent UX/payload decision freezes before the outcome. | `AR-010`, `AR-021`, `AR-022`; provider lifecycle |
| 2026-08-22 | Setup ownership could imply a new native/WebKit flow -> V app reuses the existing branded browser `setup=accounts` flow. | Existing React flow plus `INST-023` accessibility evidence; current helper has no WebKit; checked 2026-08-22. | Preserves tested onboarding and removes a duplicate client. | Challenge: one native window looks smoother. Resolution: system-browser OAuth is already normal; embedding adds cookies, files, audio, permissions and accessibility parity work. | `AR-001`, `AR-005`, `AR-030`; `INST-017`, `INST-023` |
| 2026-08-22 | Plan claimed a missing managed remote path and implied a hosted relay -> reuse Tailscale for private enrolled devices; no V-hosted relay in `v0.5.0`. | Remote owner already defines Tailscale, NetBird, Cloudflare experiment and custom edge; official Tailscale docs rechecked 2026-08-22. | Preserves remote use without creating a cloud service. | Challenge: arbitrary browsers still need a public edge. Resolution: that is Advanced/future scope; the initial promise is the user's enrolled devices with truthful consent. | `AR-026`, `AR-033`; remote access |
| 2026-08-22 | Workbench was called pinned without a release identity -> it remains parent-tracked and gets an exact source/build manifest stamp. | `components.lock.json` omits it while the parent tracks its files; checked 2026-08-22. | Makes release identity enforceable without repository surgery. | Challenge: make it a nested repo. Resolution: that adds migration and process work with no activation benefit. | `AR-007`, `AR-014`, `AR-029`; Prompt Workbench, `INST-022` |
| 2026-08-22 | App and scripts were both described as lifecycle owner -> app owns the user surface; one signed supervisor reuses packaged `scripts/viventium` lifecycle logic. | Helper currently delegates to `bin/viventium`; installer owner assigns lifecycle to `scripts/viventium`; checked 2026-08-22. | No Swift rewrite and no two supervisors; checkout dependency is removed. | Challenge: a pure native supervisor is cleaner. Resolution: it duplicates working lifecycle logic before activation is solved. | `AR-016`, `AR-030`, `AR-034`; installer resilience |
| 2026-08-22 | Intel policy and separate activation-classifier credential were implicit -> Apple Silicon only, with Intel data/export safety; Easy Install needs no second inference account. | `INST-020`/`INST-023` show Intel unproved; compiler already waives the extra activation secret for `express`; checked 2026-08-22. | Narrows the public matrix without deleting data and removes a hidden onboarding bill/account. | Challenge: this reduces platform reach and classifier redundancy. Resolution: both can return later as declared profiles; neither may block the Mac activation goal. | `AR-012`, `AR-018`, `AR-039`; installer/compiler QA |
| 2026-08-22 | License and redistribution were tasks but not a stable release requirement -> `AR-038` and a fail-closed gate now own them. | License matrix flags MongoDB/Meilisearch and pack notices; checked 2026-08-22. | Prevents an install artifact that cannot legally or safely ship. | Challenge: publisher downloads avoid most redistribution work. Resolution: downloads still need provenance, terms, notice, version and update ownership. | `AR-014`, `AR-038`; license matrix, release readiness |
| 2026-08-22 | Native body was named as a route but not a payload owner -> Codex is the first candidate with a separate usage/distribution/install/signing/update gate. | Official Codex repository exposes an Apache-2.0 Apple-Silicon publisher artifact and ChatGPT login; current provider docs do not by themselves authorize Viventium's commercial distribution/use; rechecked 2026-08-22. | Closes the most important hidden first-answer dependency before packaging. | Challenge: ask users to install Codex themselves. Resolution: that weakens one-click activation; publisher download or bundling must be approved and product-owned, otherwise release stays held. | `AR-010`, `AR-038`, `AR-041`; provider, license and runtime packaging QA |
| 2026-08-22 | GlassHive was both optional-failure and subscription core -> distinguish the logical conversation-provider/body role from wider worker readiness and add route-specific latency budgets. | GlassHive owner shows synchronous body/session startup; Claude review confirmed the architecture but exposed the failure/latency ambiguity; checked 2026-08-22. | Chat history and drafts remain usable on provider failure; delegated-work failure stays independent; slow activation cannot hide behind a general RAM/startup gate. | Challenge: a direct API route is simpler and faster. Resolution: it is preserved under Advanced and measured side-by-side, but it cannot replace the subscription promise silently. | `AR-003`, `AR-006`, `AR-017`, `AR-041`; provider failure, performance and GlassHive QA |
| 2026-08-22 | Outer signing implied nested executables would work -> every child binary now needs an early hardened-runtime/entitlement/quarantine spawn proof. | Apple signing/notarization guidance plus current Node/Python/Mongo/body payload design; rechecked 2026-08-22. | Moves a common late macOS failure into Phase 0 before the payload freezes. | Challenge: sign first and debug failures later. Resolution: late entitlement changes invalidate the exact artifact and can force packaging redesign. | `AR-014`, `AR-035`, `AR-042`; native app security and exact-artifact QA |
| 2026-08-22 | Provider exhaustion had a failure label but no product behavior -> foreground protection, background pause and no silent paid fallback are release gates. | One consumer account is expected to serve chat plus background work; current failure taxonomy already distinguishes quota/rate limit; checked 2026-08-22. | Prevents background automation from making the product appear broken or generating surprise API spend. | Challenge: provider policy may not expose priority or reset data. Resolution: Viventium still pauses work and reports only verified reset/reconnect facts; unsupported priority is explicit. | `AR-010`, `AR-011`, `AR-043`; provider lifecycle, scheduler and cognition QA |
| 2026-08-22 | Supported `exec` was treated as the likely release transport -> no native-body transport is selected until real incremental answer deltas and per-turn replacement authority both pass. | GlassHive owner evidence reports completed-event visibility rather than answer-token streaming; adversarial review rechecked 2026-08-22. | Preserves LibreChat streaming instead of disguising a completed answer as chunks; records first-visible content and completion separately. | Challenge: completed answers are simpler. Resolution: that removes an existing product behavior and violates no-loss; release stays held until the exact route streams. | `AR-003`, `AR-005`, `AR-044`; provider transport, performance and chat QA |
| 2026-08-22 | The broad feature table could lose a member without failing an AR-only evaluator -> stable capability families, generated permanent child IDs and a baseline-diff gate now apply. | Fresh document audit found AR extraction could miss removal of Agent Builder or another named capability; checked 2026-08-22. | Turns “keep it all” into a fail-closed release control and adds explicit Agent Builder parity. | Challenge: the ledger adds paperwork. Resolution: generation comes from product truth; silent feature loss is the larger cost. | `AR-002`, `AR-005`, `AR-045`; capability ledger and Agent Builder QA |
| 2026-08-22 | Advanced API setup appeared after full V activation -> both first-answer routes now ship and pass in Phase 1. | Phase ordering conflicted with the first-answer gate and ordered actions; checked 2026-08-22. | Users get the promised subscription default and Advanced alternative from the same releasable artifact. | Challenge: API can wait because subscription is primary. Resolution: Advanced is a fixed activation requirement and a measured control route, not later provider breadth. | `AR-001`, `AR-010`, `AR-023`; provider lifecycle and installer QA |
| 2026-08-22 | A separately startable GlassHive provider slice was assumed -> Phase 0 must choose a proved provider-only profile or the current full-process topology with internal fault isolation. | Current runtime constructs the full worker/project service and starts reconciliation, callback, scheduler, lease and isolation threads; inspected 2026-08-22. | Removes fictional architecture while keeping GlassHive on the first-answer route. | Challenge: splitting now gives a cleaner graph. Resolution: split only if the full process fails latency or failure isolation; otherwise reuse it. | `AR-006`, `AR-017`, `AR-021`; GlassHive lifecycle and provider-failure QA |
| 2026-08-22 | Saved memory was required for Ready to chat but scheduled for Phase 2 -> its owner, persistence and restart probe move to Phase 1. | Readiness and phase exits conflicted; checked 2026-08-22. | The first release state is truthful; deeper Recall/RAG still activates later. | Challenge: memory can warm later. Resolution: Recall can, but the declared saved-memory function cannot be absent from Ready to chat. | `AR-001`, `AR-018`, `CAP-MEMORY`; installer and memory QA |
| 2026-08-22 | Provider timing could start after cold GlassHive/body startup -> the clock now starts at the user's Send action and includes the whole route. | GlassHive owner timing currently excludes blocked cold bootstrap; adversarial review rechecked 2026-08-22. | Prevents a fast metric from hiding the user's largest wait. | Challenge: provider-only timing helps diagnosis. Resolution: keep it as a secondary trace, never the product claim. | `AR-003`, `AR-011`, `AR-044`; performance QA |
| 2026-08-22 | Least-privilege host workers relied on policy -> Phase 0 must prove an OS sandbox, separate identity, container or VM boundary. | GlassHive owner and QA state that same-UID processes can still see host data; inspected 2026-08-22. | Makes worker isolation real; a required engine may gate worker activation but never first chat. | Challenge: a container adds activation friction. Resolution: first spike the signed macOS boundary; disclose a container prerequisite if it is the only proof, never claim containment without it. | `AR-006`, `AR-028`, `AR-037`; worker permission QA |
| 2026-08-22 | “No shell dependency” contradicted reuse of lifecycle scripts -> packaged internal scripts remain behind the signed supervisor; checkout/user shell dependence is forbidden. | Section 7 and payload wording disagreed; checked 2026-08-22. | Reuses tested lifecycle logic without exposing scripts or duplicating it in Swift. | Challenge: a native port looks cleaner. Resolution: port only if the signed-helper spike finds a named unmet requirement. | `AR-016`, `AR-021`, `AR-030`; native app and installer QA |
| 2026-08-22 | The checkout was called materially divergent and native files were to be selectively ported -> verified `origin/main` becomes the clean release base and every accepted local delta is replayed onto it. | `git rev-list --left-right --count origin/main...HEAD` returned `205 1`; the sole local commit is a two-line pin change while the large current value is uncommitted; checked 2026-08-22. | Uses all newer public work, preserves local work, and avoids rebuilding hundreds of files by hand. | Challenge: replaying a dirty delta is risky. Resolution: snapshot and triage first in a separate worktree; never reset the current checkout. | `AR-014`, `AR-018`, `AR-021`, `AR-023`; release baseline and installer QA |
| 2026-08-22 | The fixed first-answer route lacked its exact QA owner -> `glasshive-core-provider` is mandatory and its recorded `GCP-018` failure plus `GCP-016/017` open cases are named blockers. | Owner map and case catalog inspected 2026-08-22. | A fail-closed ledger can no longer report clear while the actual provider route is slow or unproved. | Challenge: new release tests will replace old failures. Resolution: replacement evidence closes them; omission cannot. | `AR-003`, `AR-006`, `AR-023`, `AR-044`; GlassHive core-provider QA |
| 2026-08-22 | The manual QA-owner table omitted memory, restore, cortices, health and other gates and used a proposal-only V0.5 suite for runtime proof -> owner routing is generated from the canonical maps and capability ledger; the proposal suite cannot pass runtime. | `qa/release-test-owners.yaml`, runtime QA map and the V0.5 suite scope inspected 2026-08-22. | Every requirement/gate must resolve to executable dated evidence; the old Groq-required proposal cannot override one-account activation. | Challenge: one generated map can itself drift. Resolution: compare all four sources and fail on unmapped IDs rather than trusting one list. | `AR-023`, `AR-039`, `AR-045`; QA operating contract |
| 2026-08-22 | Health and conversation search were absent from the no-loss list -> `CAP-HEALTH` and `CAP-CHATSEARCH` are explicit baselines. | Component lock, health owner/runtime/QA and launcher/search contracts inspected 2026-08-22. | Packaging cannot silently drop the health component or private conversation search. | Challenge: neither should slow first answer. Resolution: both remain real product surfaces with on-demand/degraded states, not critical-path processes. | `AR-002`, `AR-037`, `AR-045`; health, local services and chat QA |
| 2026-08-22 | Five-minute setup lacked start/stop and byte boundaries -> first app launch to persisted Ready-to-chat answer is normative and includes every required runtime download/start; only provider human-input wait is subtracted and total wall time remains visible. | Metric audit and payload topology reviewed 2026-08-22. | Prevents large hidden downloads or bootstrap time from falling outside the activation claim. | Challenge: user download speed and MFA vary. Resolution: use the fixed network profile, report DMG/download and total wall time separately, and freeze a feasible core-byte ceiling. | `AR-001`, `AR-003`, `AR-023`; installer and performance QA |
| 2026-08-22 | Setup p95 had boundaries but no reproducible sampling rule -> `INST-025` requires at least 20 independent cold clean-state runs per hardware/macOS lane, nearest-rank p95, raw samples and fail-closed timeouts. | Final architecture audit found a single or pooled run could otherwise be labeled p95; checked 2026-08-22. | Makes the five-minute activation claim independently auditable. | Challenge: the matrix is expensive. Resolution: clean snapshots automate repetition; pooling lanes or omitting failures would make the market claim meaningless. | `AR-001`, `AR-003`, `AR-023`; `INST-025` |

## 16. Absolute next actions

Do these in order; do not begin a wholesale OpenClaw/Hermes host port or new chat UI in parallel.
The bounded Hermes activation donor lane in section 12.1 is required inside these lifecycle steps.

1. Freeze a clean, recoverable baseline and reconcile every owner: component commits/pins/builds,
   LibreChat upstream/overlay, installed versions, full feature/data/auth inventory, schema/defaults,
   proposed V0.5 scope, Easy Install labels, Intel policy, QA cases, license matrix, dirty-work
   triage, generated AR/CAP ledger and fail-closed evaluator. Preserve the current checkout, create
   the release worktree from freshly verified `origin/main`, then replay every accepted local delta
   and keep the prior native-payload failures as regressions before designing new machinery. Pin the
   reviewed Hermes donor revision and complete its file-level `copy / adapt / reject` ledger before
   implementing any new activation mechanism that Hermes may already provide.
2. Prove provider permission and the selected subscription route: branded LibreChat -> GlassHive
   provider -> official native body in a V-owned credential home. Select a supported transport only
   after per-turn authority and real incremental answer streaming pass. Prove Advanced API
   separately; separately approve the body's usage and distribution/install route. If any gate
   fails, hold the release; do not build around assumed permission or require a second account.
3. Define the control-plane-only V API, component graph, idempotent lifecycle/leases, readiness,
   GlassHive provider/full-process topology, real worker containment, permission grants,
   immutable/mutable data layout, compatibility epoch, migrator, legacy-supervisor takeover,
   recovery point and rollback contract.
4. Select and license the exact Codex candidate body, Node, MongoDB, relocatable Python/wheels,
   voice/native and container artifacts; pin Sparkle 2 and the existing Tailscale remote path; name
   distribution/update/support owners and design Keychain migration plus nested signing,
   entitlements and quarantine.
5. Turn the existing SwiftUI UI into a real signed Xcode Viventium setup/control app with bundle-owned
   helper/IPC and `SMAppService`; reuse the existing branded browser account setup and chat.
6. Build the immutable Apple Silicon runtime payload: pinned Node, production LibreChat/Viventium,
   accepted MongoDB, parent-stamped prebuilt Workbench, self-contained GlassHive/Python, and exact
   service versions; repair and extend the existing native-payload builder/assembler/runtime/workflow.
7. Close both exact-artifact journeys: install -> local user -> approved subscription -> live probe
   -> incrementally streamed answer -> restart -> same answer and saved memory, and the separate
   Advanced API path. Pass cold/warm Send-to-first-visible-content and completion budgets,
   provider/body failure repair, quota exhaustion and no-silent-spend cases.
8. Close full activation: Workbench factory/override/update/eval/trace, GlassHive least-privilege real
   worker/grant/callback/artifact,
   scheduler, Main continuity and performance, Life bootstrap, memory/Feelings, recall state,
   backup/restore, status and repair.
9. Ship the full modular powers: signed voice pack, channel-neutral parity plus selected channels,
   MCPs, consented Docker sandboxes, tested Tailscale private-device access and other integrations; wire
   schema-safe update/migration/rollback/restore/uninstall. Never force Telegram.
10. Run the exact downloaded, signed/notarized artifact through clean physical Apple Silicon Mac,
    migration, failure, security, performance, accessibility and full-product QA; release only from
    that evidence ledger and publish only its tested digest.

## Exact Onboarding And Reconciliation Acceptance

`ONB-003` keeps first-owner setup sparse, premium, dismissible, jargon-free, and conditional on a
real unmet setup need. It reuses the branded LibreChat `setup=accounts` and Connected Accounts
components, preserves a drafted prompt through sign-in, denial, retry, reload, and completion, and
returns the user to that draft. A second native, WebKit, or chat-client setup surface is forbidden.
`INST-017`, `INST-023`, `INST-UC-013`, and `INST-UC-017` own acceptance.

`ONB-005` requires one provider/channel lifecycle contract: connect, cancel or deny, test, wrong
account, expired or revoked authorization, quota/rate/network failure, retry, reauthorize, repair,
disconnect, upstream revoke, local-secret deletion, restart, and a first plus second persistent
answer. Every state preserves unrelated accounts and user state and presents one specific truthful
action. `INST-009`, `INST-010`, `INST-017`, `INST-UC-010`, and `INST-UC-011` own acceptance.

`ONB-009` requires release QA to use disposable synthetic identities or explicitly isolated,
authorized state without contaminating a personal account or public evidence. The branch matrix is
explicit: new and existing user; desktop and mobile browser; keyboard, screen reader, reduced motion,
and supported contrast or zoom; provider lifecycle; Life setup and failure edges; Telegram text,
media, and voice; Call, Wing, and Listen-Only; memory, recall, Scheduling Cortex, Prompt Workbench,
GlassHive, and worker paths; restart, upgrade, backup/restore, and rollback; LAN and off-LAN; exact
source/build/install artifacts; cleanup; public safety; and every supported platform. Each branch
has direct candidate-bound evidence and its own status. `INST-031` / `INST-UC-023` owns acceptance.

`ONB-010` begins with verified recoverable backups of every relevant branch, worktree, commit, and
private-state domain. It classifies every delta, replays only owner-accepted changes onto fresh
current component and parent main branches, and avoids blanket merges, resets, or treating dirty
working bytes as shipped. Completion requires source commit, component publication, parent pin,
compiled or prebuilt artifact, installed runtime identity, and fresh QA to agree, with a restore
drill proving the backup before cleanup. `INST-032` / `INST-UC-024` owns acceptance.

<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:START -->
## Stable requirement declarations

Each line is the canonical public owner declaration for one stable requirement ID. Detailed sections supply implementation context; they must not narrow or contradict these declared outcomes.

CC-060: Activation order: foundations/tests → side-by-side runtime → real QA → independent review → leak scan → component commit/pin/artifacts → installed runtime → drift check → private schedule activation → observe silent/delivered/interrupted/restart. Rollback disables the private schedule and keeps shared reliability fixes.
CORE-016: The public install and activation experience has one obvious, trustworthy, minimal path. Reuse proven upstream/native mechanisms and isolate Viventium-specific value; Native/Docker profiles may remain internal execution or recovery paths, not competing public choices.
GOV-014: When implementation delivery asks for the latest local Viventium to be running, start it and prove the active process/config/build are the exact candidate; “source changed” alone is not delivery.
ONB-001: A nontechnical Apple Silicon Mac user gets one signed/notarized Viventium app and immutable payload, connects one approved AI account, receives a real persistent first answer, and leaves Viventium running without Terminal, Git, Homebrew, developer tools, package managers, system Node/Python, source compilation, or Docker before that answer.
ONB-002: Activation preserves the complete Viventium product and existing user state. Optional voice, channel, search, sandbox, and worker capabilities can activate later and fail independently; they cannot block the first useful chat or erase/downgrade existing behavior.
ONB-003: First-owner setup is sparse, premium, dismissible, jargon-free, and only appears when needed. Reuse the existing branded LibreChat `setup=accounts` flow and its Connected Accounts components; do not create a second native/WebKit/chat client. Preserve a drafted prompt across account setup.
ONB-004: Recommend OpenAI/ChatGPT/Codex or Anthropic/Claude subscription connection only where the provider officially permits that route. Keep API keys and Groq/other providers under Advanced. A connection becomes Ready only after a bounded live probe; fallback uses the configured typed chain and Ready authorized routes, never an invented “fastest” provider or silent paid-account switch.
ONB-005: Provider/channel lifecycle covers connect, cancel/deny, test, wrong/expired/revoked account, rate/quota/network failure, retry, reauth, repair, disconnect, upstream revoke, local-secret deletion, restart, and a first plus second persistent answer. Every state has one specific truthful action and preserves unrelated state.
ONB-006: After first answer, the same Main, continuity, memory, calls, Wing, Listen-Only, Telegram, workers, and local-phone/remote-use paths remain first-class and reliable. Packaging may lazy-start them but may not replace, silently narrow, or fake their readiness.
ONB-009: Release QA uses disposable/synthetic or properly isolated authorized state, never contaminates the personal account or public evidence. It covers new/existing user, desktop/mobile browser, keyboard/screen reader/reduced motion, provider lifecycle, Life edge cases, Telegram text/media/voice, Call/Wing/Listen-Only, memory/recall/scheduling/Workbench/GlassHive, restart, upgrade, backup/restore/rollback, LAN/off-LAN, exact artifacts, and the supported platform.
ONB-010: Preserve all relevant branches/worktrees/commits/private state with verified recoverable backups, classify every delta, reconcile surgically onto fresh current component and parent mains, then require source commit→component publication→parent pin→compiled/prebuilt artifact→installed runtime→fresh QA agreement. Never use risky wholesale merges or treat dirty working state as shipped.
ONB-011: One machine-readable product/service registry generates coverage and status instead of adding another hand-maintained master ledger. CI enforces source→pin→artifact→installed→QA consistency. Incrementally split the launcher, CLI, and compiler into a typed supervisor and small service modules only where that removes measured coordination/failure risk; do not launch a wholesale rewrite.
<!-- VIVENTIUM-STABLE-REQUIREMENT-DECLARATIONS:END -->
