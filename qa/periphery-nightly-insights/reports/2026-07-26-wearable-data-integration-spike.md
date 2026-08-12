# Wearable Data Integration Spike

Date: 2026-07-26

Status: research and synthetic transport validation complete; owner-data connector not yet run

Scope: research and QA design only; no product code, live configuration, credential, or runtime changes

## Decision Summary

The recommended first real-device path is a **direct, read-only vendor OAuth connector exposed to
Viventium as a remote MCP server**. If the device meant by “Otis” is an **Oura Ring**, the Oura Cloud
API is the best first target: it is web/backend based, works for owners who use either iOS or Android,
supports a one-owner pilot without vendor approval, offers an official synthetic sandbox, and fits the
existing user-created MCP and on-demand retrieval architecture.

The phone is still part of the vendor's device-to-cloud sync path, but Viventium does not need its own
mobile app for this pilot. A Viventium mobile bridge is only required for data that exists solely in
Apple HealthKit, Android Health Connect, or Samsung Health.

The proposed order is:

1. Validate cognitive usefulness with one private manual export, with no connector or persistent token.
2. Run a one-owner, least-privilege Oura OAuth pilot using raw vendor facts only.
3. Promote the pattern to a Viventium-owned, vendor-neutral observation store and read-only MCP.
4. Add direct WHOOP, Google Health, Polar, or Withings adapters as demand warrants.
5. Add native iOS and Android bridges only when device breadth justifies the mobile maintenance burden.

Paid aggregators can accelerate multi-vendor breadth, but their current entry prices and additional
health-data processor make them a later decision. Browser scraping and reverse-engineered private APIs
are research fallbacks, not production paths.

“Otis device” is ambiguous. No relevant wearable platform named Otis was identified in the official
or community landscape reviewed for this spike. This report therefore treats **Oura** as the likely
intended device without presenting that assumption as fact. The actual owner-data test must confirm the
manufacturer and model first.

## Fit With Viventium Architecture

The existing architecture already supplies most of the cognitive access path:

```text
wearable -> vendor phone app -> vendor cloud
         -> least-privilege OAuth collector
         -> private, normalized observations + provenance
         -> bounded inventory / freshness summary
         -> read-only MCP tools selected on demand by the Main Agent
         -> optional scheduled health-pressure inference
         -> separately governed surfacing or compact approved state
```

This preserves the project contracts:

- MCP is the correct external capability boundary; remote streamable HTTP/SSE and per-user OAuth/API
  credentials already have a governed user configuration path.
- Raw biometric samples and proprietary scores must not enter saved memory or every prompt.
- The Main Agent should receive a compact source/freshness inventory and retrieve detail only when it
  is useful for the user's request.
- The connector is a faithful courier. It returns vendor facts, units, timestamps, source, quality,
  and missingness; it does not invent medical or wellness recommendations.
- A future `health_pressure` module may share the Periphery generation and governance substrate, but
  its representation, retention, alerting, and memory policy stay separate.
- Private health payloads, raw exports, OAuth grants, and owner-specific QA evidence remain outside
  the public repository and public QA artifacts.

The current Periphery snapshot does not ingest wearable data. Its bounded inputs are memories,
conversations, schedules, scratchpads, recent runs, and lens inventory. A real implementation therefore
needs an explicit wearable evidence adapter; editing generated App Support snapshots would not be a
product integration.

## Integration Path Inventory

