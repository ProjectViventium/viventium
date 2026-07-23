# Open-Source Installer And Onboarding Research — 2026-07-18

## Research Boundary

This review compared active open-source/self-hosted AI and home-server products for patterns that
can improve Viventium's macOS Easy Install and onboarding. Three repositories were initially
shallow-cloned to disposable `<temp>` storage for static inspection only; nothing was run or copied
into Viventium. On 2026-07-20, six current shallow snapshots were retained in a separate private
inspection workspace outside every public repository so the comparison remains reproducible
without turning third-party code into shipped product code. GitHub stars are a directional adoption
signal, not proof of security, usability, or fitness. License constraints are treated as design
boundaries.

Scoring weights:

The numeric scores below are the audit team's directional judgments against these weights, not
measured usability outcomes or independent benchmarks. They are an organizing aid; inspected
behavior, maintenance, security, license, and Viventium fit control the recommendation.

- beginner first-run: 25%;
- recovery and lifecycle: 25%;
- security and privacy: 20%;
- integration onboarding: 15%;
- reusable licensing: 10%;
- activity/evidence: 5%.

## Ranked Inspiration

| Rank | Project | Score | Evidence-backed strength | Do not copy |
| --- | ---: | ---: | --- | --- |
| 1 | [Home Assistant](https://github.com/home-assistant/core) | 8.9 | First-class config flows, reauthentication, reconfiguration, repairs, and actionable issue lifecycles | It is architectural inspiration, not a desktop installer to transplant. |
| 2 | [Jan](https://github.com/janhq/jan) | 8.6 | Signed desktop delivery, hardware-aware choices, true progress, OS Keychain, provider credential testing | Optional verification skips and machine-ID-derived secret fallback are too weak. |
| 3 | [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | 8.3 | Clear provider/privacy cards and strong guided Telegram onboarding | Early onboarding still exposes too many choices; telemetry should not default on. |
| 4 | [Coolify](https://github.com/coollabsio/coolify) | 7.8 | Idempotent reruns, diagnostics, upgrade backup, rollback/downgrade | Root `curl | bash` and first-public-registrant patterns are wrong for local Easy Install. |
| 5 | [Ollama](https://github.com/ollama/ollama) | 7.7 | Small local-model install surface | It solves only a model-engine slice. |
| 6 | [Dify](https://github.com/langgenius/dify) | 7.5 | Plugin review checks and documented backup/migration | Modified license, branding restrictions, and UI patent concerns require inspiration-only use. |
| 7 | [Open WebUI](https://github.com/open-webui/open-webui) | 7.2 | Simple persistent-volume quick start and version-pinning guidance | Current license constrains branding; first-run setup is polished but shallow. |
| 8 | [n8n](https://github.com/n8n-io/n8n) | 7.0 | Provider-specific credential UX and community-package risk tiers | Sustainable Use License; inspiration only. |

Popularity snapshot observed on 2026-07-18: Ollama about 176k GitHub stars, Open WebUI 145k,
Home Assistant 89k, AnythingLLM 63k, and Jan 43k. Exact values change; product decisions should be
based on inspected behavior, maintenance, security, and license rather than stars alone.

The star counts above were manually observed on the linked repository pages; no separate GitHub API
response or timestamped popularity dataset was retained. They are dated directional context, not a
reproducible benchmark. The retained line-level source snapshots cover Home Assistant, Jan,
AnythingLLM, Coolify, Ollama, and Open WebUI. Dify and n8n were secondary public-repository/docs
comparisons only; no pinned local snapshot was recorded for either, so their scores must not be
treated as equivalent line-level inspection evidence or used alone for a release decision.

## Target Easy Install Sequence

The best common pattern is a short transactional path:

`preflight → protect existing setup → verify immutable release → install → start → health-check → local onboarding → first successful synthetic conversation → optional integrations`

Recommended visible stages:

1. Check this Mac.
2. Protect the existing setup.
3. Download verified components.
4. Configure the local runtime.
5. Start services.
6. Verify live health.
7. Open Viventium.
8. Connect a provider, optional if a useful local default exists.
9. Test the first conversation.

Every stage needs a stable ID, durable journal entry, measured progress where available, elapsed
time, sanitized details, safe cancel semantics, retry, and resume. Rerunning the same command should
resume or repair; it must not destroy state or restart blindly.

## Secure Bootstrap And Runtime Design

### Bootstrap

- Publish a small versioned bootstrap instead of executing mutable `main` directly.
- Verify checksum/signature/provenance before execution.
- Validate an existing target directory's remote identity before any fetch, checkout, or pull.
- Install exact application and component versions; record manifest, image digests, and SBOM.
- Use an install transaction journal with preconditions, mutation boundary, rollback point, and
  completion proof for every stage.
- Refuse to proceed if a complete recovery checkpoint cannot be created for an existing install.

### Minimal useful core

- Make the first useful local conversation the success condition, not “processes started.”
- Defer heavy shared services and optional channels until after the core is live.
- Detect hardware and prerequisites read-only before asking questions.
- Recommend one default while allowing Custom Settings Install choices later.
- Never bind services to `0.0.0.0` by default or expose first-registration publicly.

### Secrets

- Store host credentials in [Apple Keychain](https://developer.apple.com/documentation/security/keychain-services).
- Pass only narrowly scoped secret files/references into containers; follow
  [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/).
- The browser receives an opaque reference and status, never a raw credential.
- Logs, diagnostics, install journal, browser storage, generated examples, and QA artifacts must
  never contain token values.
- Disconnect, upstream revoke, and local-secret deletion are distinct explicit actions.

### OAuth

Native OAuth should use the system browser, authorization code flow with PKCE, a random loopback
redirect, state validation, least-privilege scopes, and refresh-token rotation. Do not use embedded
webviews or copy/paste authorization codes. Primary sources:

- [RFC 8252 — OAuth 2.0 for Native Apps](https://www.rfc-editor.org/rfc/rfc8252)
- [Google OAuth for installed apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Microsoft authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)

## Connection UX Contract

Each provider/channel card should expose:

- Connect;
- Test;
- Ready or degraded state;
- Reauthenticate;
- Reconfigure;
- Retry or Repair;
- Disconnect;
- upstream revoke when supported;
- explicit local-secret deletion.

Use stable states rather than feature-specific prose:

| State | Meaning | Required action |
| --- | --- | --- |
| `not_configured` | No usable account/credential reference | Offer one recommended Connect path. |
| `connecting` | Browser/device/token flow is active | Show cancel and safe retry. |
| `configured` | Required values exist but no live request has passed | Run Test; never call this Ready. |
| `ready` | A current least-privilege live self-test passed | Show last-tested time and capabilities. |
| `degraded` | Part of the adapter works | Name the failed capability and repair. |
| `needs_auth` | Authentication expired/denied | Reauthenticate without deleting setup. |
| `missing_scope` | Auth works but permission is insufficient | Explain and request only the missing scope. |
| `invalid_credential` | Provider rejected the credential | Replace/reconnect without exposing it. |
| `quota_or_rate_limit` | Provider accepted auth but cannot serve now | Show retry guidance and fallback. |
| `network_unavailable` | Provider cannot be reached | Preserve work and retry. |
| `dependency_unhealthy` | Local sidecar/service is unhealthy | Repair the dependency. |
| `unsupported` | Product does not implement the integration | Say so; do not show a fake config form. |
| `update_required` | Adapter/provider contract is incompatible | Offer a verified update path. |

Provider cards should plainly state whether work stays local or goes to a named company, account and
billing prerequisites, data destination, cost/quota implications, privacy-policy link, last live
test, and repair action.

## Integration Priorities

### 1. Telegram — supported first

AnythingLLM's guided Telegram flow is the strongest current reference. The Viventium flow should:

1. open or explain BotFather with numbered steps and optional QR/deep link;
2. accept a hidden token into LibreChat's server-encrypted channel record (the established Custom
   Settings operator path may continue using Keychain);
3. validate it with `getMe`;
4. use long polling for local Easy Install;
5. pair or allowlist explicit users/chats;
6. keep groups and inline mode off by default;
7. detect webhook/polling conflicts;
8. send a synthetic test and prove receipt;
9. prove restart persistence and disconnect/revoke behavior.

Telegram documents that polling and webhooks are mutually exclusive in the
[Bot API](https://core.telegram.org/bots/api).

### 2. Slack — guided Easy Install connection after first answer

Slack Socket Mode avoids a public inbound URL for a local runtime, but it still requires creating a
Slack app, an app-level token with `connections:write`, bot OAuth, and granular scopes. Viventium
should generate the least-privilege manifest, guide those provider-owned steps in Settings, and use
Slack's focused official `@slack/socket-mode` and `@slack/web-api` packages rather than maintaining a
custom WebSocket reconnect/ack implementation. This keeps local setup free of a public request URL.
A future truly one-click workspace install still requires a reviewed hosted OAuth/public-app
boundary; Easy Install must not pretend a local app can grant its own Slack permissions.

- [Slack OAuth installation](https://docs.slack.dev/authentication/installing-with-oauth/)
- [Slack Socket Mode](https://docs.slack.dev/apis/events-api/using-socket-mode/)

### 3. WhatsApp Business Cloud — guided Easy Install connection after first answer

Do not promise consumer WhatsApp Easy Install setup and do not rely on unofficial personal-account
libraries. Official support uses Meta's Cloud API and needs a Meta business portfolio, WhatsApp
Business Account, business phone number, app credentials, and a stable public HTTPS webhook. The
Settings flow can guide and validate those provider-owned steps, but must stay action-required until
the callback challenge succeeds. POST delivery must verify `X-Hub-Signature-256`, WABA and phone
scope; acknowledge only after durable enqueue; and deduplicate the provider message ID before a
single reply. The official payload shape identifies `object`, WABA `entry.id`, `field`, and
`metadata.phone_number_id`, so accepting only the phone field is not a sufficient tenant boundary.

- [Meta WhatsApp Cloud API](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
- [Meta webhook payload reference](https://www.postman.com/meta/whatsapp-business-platform/folder/tduohwq/webhook-payload-reference)

### 4. Groq and xAI/Grok

Use labels that cannot be confused:

- **Groq API** — activation/inference provider;
- **xAI API — Grok models** — separate provider and entitlement.

A consumer Grok subscription is not an xAI API entitlement. Store keys in Keychain and validate
against the provider's model endpoint with distinct 401, 403, 429, network, quota, and unsupported
model states.

- [Groq quickstart](https://console.groq.com/docs/quickstart)
- [xAI quickstart](https://docs.x.ai/developers/quickstart)

### 5. Google and Microsoft

Start with minimal read-only scopes and request additional scopes incrementally when an action needs
them. Reauthorization and wrong-account recovery should preserve adapter configuration rather than
requiring delete-and-readd.

## Feelings And Setup Discoverability

Feelings should be a first-class control-panel destination alongside MCP, Agent Builder, and Prompt
Templates. The persistent shell should also expose a small Setup/Connections health badge.

When Feelings needs an account or provider, show:

- what is missing in plain language;
- one recommended Connect action;
- what data will leave the Mac;
- a local/private alternative where supported;
- preserved draft/current state;
- a return path to the previous conversation.

Never leave a user to infer that setup lives in an unrelated account menu.

## Community Skills And Plugins

The [Agent Skills specification](https://agentskills.io/specification) is a useful package format,
not a trust signal. The [official MCP Registry](https://registry.modelcontextprotocol.io/) is
preview-stage and minimally moderated; registry presence alone cannot mean safe.

Default Viventium policy should require:

- first-party or reviewed packages by default;
- signature/digest and SBOM verification;
- explicit filesystem, network, account, and tool permissions;
- sandboxed execution;
- opaque secret references;
- preview before enabling;
- separate discover, install, and enable actions;
- per-tool enablement;
- clear telemetry and data-routing disclosure;
- review, update, migration, deprecation, and removal lifecycle;
- “also remove credentials?” as a separate explicit choice.

[Docker MCP Catalog and Toolkit](https://docs.docker.com/ai/mcp-catalog-and-toolkit/) is the best
current execution pattern inspected: curated signed local images, provenance/SBOM, container
isolation, profiles, and secret storage. Validation is still best-effort, and removing a server does
not necessarily remove its credentials; Viventium should close that lifecycle gap.

## Safe QA Isolation

A different `HOME` is not a security boundary. Native installers can still touch Keychain,
LaunchAgents, package managers, ports, system directories, Docker contexts, and TCC permissions.

| Tier | What it proves | What it cannot prove |
| --- | --- | --- |
| Disposable macOS VM or sacrificial Mac, no host mounts, synthetic accounts | Full public macOS installer/helper/Keychain/browser/user journey | Prefer Apple Virtualization.framework. Docker inside the guest needs supported nested virtualization; microphone/WebRTC may still need a physical Mac. Intel requires a separate Intel target if supported. |
| Named Colima profile with no host mounts, separate context/project/ports/state | Container and Linux-compatible CLI/service isolation | macOS Keychain, Homebrew/Xcode, helper, LaunchAgent, TCC, native voice. |
| Temporary directories plus mocked/synthetic release tests | Wizard/compiler/status/source contracts | Any real host mutation, restore, provider, or user experience. |

Useful isolation sources:

- [Colima profiles](https://colima.run/docs/profiles/)
- [Lima mounts and host exposure](https://lima-vm.io/docs/config/mount/)
- [Docker Compose project isolation](https://docs.docker.com/compose/how-tos/project-name/)
- [Docker health-based startup ordering](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker volume backup and restore](https://docs.docker.com/engine/storage/volumes/)

The initial host audit stayed read-only except for access-restricted private backup files,
temporary compiler/browser artifacts, and public-safe documentation. The later implementation pass
installed Tart and the Softnet formula on the host without enabling Softnet's privileged DHCP/SUID
path, then ran a no-host-mount disposable macOS VM with synthetic state. Clean signed-payload,
helper/Keychain/Gatekeeper, full provider connection, channel, and restore acceptance remain blocked
as recorded in the dated installer audit.

## Anti-Patterns

Do not adopt:

- floating `latest`/`main` or root `curl | bash` as the only installation story;
- host-home, Docker socket, privileged, or root mounts;
- plaintext `.env`, shell-startup, web-storage, or log credentials;
- services bound to `0.0.0.0` by default;
- public first-registration admin creation;
- default-on telemetry without explicit consent;
- a provider wall before the first useful result;
- fake progress or success based only on process/config presence;
- upgrade without a recovery checkpoint and rollback;
- retry that deletes data or starts from zero;
- unofficial WhatsApp personal-account libraries;
- arbitrary community packages trusted because they are popular;
- license-restricted UI/code without clearance;
- provider/model remapping, prompt keyword heuristics, or machine-specific workarounds.

## Acceptance Matrix Derived From Research

Every supported release must cover:

- fresh supported Mac and existing stable install with zero unintended drift;
- Apple Silicon and Intel only if Intel remains supported;
- Docker present, absent, stopped, unhealthy, and an explicitly supported alternative;
- low disk, low RAM, port collision, permissions, disabled virtualization;
- offline, DNS, proxy/TLS, registry-rate-limit, interrupted/resumed download;
- corrupt checksum, missing signature, partial artifact;
- cancel, quit, crash, and reboot at each transactional stage;
- idempotent rerun, repair, update, migration, rollback, downgrade;
- invalid, revoked, under-scoped, quota-exhausted, and unreachable providers;
- OAuth denial, wrong account, expired refresh, reauthorization, revoke;
- Telegram invalid token, allowlist, group privacy, and polling conflict;
- Slack missing-scope/disconnect when shipped;
- WhatsApp truthful prerequisite blocking until shipped;
- refresh, service restart, and machine restart persistence;
- uninstall preserving data versus explicit verified deletion;
- telemetry consent and zero-network behavior when opted out;
- keyboard, screen-reader, reduced-motion, narrow-layout, and localization behavior;
- visible outcome, expanded details, persistence, logs, DB/state, shipped artifact, and final wording
  agreement.

## Source Inspection Revisions

The retained static snapshots are AnythingLLM `28fbff47`, Coolify `b53ae426`, Home Assistant Core
`5865d633`, Jan `84a98bf4`, Ollama `573386c3`, and Open WebUI `ecd48e2f`. These identifiers make the
six retained source comparisons reproducible; no source was executed or copied into Viventium.
Dify and n8n have no retained revision in this audit and remain secondary inspiration until a future
research refresh records an exact ref, observation date, license boundary, and inspected files.

## Easy Install Native Packaging Addendum — 2026-07-18

The approved Native implementation adds a closer macOS reference set and current official runtime
constraints:

- [Syncthing for macOS](https://github.com/syncthing/syncthing-macos) is the closest structural
  reference: a native macOS wrapper owns a bundled headless service, localhost browser UI, App
  Support state, signing/notarization, and Sparkle updates. It is inspiration only; no code is copied.
- A small signed/notarized `Viventium.app` should own setup, status, update, and a user LaunchAgent
  registered through Apple's supported ServiceManagement API. Versioned runtime bundles remain
  separate so a backend health failure can return to N-1 without pretending a data migration rolled
  back. Primary sources: [Apple custom notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow) and [Apple helper migration guidance](https://developer.apple.com/documentation/servicemanagement/updating-helper-executables-from-earlier-versions-of-macos).
- The historical source install's Node 20 pin was obsolete for a new artifact and has now been
  aligned to Node 24 across the source installer and launcher layers. Node's official schedule
  marks Node 20 EOL and says production applications should use Active or Maintenance LTS. Node 24
  is the preferred candidate after compatibility testing. [Node release schedule](https://nodejs.org/en/about/previous-releases).
- Node SEA is not the first packaging choice because Node still labels it Active Development and its
  module/native-addon constraints add avoidable risk. Ship a pinned official Node runtime and
  production bundle first. [Node SEA documentation](https://nodejs.org/api/single-executable-applications.html).
- MongoDB's official macOS tarball flow proves Homebrew/Xcode are unnecessary. The first
  implementation should download an exact publisher archive and verify a digest already carried by
  Viventium's signed manifest. Public redistribution remains a separate SSPL/license review.
  [MongoDB macOS tarball installation](https://www.mongodb.com/docs/manual/administration/install-community/?macos-installation-method=tarball&operating-system=macos), [MongoDB SSPL](https://www.mongodb.com/legal/licensing/server-side-public-license).
- Meilisearch is optional until runtime evidence proves otherwise. If selected, pin Community
  Edition and override its resource-oriented defaults rather than letting indexing consume a large
  share of a small VM. [Meilisearch local installation](https://www.meilisearch.com/docs/resources/self_hosting/getting_started/install_locally).
- Tart is the Native cleanroom. Use an untouched stopped baseline and a fresh copy-on-write clone
  for every run; no host directories/disks, clipboard, audio, personal credentials, or personal
  Keychain state may cross the boundary. Tart is not evidence for Docker Desktop inside a macOS
  guest. [Tart quick start](https://tart.run/quick-start/).

The selected shape is therefore:

`small macOS helper -> signed manifest -> separately versioned runtime bundle -> exact publisher Mongo download -> health-gated atomic activation -> browser account-first setup`

Electron, a source-build `curl | sh`, Homebrew as an end-user prerequisite, Mongo-to-SQLite rewrite,
and Node SEA are rejected for this implementation because they add resources, migration scope, or
active-development risk without improving the first clean-machine proof.

## Primary-Source Recheck — 2026-07-19

The final decision pass rechecked the release-critical practices against current primary sources:

- Apple's current [`SMAppService`](https://developer.apple.com/documentation/servicemanagement/smappservice)
  guidance keeps login items and LaunchAgents inside the app-owned helper lifecycle; manually
  dropping a personal-user plist is not the preferred finished product.
- Apple's [notarization guidance](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
  still requires Developer ID signing before direct distribution and supports a stapled ticket that
  Gatekeeper can verify. The locally ad-hoc-signed helper therefore remains test-only.
- [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252) requires an external browser and PKCE for
  public native clients. A desktop loopback redirect should use an IP literal, bind only to loopback,
  open only for the authorization attempt, and close after the response.
- Slack's official [Socket Mode](https://docs.slack.dev/tools/bolt-js/concepts/socket-mode/) still
  needs an app-level token, and distributed installation still needs OAuth. This confirms Custom
  Settings Install first; it is not a zero-configuration Easy Install channel.
- Telegram still documents pull `getUpdates` and push webhooks as distinct update mechanisms in its
  [official webhook guide](https://core.telegram.org/bots/webhooks). Local Easy Install should use
  polling, validate the bot, detect a conflicting webhook, and never pretend pairing is complete
  until a synthetic send/receive succeeds.
- Groq's current [API reference](https://console.groq.com/docs/api-reference) exposes an authenticated
  model endpoint, while [model permissions](https://console.groq.com/docs/model-permissions) can
  return a distinct 403. The account test must distinguish invalid credentials, permissions, quota,
  rate limit, missing model, and network failure.
- xAI's [current quickstart](https://docs.x.ai/developers/quickstart) requires an xAI account, funded
  credits, and an xAI API key. This reaffirms that a consumer Grok subscription cannot be displayed
  as API readiness.
- Tart's [current quick start](https://tart.run/quick-start/) exposes separate Tahoe `vanilla`,
  `base`, and `xcode` images. The next decisive clean-machine lane must use a pinned vanilla image;
  the base image used in this audit cannot close the no-developer-tools gate.
- uv's [standalone installer](https://docs.astral.sh/uv/getting-started/installation/) and
  [`UV_NO_MODIFY_PATH` / unmanaged mode](https://docs.astral.sh/uv/reference/installer/) are useful
  evidence for hermetic tool bootstraps. Viventium should copy the pattern—pinned standalone
  artifacts and no shell-profile mutation—not add uv as another required end-user dependency.

These sources do not change the selected architecture. They strengthen the same conclusion: the
finished Easy Install should be an app-owned, versioned, signed/notarized payload with a tiny
transactional bootstrap, browser-first account setup, optional capabilities after first use, and
no package-manager or developer-tool dependency on the user's Mac.

## Release-Authority And Architecture Recheck — 2026-07-20

The final publication pass separated work the repository can enforce from authority only Apple or
the repository owner can supply:

- Sign nested executable code inside-out with a Developer ID Application certificate, hardened
  runtime, secure timestamp, and minimal entitlements. If a flat package is shipped, sign it with a
  Developer ID Installer certificate. Ad hoc or self-issued identities are local-QA evidence only.
- Submit every downloaded executable payload and the final wrapper independently with
  `notarytool`, inspect each result, staple the enclosed app/package, and run Gatekeeper checks on
  quarantined downloaded bytes. A ZIP can be submitted but cannot itself carry a stapled ticket;
  staple its enclosed code before rebuilding the final ZIP. See Apple's
  [custom notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)
  and [notarization troubleshooting](https://developer.apple.com/documentation/security/resolving-common-notarization-issues).
- Hash and sign only the final stapled bytes. The Viventium manifest complements Developer ID and
  notarization; it does not replace either. Apple Developer Program team membership, certificate
  private keys, App Store Connect team API credentials, Apple's timestamp/notary services, and a
  protected repository release environment are external authorities and cannot be synthesized by
  local code. Apple documents the account roles for
  [Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)
  and [App Store Connect API access](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api/).
- GitHub's current standard runner table provides explicit same-OS lanes: `macos-15` is M1/arm64
  and `macos-15-intel` is x86_64. The source-level compiler workflow now asserts both architectures
  and pins every action to a full commit SHA. GitHub-hosted macOS images include developer tools
  and arm64 nested virtualization is unsupported, so these lanes cannot close the pristine-Mac or
  physical Docker/TCC gates. See the
  [GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
- A protected signing/release job must pin all actions, expose signing secrets only in that
  environment, publish exact immutable assets, and independently download and verify them on both
  architectures. Multi-member organizations should require a separate reviewer and prevent
  self-review. A sole-owner organization instead needs an explicit owner dispatch from protected,
  CI-gated source; enabling both reviewer requirements and no-self-review would deadlock release.
  GitHub documents
  [protected environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
  [secure Action pinning](https://docs.github.com/en/actions/reference/security/secure-use), and
  [immutable releases](https://docs.github.com/en/enterprise-cloud@latest/code-security/concepts/supply-chain-security/immutable-releases).

This recheck authorizes source/CI hardening and exact artifact verification once credentials exist;
it does not authorize a fake signature, a branch-protection bypass, or release wording that claims
the external gates passed.