| Path | iOS owners | Android owners | Web-only Viventium | Freshness | Product fitness | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Direct vendor OAuth REST API | Yes | Yes | Yes | Polling; sometimes webhooks | Best provenance and least dependency for supported vendors | **Preferred first connector** |
| Direct vendor webhook + reconciliation | Yes | Yes | Yes | Near-real-time after vendor sync | Efficient, but must reconcile missed, duplicate, corrected, and deleted events | Add after historical pull works |
| Apple HealthKit native bridge | Yes | No | No | Background/device dependent | Broad iOS coverage; per-type consent and App Store obligations | Later mobile phase |
| Android Health Connect native bridge | No | Yes | No | Background/device dependent | Broad Android coverage; Android runtime permissions and publishing declarations | Later mobile phase |
| Samsung Health Data SDK bridge | No | Yes | No | Local-device | Strong Galaxy data; Android app and production partner registration | Later specialized phase |
| Official vendor export upload | Usually | Usually | Yes | Manual snapshot | Fastest no-token cognitive-value test; format and cadence are weak | **Preferred Phase 1** |
| Email/Drive watched-export workflow | Usually | Usually | Yes | Export-dependent | Can reduce manual steps but remains brittle and format-dependent | Optional user-controlled automation |
| Commercial aggregator REST API | Yes | Yes | Usually | Polling/webhooks | Fast breadth and normalization; cost, lock-in, and another data processor | Re-evaluate after demand proof |
| Commercial aggregator hosted MCP | Yes | Yes | Yes | Provider-dependent | Fastest MCP-shaped breadth when available | Paid evaluation only |
| Self-hosted Open Wearables | Cloud sources | Cloud sources | For cloud sources | Provider-dependent | Promising MIT-licensed normalization and MCP foundation; young project | Lab candidate, not adopted yet |
| Community vendor MCP | Usually | Usually | Yes | Provider-dependent | Can prove transport quickly; quality/security semantics vary widely | Audit or fork before use |
| Home Assistant/community plugin | Usually | Usually | Yes | Provider-dependent | Useful when an actively maintained official integration exists | Device-specific research path |
| Browser automation of vendor portal | Usually | Usually | Yes | Scheduled session scrape | MFA, session, UI churn, terms, and data-integrity risk | Isolated fallback only |
| Reverse-engineered mobile/private API | Usually | Usually | Often | Variable | Brittle, credential-heavy, unsupported, possible terms risk | Reject for production |
| Local Bluetooth/device protocol | Device-specific | Device-specific | No | Potentially live | Often proprietary; high reverse-engineering and mobile/driver burden | Only for a proven offline requirement |

## Device And Service Inventory

| Device/service | Official cloud route | Official phone/platform route | Official export | Community/unofficial route | Assessment |
| --- | --- | --- | --- | --- | --- |
| **Oura Ring** | API v2, OAuth 2.0, webhooks, synthetic sandbox | Apple Health; Health Connect | Web trend download while Oura Web remains available; Membership Hub full export | Several MCP servers; quality varies | **Best first one-owner web connector** |
| **WHOOP** | API v2, OAuth 2.0, webhooks | Apple Health; Health Connect | Mobile-requested emailed CSV bundle | Community clients/MCPs | Strong second direct adapter |
| **Fitbit / Google Health API** | New Google Health API; legacy Fitbit Web API retires in September 2026 | Health Connect | Google Takeout / Google Health export | Mature legacy clients, but migration risk | Target the new API, not new legacy work |
| **Apple Watch / Apple Health** | No general HealthKit cloud REST API | Native HealthKit on iPhone | Apple Health XML export | Export parsers and third-party sync apps | Manual import now; native iOS bridge later |
| **Garmin** | Garmin Connect Health API after program approval; commercial licensing may apply | Apple Health/Health Connect coverage varies | Activity files, activity CSV, account export, day wellness FIT | Aggregators and self-hosted projects | Rich but gated; not the quick pilot |
| **Polar** | AccessLink OAuth, REST, webhooks | Platform sharing varies | Account export | Aggregators and clients | Accessible direct API; good expansion candidate |
| **Withings** | Public API, OAuth, notification callbacks | Apple Health/Health Connect coverage varies | Emailed CSV export | Aggregators and clients | Good cloud candidate; confirm commercial terms/limits |
| **Samsung / Galaxy Watch** | No equivalent general web API for an owner pilot | Samsung Health Data SDK; Health Connect | Account/privacy export paths | Aggregators, early self-hosted SDK adapters | Requires Android bridge for first-party access |
| **Ultrahuman Ring** | Official personal-token and OAuth partner APIs | Apple Health/Health Connect coverage varies | Account/privacy export path | Open Wearables adapter | Credible direct cloud candidate; verify partner onboarding |
| **RingConn** | No public developer API verified | Apple Health and Health Connect | In-app/privacy export path | Community private-API experiments | Use platform bridge or export; no private API in product |
| **Eight Sleep** | No public developer API verified | Vendor app | Privacy/account request path | Reverse-engineered cloud clients; former integrations have broken after API changes | Aggregator/partnership or manual only |
| **Amazfit / Zepp** | No self-service historical health-cloud API verified | Zepp OS device apps; Apple Health/Health Connect sharing where supported | Privacy/account export path | Private-cloud clients and custom watch apps | Platform bridge/export; do not assume a cloud API |

### Official details that affect the design

- **Oura:** API v2 uses OAuth authorization code flow. Personal access tokens were deprecated in
  December 2025 and are no longer available. New apps are limited to ten users until approved. Oura
  recommends a historical pull followed by webhooks; published limits are 5,000 requests per five
  minutes. Data availability still depends on the ring syncing through the Oura app. Sources:
  [API docs](https://cloud.ouraring.com/v2/docs),
  [export](https://support.ouraring.com/hc/en-us/articles/360025441594-Export-Share-Your-Oura-Data),
  [Apple Health](https://support.ouraring.com/hc/en-us/articles/360025438734-Apple-Health-Integration),
  [Health Connect](https://support.ouraring.com/hc/en-us/articles/10786105824531-Health-Connect-by-Android-Integration).
- **WHOOP:** unapproved apps can connect up to ten members. The `offline` scope provides rotating
  refresh tokens. Webhook events tell the client to fetch the authoritative object; consumers must
  tolerate duplicates and reconcile missed events. Published limits are 100 requests per minute and
  10,000 per day. Sources: [getting started](https://developer.whoop.com/docs/developing/getting-started/),
  [OAuth](https://developer.whoop.com/docs/developing/oauth/),
  [webhooks](https://developer.whoop.com/docs/developing/webhooks/),
  [rate limits](https://developer.whoop.com/docs/developing/rate-limiting/),
  [export](https://support.whoop.com/s/article/How-to-Export-Your-Data). The official contract probes,
  community MCP audit, and owner-device acceptance sequence are in
  [the dedicated WHOOP validation](2026-07-26-whoop-smart-wristband-validation.md).
- **Google/Fitbit:** Google documents the Google Health API as the next-generation Fitbit Web API;
  legacy Fitbit Web API integrations are scheduled for deprecation in September 2026. The new API is
  REST/gRPC, OAuth-based, and supports reconciled streams/webhooks. Sources:
  [Google Health API](https://developers.google.com/health),
  [getting started](https://developers.google.com/health/get-started),
  [data types](https://developers.google.com/health/data-types),
  [export](https://support.google.com/googlehealth/answer/14236615).
- **Apple HealthKit:** access is mediated by a native app on the user's device and permission is
  granted per data type. Apple provides observer queries for background delivery and an on-device
  “Export All Health Data” XML path. Sources: [HealthKit](https://developer.apple.com/documentation/healthkit),
  [privacy](https://developer.apple.com/documentation/healthkit/protecting-user-privacy),
  [export](https://support.apple.com/guide/iphone/share-your-health-data-iph5ede58c3d/ios).
- **Android Health Connect:** this is an Android device data store with runtime permissions, not a
  vendor-neutral backend REST API. Background and historical reads have separate policy and
  permission requirements. Source: [Health Connect](https://developer.android.com/health-and-fitness/health-connect).
- **Garmin:** its Health API is cloud-to-cloud but requires program approval and may require a
  commercial-use license fee. Source: [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/).
- **Polar:** AccessLink offers owner OAuth, exercises, daily activity, continuous heart rate, sleep,
  Nightly Recharge, and webhooks. Source: [Polar AccessLink](https://www.polar.com/accesslink-api/).
- **Withings:** the public API uses OAuth authorization code flow and provides notification callbacks
  that are followed by data fetches. Published standard callback/API limits include 120 requests per
  minute. Sources: [API reference](https://developer.withings.com/api-reference/),
  [notifications](https://developer.withings.com/developer-guide/v3/data-api/notifications/notification-overview/).
- **Ultrahuman:** the official developer portal documents both a personal data-sharing token route and
  OAuth authorization-code/refresh-token flow with `profile`, `ring_data`, and `cgm_data` scopes.
  Source: [Ultrahuman developer docs](https://vision.ultrahuman.com/developer-docs?type=oauth).
- **Samsung:** the current Health Data SDK reads the local Samsung Health store on Android 10 or
  later, requires Samsung Health 6.30.2 or later, does not support emulators, and requires app
  registration/partner approval for public distribution. Sources:
  [SDK introduction](https://developer.samsung.com/health/data/guide/introduction.html),
  [app verification](https://developer.samsung.com/health/data/guide/app-verification.html).

## MCP And Aggregator Options

### Existing Viventium MCP seam

LibreChat's user-created MCP configuration already accepts remote SSE and streamable HTTP servers.
OAuth client secrets and administrative credentials are encrypted in the existing server-config
store. A user API key is represented through the per-user variable path rather than a hard-coded
header. Any pilot should use that governed path, a narrow tool allowlist, and a revocable bearer token.

### Commercial breadth options

| Service | Relevant shape | Public price signal reviewed | Assessment |
| --- | --- | --- | --- |
| [Spike](https://docs.spikeapi.com/mcp/overview) | Multi-provider API plus a hosted remote MCP endpoint | [Sandbox starts at USD 450/month](https://www.spikeapi.com/pricing) | Fastest paid MCP-shaped evaluation; too expensive for the first owner-only proof |
| [Terra](https://docs.tryterra.co/introduction) | Cloud APIs plus mobile SDKs for Apple/Health Connect | [USD 499/month monthly or 399/month annual entry tier](https://tryterra.co/pricing) | Broad and mature-looking; another processor and material recurring cost |
| [Thryve](https://docs.thryve.health/thryve-product-overview/connect) | Web connection widget for cloud sources plus native mobile SDKs | Contact sales | Credible breadth option; requires commercial/privacy diligence |

Aggregator marketing coverage is not acceptance evidence. Before adoption, run a vendor demo against
the exact device, metrics, correction semantics, latency, deletion, regional processing, export,
subprocessor, and MCP/tool requirements.

### Self-hosted option

[Open Wearables](https://github.com/the-momentum/open-wearables) is a promising MIT-licensed,
self-hosted FastAPI/PostgreSQL/Redis project with provider adapters, normalized APIs, mobile SDK work,
and MCP work. It can reduce multi-provider scaffolding without sending data to a commercial
aggregator. It is also young: provider coverage and maturity differ, some UI/widget/AI features remain
in progress, and adopting its operational stack would be a substantial dependency. Evaluate it in an
isolated lab against the same raw-fact and provenance contract; do not import its AI-health behavior
into Viventium by default.

### Community MCP audit finding

Several Oura MCP repositories exist, but freshness alone is insufficient. One current OAuth-capable
remote server was checked at a pinned commit in an isolated temporary directory. It built and
type-checked, reported zero production dependency vulnerabilities, returned `401` without its server
key, and completed an authenticated MCP initialize handshake. It had no test files and also exposed
tools that:

- returned personal profile information beyond the pilot's need;
- hard-coded generic readiness/step thresholds and wellness advice;
- relabeled a small sample minimum as “resting heart rate”; and
- performed trend arithmetic without adequate empty/missing-data guarantees.

That implementation is **not fit for Viventium as-is**. It proves the remote MCP transport shape, not
the health semantics. A later connector must expose vendor observations and proprietary vendor scores
as facts, while Viventium owns bounded, evidence-linked inference.

## Canonical Evidence Contract

The normalized layer should preserve source truth before it tries to make device data look uniform.

### Connection and consent

- `source_system`, connector version, ingestion method, pseudonymous account and device references
- granted scopes, consent purpose/version/time, expiry, revocation/deletion state
- vendor object/API version and regional/processing metadata where known

### Observation or session

- stable vendor object ID plus version/revision; raw-payload hash for audit without logging payloads
- canonical metric type and original vendor metric name
- value, unit, aggregation/window, source/device type, quality/coverage
- recorded start/end, vendor generation time, ingestion time, local date, timezone, and UTC offset
- source endpoint/object and any correction or deletion tombstone
- vendor score stored explicitly as a **vendor-derived score**, not an objective physiological fact

### Missingness and correction

Do not collapse missing data to `null` or zero. Preserve at least: not measured, not worn, not synced,
not authorized, provider unavailable, delayed, deleted, and unsupported. Deduplicate by source,
account, vendor object ID, and version. Corrections append or supersede with lineage; they do not
silently overwrite the evidence used by a prior insight.

### Viventium inference

A future health-pressure artifact is a separate object with evidence references, time horizon,
confidence, freshness, missingness, non-diagnostic status, TTL, and surfacing policy. Raw samples,
vendor exports, and invented “insights” from connectors are not saved memory.

## Security, Privacy, And Product Guardrails

Health and biometric data should be treated as sensitive even when a vendor labels the device
“wellness” rather than medical.

- Use authorization code + PKCE where supported, exact redirect allowlists, CSRF `state`, short-lived
  access tokens, rotated refresh tokens, encrypted/Keychain-backed storage, and revocation.
- Start with read-only daily summary scopes. Do not request email, demographics, tags, CGM, location,
  or raw high-frequency heart rate unless an accepted use case requires them.
- Keep raw payloads and tokens out of prompts, browser cards, logs, public QA, source control, and
  analytics. Log only sanitized source, time, count, status, latency, and correlation metadata.
- Make AI use, purposes, sources, retention, processors, deletion, and withdrawal understandable at
  consent time. A vendor OAuth grant is not by itself consent for every AI inference or alert.
- Provide disconnect, token revocation, raw-data deletion, derived-artifact expiry, and an audit trail.
- Default to on-demand answers. Health alerts or durable state need a separate opt-in policy and
  medical-humility evaluation.
- Complete privacy/legal review before broader distribution. Canada's meaningful-consent guidance
  emphasizes understandable purposes, involved parties, consequences, and withdrawal; Quebec privacy
  requirements add privacy-impact and high-default expectations for sensitive personal information.
  Sources: [Office of the Privacy Commissioner of Canada](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/principles/p_consent/),
  [Commission d'accès à l'information du Québec](https://www.cai.gouv.qc.ca/protection-renseignements-personnels).

This is architecture guidance, not legal or medical advice.

## Proposed Actual Evaluation

### Phase 0 — completed synthetic proof

The official Oura OpenAPI description and synthetic sandbox were probed without owner data. Eight
representative endpoints—daily readiness, activity, sleep, SpO2, stress, detailed sleep, heart rate,
and workout—returned structured synthetic documents for a bounded date. Missing authorization was
rejected. The WHOOP OpenAPI document parsed and an unauthenticated production request was rejected.
A commercial hosted MCP endpoint accepted an SSE connection shape but was not authorized or sent user
data. This proves documentation and transport behavior only.

### Phase 1 — no-code private value test

Purpose: determine whether wearable evidence actually improves Viventium's relevance before building
continuous plumbing.

1. Confirm the device vendor/model and the user's desired questions.
2. The user obtains a small official export covering 14–30 days.
3. Keep the export in private runtime/user storage; never commit it or copy it into public QA.
4. Ask a fixed, non-diagnostic question set: sleep consistency, recovery/readiness changes, workload
   timing, missing-data honesty, and whether the evidence should affect planning today.
5. Compare an answer with no wearable access against an answer with the private export.
6. Score intelligence, relevance, usefulness, alignment, latency, evidence traceability, uncertainty,
   and privacy. Require the data-assisted answer to add material value without unsupported causality.
7. Delete the test copy and record only sanitized counts, date span, hashes, statuses, and conclusions.

This is iOS/Android neutral and requires no persistent connector credential.

### Phase 2 — one-owner OAuth connector spike

Assuming the device is Oura:

1. Register a development OAuth app with one exact HTTPS callback. A temporary tunnel may be used only
   for the isolated callback test; no secret or private URL belongs in public evidence.
2. Request the minimum useful scopes: begin with `daily`; add `heartrate`, `workout`, or `spo2Daily`
   only when a test question requires them. Exclude `email`, `personal`, and `tag` by default.
3. Historical backfill a bounded 30-day window, then test vendor webhooks/poll reconciliation.
4. Expose only raw read tools: source status/freshness, list daily summaries, read sleep sessions,
   read heart-rate summaries/samples, and read workouts. No medical advice or hard-coded insight tool.
5. Connect through the existing per-user remote MCP path with a revocable, user-scoped server key.
6. Run happy path, first sync, no data, missing scope, token expiry/refresh, revocation, delayed phone
   sync, duplicate webhook, corrected record, deletion, provider timeout/rate limit, restart, and full
   disconnect/deletion cases.
7. Run the same cognitive A/B evaluation as Phase 1, including on-demand tool selection, visible tool
   detail, refresh/persistence, backend trace, and confirmation that ordinary chat does not retrieve
   health data without relevance.

### Acceptance gate

Do not promote the pilot unless all of these are true:

- The real device path works after an actual phone-to-vendor sync on the owner's current mobile OS.
- Every answer cites source and measurement time and distinguishes observation, vendor score, and
  Viventium inference.
- Missing, late, corrected, revoked, and unavailable data remain honest in both UI and logs.
- No raw health payload or credential appears in saved memory, the default prompt, logs, public QA,
  repository files, or unrelated conversations.
- Disconnect revokes access; deletion covers raw and derived artifacts; restart does not broaden scope.
- The data-assisted answer is measurably more useful, not merely more detailed or faster.
- iOS and Android support claims are based on the actual vendor sync path tested. HealthKit/Health
  Connect coverage is not implied by a cloud-OAuth test.

## Evidence And Current Status

| Evidence item | Result | Limitation |
| --- | --- | --- |
| Project requirement/architecture trace | PASS | Documents intended seam; does not create a connector |
| External Deep Research source-discovery pass and correction audit | PASS; 45 cited sources in the completed research report | Supporting discovery only; primary sources and isolated probes control this report where claims conflicted |
| Claude Opus 5/xHigh independent review-only pass | BLOCKED; desktop and headless fallback both returned the active weekly usage limit before any review | No Claude verdict was inferred; primary-source correction audit and Codex self-review remain the available review evidence |
| Public report external-link check | PASS; all 30 cited external URLs returned HTTP 200 on 2026-07-26 | Reachability does not prove every vendor policy will remain stable |
| Existing MCP input-schema and encrypted server-config tests | PASS; 2 schema tests and 60 server-config tests | Confirms the present seam, not a wearable implementation |
| Oura API description parse | PASS; 72 documented paths in the reviewed description, including sandbox paths | Counts can change with the vendor spec |
| Oura synthetic endpoint probes | PASS; eight representative resources returned synthetic data | No owner account, OAuth callback, webhook, or phone sync tested |
| WHOOP API description parse/auth rejection | PASS | No authorized member data tested |
| WHOOP official contract and community MCP audit | PARTIAL; 20-path contract, six fail-closed resource probes, 198 connector tests, lint/type checks, and MCP handshake completed | No ordinary developer sandbox or owner OAuth; audited community package has unresolved transport, scope, privacy, export, dependency, and version-reporting blockers ([details](2026-07-26-whoop-smart-wristband-validation.md)) |
| Hosted commercial MCP transport probe | PASS for reachable SSE transport | No vendor authorization, tools, payloads, or commercial agreement tested |
| Current community Oura MCP build/handshake/security-semantic audit | PARTIAL transport proof; rejected as a product dependency | One pinned repository, no owner credential or data |
| Real owner export cognitive A/B | NOT RUN | Requires private export and explicit test session |
| Real owner OAuth connector | NOT RUN | Requires confirmed device, OAuth app/callback, and explicit credential grant |
| iOS HealthKit bridge | NOT RUN | Requires native app and physical iPhone test |
| Android Health Connect/Samsung bridge | NOT RUN | Requires native app and physical Android test |

No completion claim is made for real wearable access. The spike has established a source-backed
decision and an executable acceptance plan; the user-data and continuous-connector gates remain open.

## Research Corrections And Uncertainties

The review deliberately excluded claims that could not be confirmed from authoritative current
sources:

- no published Withings free-user ceiling is used in the decision;
- no general Zepp historical wellness-cloud OAuth API is assumed;
- no active official or dependable Home Assistant route is claimed for Eight Sleep;
- no community MCP is treated as official merely because it supports OAuth or is recently updated;
- vendor score names do not imply clinical validation or cross-device comparability;
- Oura Web export is a transition path because Oura says the web service will be discontinued later
  in 2026.

Vendor APIs, policies, pricing, and platform export behavior are current as of the report date and
must be rechecked immediately before implementation.

## Related Viventium Sources

- `docs/requirements_and_learnings/01_Key_Principles.md`
- `docs/requirements_and_learnings/07_MCPs.md`
- `docs/requirements_and_learnings/11_Scheduling_Cortex.md`
- `docs/requirements_and_learnings/20_Memory_System.md`
- `docs/requirements_and_learnings/32_Conversation_Recall_RAG.md`
- `docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md`
- `docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`
- `docs/requirements_and_learnings/53_Viventium_Periphery_Nightly_Insights.md`
- `docs/02_ARCHITECTURE_OVERVIEW.md`
- `docs/03_SYSTEMS_MAP.md`
- `viventium_v0_4/docs/ARCHITECTURE.md`
- `qa/README.md`
- `qa/feature-user-use-case-checklist.md`
