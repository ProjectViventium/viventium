# Viventium Periphery And Nightly Insight Routines

**Status:** Risk-radar pilot implemented and locally accepted 2026-07-11; WHOOP health-context integration connected, backfilled, activated, and locally accepted 2026-08-10
**Owner:** Viventium Core
**Scope:** Private scratchpads, nightly insight formation, risk/opportunity/blind-spot analysis,
health-pressure awareness, and optional surfacing into the conscious agent.

## Vision

This is one of Viventium's defining ambitions.

Viventium should not be only a chat surface that answers the latest message. It should grow a
private, evidence-grounded periphery: a place where longer-horizon thought can form quietly, where
risks and opportunity costs can be noticed before they become obvious, where blind spots can be
held with care, and where empathy can become more than tone. The goal is prediction, emotional
mirroring, health-pressure awareness, strategic opportunity sensing, and protective challenge in one
coherent intelligence system.

This should be treated proudly. It is not a reminder feature, a dashboard widget, or a modest
prompt tweak. It is Viventium learning to care over time.

The implementation must still stay disciplined. The more ambitious the product becomes, the more
important it is that the design remains evidence-first, private by default, non-invasive, and free of
hardcoded overfit.

## Product Thesis

The conscious agent should have peripheral awareness, not peripheral noise.

Nightly routines can think deeply over memory, recent work, scratchpads, schedules, and relevant
private artifacts. Their output should not be shoved into every conversation. Instead, they should
leave governed private artifacts and compact availability signals so Viventium can choose, when
relevant, to inspect more.

This gives Viventium three layers:

1. **Conscious chat:** fast, warm, useful response to the present moment.
2. **Background cortices:** asynchronous live-turn insight and follow-up.
3. **Private periphery:** slower nightly/offline insight formation, retained as artifacts and
   surfaced only when useful.

## Existing Product Foundation

This direction must reuse the foundation already present in Viventium:

- **Prompt Workbench scheduled prompts** already own private scheduled prompt authoring, variable
  previews, run history, private rendered prompt details, and `memoryWriteMode`.
- **Scheduling Cortex** already owns recurrence, misfire/catch-up policy, ledger state, callback
  reconciliation, and cross-channel scheduled-task execution.
- **GlassHive host workers** already own private local execution and can write to the per-user
  private continuity folder.
- **Memory proposals** already use structured `memory-proposals-*.json` files plus governed dry-run
  or apply behavior.
- **Conversation recall and transcript recall** already prove the inventory pattern: compact
  model-visible inventories can point to larger detailed artifacts without dumping every artifact
  into the main prompt.
- **Background cortices** already provide lenses such as emotional resonance, pattern recognition,
  red-team challenge, confirmation-bias checks, and strategic planning. Nightly routines should
  reuse these lenses as thinking material before creating a duplicate specialist stack.

## Existing Nightly And Scheduled Routines

At a high level, Viventium already has these routine classes:

- **Memory hardening:** governed saved-memory maintenance, transcript ingest, proposal/apply/rollback
  behavior, and healthy empty skips.
- **Prompt Workbench nightly reflection:** private GlassHive scheduled thought formation with
  scratchpad and memory-proposal outputs.
- **Scheduling Cortex user/agent schedules:** user-visible or silent scheduled agent runs across
  LibreChat and Telegram, with `{NTA}` suppression and delivery ledgers.
- **Transcript and recall maintenance:** processing transcript summaries/inventories and maintaining
  recall/RAG derived state when configured.
- **Brain readiness checks:** scheduler, Workbench, GlassHive, memory hardening, recall, search,
  provider, voice, Telegram, and MCP readiness surfaces.

New insight routines must extend this ecosystem, not bypass it.

## Required Sequencing

Do not add a risk-radar or health-pressure routine on top of an unclassified nightly failure.

Before new routines are made active, the current scheduled-run substrate must be understood:

- classify recent Workbench/scheduled-prompt failures by structured failure class
- inspect Scheduler, Workbench, GlassHive, callback outbox, and watchdog evidence
- distinguish provider reconnect/action-required failures from executor dependency failures
- clear or explain queued/stale runs
- prove the canonical path again:
  scheduled prompt -> filled variables -> GlassHive run -> callback -> parent/child ledger ->
  Workbench visible completed state

This is not bureaucracy. If Viventium is going to think overnight, the night worker has to be honest.

## Periphery Artifact Contract

The periphery should formalize the existing private scratchpad habit into typed private artifacts.

Recommended private shape:

```text
periphery/
  _index.json
  risk_radar/
    YYYY/
      MM/
        YYYYMMDDTHHMMSSZ.risk_radar.md
        YYYYMMDDTHHMMSSZ.risk_radar.json
  health_pressure/
    YYYY/
      MM/
        YYYYMMDDTHHMMSSZ.health_pressure.md
        YYYYMMDDTHHMMSSZ.health_pressure.json
```

The markdown file is for human/agent reading. The JSON sidecar is the contract.

Minimum JSON fields:

- `schemaVersion`
- `moduleId`
- `generatedAt`
- `scheduledRunRef`
- `sourceRefs`
- `confidence`
- `severity`
- `timeSensitivity`
- `ttl`
- `staleAfter`
- `observations`
- `risks`
- `blindSpots`
- `opportunityCosts`
- `opportunities`
- `whatWouldMakeThisWrong`
- `whenToSurface`
- `proposedActions`
- `memoryProposalRefs`

Artifacts are private runtime state. They must not be committed, published, copied into public QA
reports, or exposed through screenshots.

The live filesystem contract is owner-only: the user continuity root, `my_folder`, `periphery`, and
artifact parent directories are mode `0700`; paired Markdown/JSON files and `_index.json` are mode
`0600`. Discovery, listing, and body reads are descriptor-relative and do not follow links. Symlinked paths
are withheld, files with multiple hard links are withheld because their inode boundary cannot be
proven, and the reader never returns content from a different open than the one it validated. Index
replacement uses an exclusive random temporary file and a descriptor-relative rename.

The public index distinguishes `available`, `degraded`, and `blocked`. A single withheld artifact
cannot hide healthy artifacts: `degraded` retains usable insights and reports the withheld count;
`blocked` is reserved for a corpus with no safely readable artifacts. Agent-facing output receives
only allowlisted reason codes and path-free remediation guidance. `unsafe_symlink`,
`unsafe_hard_link`, `outside_periphery_root`, and `private_permissions_unavailable` never expose a
private path. A hard-linked backup must be restored as a normal private file before ingestion.

Current implementation:

- Prompt Workbench exposes authenticated metadata, snapshot-status/refresh, and on-demand artifact
  detail endpoints for private periphery sidecars.
- The endpoint returns sidecar filenames, relative private paths, timestamps, confidence/severity
  labels, stale/TTL fields, source-reference counts, scheduled-run-reference hashes, markdown
  existence, and content counts.
- The endpoint does not return markdown bodies, raw source refs, raw observations, raw risks, raw
  blind-spot text, raw opportunity text, local absolute paths, or private run detail text.
- Malformed sidecars are listed as invalid metadata with a reason instead of crashing or pretending
  insight exists.
- Schema v2 artifacts bind every claim to a private snapshot with `snapshotRef` and source refs.
  Validation resolves those refs against the captured snapshot, counts grounded/ungrounded claims,
  and marks artifacts `passed`, `warning`, `failed`, `legacy`, or invalid with explicit quality
  reasons instead of trusting shape alone. Claim grounding counts only refs actually resolved in the
  snapshot; an aged-out snapshot is reported as unavailable rather than as an unexplained failure.
- The built-in Workbench nightly prompt is compact and asks the existing private nightly worker to
  read projected evidence files and write one `risk_radar` sidecar pair, including an honest
  low-signal/no-result artifact when strong evidence is missing. Raw snapshot content is not inlined
  into prompt text.
- Workbench startup seeding reconciles the built-in nightly definition and scheduler task so the
  live scheduled run receives the sidecar contract after a managed Workbench restart.
- Built-in health-context definitions carry a managed template revision. Source upgrades may
  reconcile that prompt only while it remains managed; the first owner edit marks it unmanaged so
  startup cannot silently overwrite private customization.
- The built-in risk-radar routine uses `memoryWriteMode=off`. A durable memory change requires a
  separately governed proposal; the nightly routine does not create memory proposals by default.
- Scheduling Cortex exposes two user-scoped read-only tools: a bounded periphery index and an
  on-demand read. The list returns only the newest current artifact per module, plus bounded
  historical context, so repeated versions do not trigger redundant reads. The agent-facing
  serializers remove paths, filenames, run/snapshot ids, raw source record ids, invalid-artifact
  details, and duplicate markdown while preserving evidence text, freshness, uncertainty, and
  grounding counts.
- Artifact recency comes from validated `generatedAt`, not file modification time, so touching or
  restoring an older file cannot make it the newest insight.
- The main conscious agent carries only those optional read tools and the Scheduling Cortex's
  tool-owned instructions. No nightly body, saved-memory key, or new periphery block is injected
  into the main chat prompt.

## Awareness Without Prompt Bloat

Risk, opportunity, and blind-spot artifacts should not be inserted into the main prompt by default.

The awareness mechanism is the Scheduling Cortex's tool-owned instruction plus two read-only tools,
not a new saved-memory key or a main-prompt block:

- Viventium may have private periphery scratchpads.
- When the user asks for blind spots, risks, opportunity costs, prior nightly insights, deep
  planning, or self-review, list the available periphery and read only the relevant artifact.
- Do not mention or inspect the periphery by default.
- Do not pretend a periphery artifact exists when the index or read path is unavailable.

This preserves peripheral awareness without forcing every conversation to carry every overnight
thought.

## Memory Boundary

Saved memory is not the scratchpad store.

Do not add a `periphery` saved-memory key for risk radar in the first implementation. Do not overload
`drafts` with generated nightly insight indexes. `drafts` remains active user work in progress.

Risk and opportunity insights belong first in private artifacts and governed proposals. If a stable
fact or durable preference emerges, it can be proposed through the existing memory-governance path.

The health-pressure gauge is different. It may eventually need a compact always-available state
because it can shape the conscious agent's response posture in ordinary conversation. That decision
must be evaluated separately and must preserve medical humility: health-pressure awareness is a
behavioral support system, not diagnosis.

## Risk Radar Module

The first proposed periphery module is a private risk/opportunity/blind-spot radar.

It should answer questions like:

- What is the user not seeing?
- What risks are accumulating quietly?
- What opportunities are being missed because attention is elsewhere?
- What opportunity costs are hidden inside current commitments?
- What assumptions look fragile?
- What would a caring but sharp partner call out?

Output must be evidence-first. Every non-trivial claim needs a source reference or an explicit
uncertainty label. The module must distinguish:

- observation
- inference
- hypothesis
- risk
- opportunity
- stale/unsupported thought

Default surfacing is silent. The main agent may use the artifact when the user asks, during deep
planning/review, or when an approved future surfacing policy says a high-confidence time-sensitive
item should be raised.

## Health Pressure Module

Health-pressure awareness is a sibling module, not simply another risk-radar note.

It shares the front-half governance spine:

scheduled private inference -> evidence-cited artifact/proposal -> evals -> governed persistence.

Its durable representation may diverge because the product goal is different. A health gauge is
stateful and longitudinal. It may need a compact current-state/trend surface so Viventium can be
more empathetic, quieter, firmer, or safer without explicitly announcing the gauge every turn.

Rules:

- no medical diagnosis
- no inferred hormone or neurotransmitter claims from text
- no RED/danger classification from ambition alone
- no health nagging by default
- use observed evidence, user-stated hypotheses, and clinician/user-provided facts distinctly
- keep the user in control of escalation policy

### Wearable evidence ingress

Wearable data is evidence for health-context awareness, not a new saved-memory class and not an
excuse to put raw biometrics in the main prompt. The accepted first integration is the separately
versioned `Viventium-Health` component with WHOOP as its first provider.

The owning path is:

1. official, least-privilege WHOOP OAuth using only documented scopes and endpoints
2. exact response bytes plus separate provenance in an owner-only, append-only local archive
3. bounded inventory and read-only MCP tools for model-owned, on-demand retrieval
4. an opt-in Prompt Workbench snapshot that combines bounded health evidence with the existing
   private context snapshot without exposing record IDs, paths, credentials, or raw content in its
   manifest
5. a separate Scheduling Cortex routine that may write a private `health_context` artifact, with
   memory writes off and no automatic health-pressure gauge or chat injection
6. an optional metadata-only status projection into the owner's Life health folder; raw provider
   payloads stay in App Support and remain available through the bounded reader

The local-administrator Settings card is the onboarding owner. With an approved WHOOP app already
provisioned, one **Connect WHOOP** action opens official consent; the registered `viventium://`
callback returns through the macOS helper on stdin, then all-history import and the native daily
correction job start automatically. A public build cannot embed a reusable confidential WHOOP
client secret. An unprovisioned installation therefore offers a combined **Save and connect**
self-managed developer-app fallback and states WHOOP's 10-member unapproved-app cap. Status exposes
all six documented resource families and provider item counts, not archive-page counts.

Health data remains host-owner scoped even if the main agent itself is shared. The generated health
MCP declares a reusable `local_owner` request audience; the common MCP loader denies missing or
ordinary-user identity before discovery or process startup, while the HTTP onboarding surface keeps
every read and mutation behind the local admin gate. A disabled health integration is omitted from
generated MCP configuration rather than advertised as a broken tool. OAuth consent state expires
after ten minutes, onboarding is single-flight across helper/browser retries, abandoned UI polling
is bounded, and error-code-based recovery remains visible without exposing callbacks or paths.

The raw archive intentionally supersedes the earlier normalized-store proposal. Normalizing vendor
payloads at ingress would risk silently dropping fields, rewriting units, or hiding later provider
corrections. Interpretation belongs downstream and must cite immutable source references.

The explicit first-connection import uses `viventium health pull whoop --all-history`. It requests
all available history exposed by WHOOP's six official v2 read resources, omits the collection
minimum-time filter, fixes the upper capture time, and follows provider pagination. The courier
proactively honors the published minute budget, can rotate an expired token again on a later page,
reports an exact run-record count, and fails visibly at its 1,000-page-per-resource safety cap.
Daily acquisition remains the smaller three-day correction window.

#### Recurrence ownership

There are two recurrence lanes and each has exactly one owner:

- `Viventium-Health` owns provider acquisition through its explicit macOS LaunchAgent. The default
  WHOOP pull runs at 06:00 local time, uses a three-day correction overlap, and appends rather than
  overwrites.
- Scheduling Cortex owns the opt-in `health_context` analysis definition through Prompt Workbench.
  Its default run is 06:15 local time with catch-up semantics. It does not pull WHOOP, refresh OAuth,
  or mutate the health archive.

The analysis routine is seeded inactive unless the operator explicitly enables it. Connector
availability, authorization, source freshness, and worker readiness are reported independently; an
empty archive is never presented as a healthy successful pull.

#### Bounded correlation snapshot

The health-context snapshot is a specialization of the existing private Periphery snapshot. It may
contain bounded health record bodies only in the private model snapshot; Workbench APIs and variable
previews expose metadata, counts, hashes, and prerequisite state only.

Initial bounds are:

- at most 120 record summaries inspected (reported as inspected, never mislabeled as the archive total)
- at most 18 record bodies selected, distributed across available WHOOP resource families
- at most 65,536 bytes from one record and 384,000 health-content characters in one snapshot
- provider and archive commands time out and fail closed
- every model-visible record has a derived `health:<opaque-hash>` source reference, provider,
  resource, fetch time, response status, byte length, SHA-256, encoding, completeness, and exact
  bounded content
- every snapshot field is untrusted evidence; provider bodies and adjacent contextual sources can
  never supply instructions, change authority, or override the bounded correlation contract

The routine must distinguish measurement time inside vendor evidence from archive fetch time. It may
describe associations across matching time windows, but it must not claim diagnosis or causation,
invent thresholds, treat a proprietary vendor score as a clinical fact, or recommend treatment.
No-result and missing-prerequisite outputs are valid artifacts when evidence is absent or stale.

#### WHOOP contract boundary

WHOOP's documented developer API currently covers cycles, recovery, workout, sleep, profile, and
body measurements. It does not document the app's 0–3 Stress Monitor score as an API resource or
OAuth scope. Viventium therefore does not scrape the app or call private mobile endpoints. Stress
Monitor screenshots are accepted as bounded PNG/JPEG manual evidence: exact private bytes are
append-only, counted separately from API items, integrity-checked, and available through a read-only
MCP image tool. They are never promoted into structured longitudinal measurements. The official
WHOOP export importer preserves the exact ZIP and every safe entry, including Journal CSVs, while
rejecting traversal, links, encryption, and expansion abuse. These API + export + screenshot lanes
are the supported hybrid boundary. Exact duplicate export bundles reuse the prior immutable run by
content hash, so a recovery click cannot grow the private archive without adding evidence.

Official contract references:

- <https://developer.whoop.com/api/>
- <https://developer.whoop.com/docs/developing/oauth/>
- <https://developer.whoop.com/docs/developing/app-approval/>
- <https://developer.whoop.com/docs/developing/webhooks/>
- <https://support.whoop.com/s/article/How-to-Export-Your-Data>

#### Runtime and private-state boundary

Clean install, upgrade, and start paths must bootstrap the pinned `Viventium-Health` component and
materialize a self-contained owner-only Python runtime at
`~/Library/Application Support/Viventium/health/runtime/`. LibreChat invokes only that installed
artifact by default. The component source commit, parent lock pin, generated MCP configuration, and
installed artifact manifest must agree before the integration is called healthy.

OAuth clients/tokens, raw response bodies, private Life projections, logs, and real health-derived
artifacts are never tracked in this public repository. The optional Life projection contains only
connector freshness/status/count metadata and opaque hashes; correlation reads the private archive,
not a duplicated normalized health corpus.

#### 2026-08-09 implementation and acceptance status

- The parent lock pin, isolated runtime installer, public `health` command, generated read-only MCP
  definition, installed runtime manifest, owner-only permissions, and existing archive preservation
  pass automated and live checks. A fresh external clone/install was not run in this session.
- The WHOOP acquisition LaunchAgent is configured and loaded. Historical exact evidence remains
  readable, but the latest provider pulls report `authorization_failed`; analysis therefore remains
  inactive until the owner completes WHOOP OAuth again.
- A real Workbench refresh inspected 30 bounded record summaries, included 18 exact record bodies
  across the available resource families, reported zero read/integrity failures, and exposed only
  counts/status in the UI manifest. The optional Life projection was owner-only and metadata-only.
- The first live Sol/xHigh manual correlation completed through GlassHive and callback reconciliation,
  with memory writes off and zero memory proposals. Browser artifact validation correctly rejected
  its sidecar because `staleAfter` equaled `generatedAt`.
- The health artifact contract now requires UTC timestamps, `P1D`, and `staleAfter` strictly 24 hours
  after `generatedAt`; a managed template revision and regression test preserve that repair without
  overwriting owner-customized prompts. The immediate corrected rerun reached dispatch but was
  blocked by the configured provider usage limit before inference, so post-fix live artifact
  acceptance remains partial rather than assumed.
- The managed health-context template explicitly treats provider records and every adjacent
  snapshot field as untrusted data, forbids embedded instructions from changing worker behavior,
  and preserves owner-edited prompts during revision reconciliation.

#### 2026-08-10 full-history hardening status

- The pinned and installed `Viventium-Health` artifact now exposes the explicit all-history import,
  keeps daily correction pulls unchanged, and preserves the existing archive and loaded acquisition
  schedule.
- Component acceptance passes 29 synthetic tests plus two live public WHOOP contract checks. The
  live contract proves collection `start` is optional on all four collection resources. Parent
  runtime, MCP, health-context integration, and public-help coverage passes 25 focused tests.
- Full-history regressions cover optional open start, fixed end, pagination completion, explicit
  safety-cap failure, minute-budget pacing, headerless 429 fallback, page-level rotating refresh,
  exact uncapped run counts, archive-path safety, and private/public boundaries.
- A review-only independent pass initially found scale-path defects, then verified every repair and
  approved the final component diff with no Critical or Important findings.
- Owner OAuth completed with all six documented read scopes plus offline refresh. The explicit
  all-history run completed across all six official resources with one fixed capture end and no
  minimum-time filter: 15 cycles, 14 recovery records, 14 sleeps, 6 workouts, one profile, and one
  body measurement (51 provider items total). All six archived response pages passed the stored
  SHA-256 integrity check; the wider archive inventory reported 48/48 complete summaries with
  hashes.
- The one acquisition LaunchAgent is loaded for 06:00 local time. A real three-day correction run
  completed all six resources and its last process exit was zero. The one `health_context`
  Scheduling Cortex definition is active for 06:15 `America/Toronto`, keeps memory writes off, and
  never pulls WHOOP itself. Activation exercised the catch-up path: the missed scheduled occurrence
  completed through GlassHive and advanced the next due time to 06:15 the following day.
- The scheduled run created a complete bounded snapshot (48 summaries inspected, 18 exact bodies,
  zero read failures, zero truncations) and a fresh schema-v2 `health_context` artifact. Workbench
  accepted it with 4/4 source references resolved, zero ungrounded claims, `P1D` expiry, zero
  proposed actions, and zero memory proposals. Browser reload preserved the enabled schedule,
  completed scheduled run, complete snapshot, passed artifact, and memory-off state.
- Periphery ingestion now enforces the owner-only filesystem contract on every discovered sidecar,
  including artifacts beyond the 100-item index limit, and on the body-read path. A review-only
  independent security pass found no remaining Critical privacy/integrity issue and approved live
  application. Live acceptance found 26/26 discovered sidecars and paired Markdown files at `0600`,
  the relevant private directories at `0700`, and an available index with zero privacy blockers.
- The optional Life health projection refreshed to complete, remained `0700`/`0600`, and contained
  connector status/count/hash metadata only. No provider body, record locator, or credential was
  duplicated there.
- The next ordinary wall-clock occurrence had not elapsed when this acceptance report closed. The
  successful scheduler-owned catch-up run proves the real recurrence path; the next due time is
  persisted. Live disconnect/revoke was intentionally not run because the requested end state is an
  ongoing connection; synthetic disconnect coverage remains the safe regression lane.
- Native CLI provider-limit control records now retain a structured `provider_quota_exhausted`
  failure class through the GlassHive callback, Scheduling Cortex ledger, and Workbench UI. The
  evidence rule accepts structured JSON or a native `ERROR:` stderr record only when stdout has no
  structured result; ordinary task prose cannot manufacture the class. A post-restart manual run
  and browser reload proved the visible/persisted classification. Corrected artifact inference is
  still blocked until provider capacity returns.
- The classification repair is currently validated in an already-dirty GlassHive component
  checkout whose local head differs from the parent component pin. It is not release-ready until
  that component change is isolated, reviewed, committed, and the parent pin/delivery artifacts are
  updated.

Cloud vendor APIs can support owners on iOS and Android without a Viventium mobile app, although the
vendor's app may still be required to sync the device. Apple HealthKit, Android Health Connect, and
Samsung Health are device-local stores and require native mobile bridges for continuous first-party
access. Official manual exports are the preferred no-code value test before continuous plumbing.

Connectors must act as faithful evidence couriers. They must not hard-code wellness thresholds,
diagnoses, causal claims, or generic recommendations. Browser scraping, private mobile APIs, and
reverse-engineered cloud protocols are isolated research fallbacks, not production integration
contracts.

The 2026-07-26 research inventory, source links, isolated validation, privacy guardrails, and proposed
one-owner OAuth acceptance plan live in
`qa/periphery-nightly-insights/reports/2026-07-26-wearable-data-integration-spike.md`.

## Extensibility

The system should support future modules without growing a tangle.

A module should declare:

- `moduleId`
- title
- owner requirement doc
- schedule/cadence
- executor
- input snapshot contract
- output schema
- retention/TTL policy
- surfacing policy
- memory write mode
- QA owner

Do not build a large registry before it is earned. Start with the existing Workbench scheduled prompt
path and generalize only when at least two modules prove the same configuration shape is real.

## Automation Model Policy

Unattended analytical automations use the compiled runtime tuple, currently `gpt-5.6-sol` with
`xhigh` reasoning. This includes Workbench/GlassHive scheduled analysis in this pipeline and OpenAI
memory hardening. The compiler, Workbench definition reconciler, Scheduling Cortex dispatch,
GlassHive bootstrap, run ledger, and UI must agree on the requested and effective tuple. Ambient CLI
config, stale per-definition metadata, or an unpropagated route-proof flag must not silently
downgrade it.

This policy applies to this growing private automation pipeline and future analytical modules that
reuse it. The GlassHive host Codex configuration is shared with direct host Codex delegation, so the
same Sol/xHigh deployment default applies there unless explicitly overridden. It does not rewrite
existing `viventium_agent` reminders, latency-sensitive background activation classifiers, voice
reactions, or the interactive conscious-agent route; those have separate owning contracts and must
be migrated intentionally if their requirements change.

## Snapshot Harness Requirement

Real insight quality cannot be evaluated on a messy live corpus without controls.

The private snapshot harness now:

- snapshots bounded memories, recent conversations/messages, schedules, scratchpads, recent run
  ledgers, and the existing background-lens inventory
- labels QA/test/synthetic conversations, messages, and scratchpads by structured metadata or exact
  private id instead of deleting them or adding runtime keyword classification
- creates synthetic eval cases and supports private-real scheduled runs against the same projection
- keeps raw private content outside public QA
- reports public-safe counts, hashes, statuses, and conclusions only

The harness tests:

- no hallucinated evidence
- confidence calibration
- no unsupported current facts
- no unsupported medical claims
- stale artifact handling
- no direct memory writes
- no private leakage
- no verbatim copying of bounded private evidence into generated insight text
- no nagging or intrusive surfacing
- no overfitting to one anecdote or one test phrase

The initial bank contains material-signal, honest-no-signal, degraded-source, medical-humility,
unlabelled-QA-noise, and stale-correction cases. Provider/auth/quota failures are operationally
classified and are not scored as model negatives. Raw completions and private snapshots remain in
private runtime storage; public QA records only sanitized counts, hashes, status, and conclusions.
The compact nightly prompt and schema constants live in one dependency-free contract module shared by
Workbench execution and the eval harness, so the two paths cannot quietly drift apart.

## Surfacing Policy

Periphery insights should be useful, not noisy.

Allowed surfacing modes:

- **On demand:** user asks what Viventium noticed, what they are missing, or what the risks are.
- **Contextual pull:** main agent is doing deep planning, prioritization, health reflection, or
  postmortem work and chooses to inspect the periphery.
- **Approved high-signal alert:** future policy may allow rare surfacing when a high-confidence,
  time-sensitive risk exists and the user has approved that class of alert.

Forbidden surfacing modes:

- routine nagging
- generic productivity pressure
- ungrounded health warnings
- "I had a thought overnight" filler
- hidden main-prompt pressure that makes Viventium sound constrained or over-instructed

## Documentation And QA Ownership

This document owns the cross-cutting product truth for Viventium Periphery and nightly insight
modules.

Related implementation surfaces remain owned by their existing docs:

- Scheduling recurrence and ledgers: `11_Scheduling_Cortex.md`
- saved-memory boundaries and health-state decisions: `20_Memory_System.md`
- retrieval/inventory/file-search patterns: `32_Conversation_Recall_RAG.md`
- prompt placement and token efficiency: `49_Prompt_Architecture_and_Token_Efficiency.md`
- background cortex lenses: `02_Background_Agents.md`
- private/public artifact safety: `40_Public_Private_Boundaries_and_License_Matrix.md`

QA owner:

- `qa/periphery-nightly-insights/`

No implementation is complete until it connects:

feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap.

## Approval Gates

Before activating a new risk-radar or health-pressure routine:

1. The user approves the periphery architecture and surfacing policy. Status: approved and locally
   accepted for the risk-radar pilot on 2026-07-11.
2. Current nightly executor failures are classified and repaired or explicitly bounded. Status:
   complete for the pilot; fresh post-restart GlassHive execution completed with requested/effective
   Sol/xHigh, first-attempt callbacks, a successful parent ledger, and a validated v2 artifact.
3. Existing nightly reflection/cortex coverage is reviewed to avoid duplicate modules. Status:
   complete for Phase 0; reuse the current nightly reflection/cortex path first.
4. The private snapshot harness design is approved. Status: implemented with bounded evidence,
   structured exact-id labels, retention, degraded-source handling, and private-real/synthetic evals.
5. The first risk-radar pilot is run with memory writes disabled. Status: active locally, repeatedly
   completed, and accepted through Workbench, browser, logs, DB, and artifact validation.
6. Health-pressure persistence is decided separately from risk-radar scratchpads. Status: separate
   design track; do not persist it through the periphery scratchpad path by default.
7. WHOOP correlation is approved as an opt-in, memory-off health-context routine after fresh
   provider authorization and accepted grounded output. Status: connected and active; a real
   scheduler catch-up completed, a fresh artifact passed, and the next 06:15 run is persisted.

## Cognitive Control-Plane Map

The three recurring lanes are intentionally separate:

| Lane | Trigger | Owning execution path | Evidence | Mutation authority |
| --- | --- | --- | --- | --- |
| Saved-memory hardening | local macOS schedule | direct memory-hardening wrapper | trigger receipt, run summary, provider/vector telemetry | bounded memory maintenance only |
| Prompt Workbench nightly | scheduler definition | placeholders → GlassHive → callback → scheduler ledger → Workbench | definition, worker run, callback, ledger, visible result | scheduled prompt's declared work |
| Codex nightly QA | Codex automation | `cognitive-integrity --json` plus read-only evidence review | integrity report and sanitized audit | none; observer only |

The observer must open scheduling SQLite with an explicit read-only storage mode. Constructing an
ordinary scheduler store is not observation: schema initialization, mirror sync, sanitization, and
stale-run reconciliation can all write. The selected App Support root owns the database path; a
test/dev observer must never fall through to canonical production state.

The joined map also consumes privacy-safe per-turn saved-memory read/writer receipts. This separates
"configured" from "observed healthy" and prevents a working read path, healthy independent
hardener, or completed Workbench nightly from hiding an immediate-writer auth failure.

These lanes must never infer one another's health from a shared timestamp or output file. The
integrity report is the canonical cross-lane map; it does not become a fourth scheduler or a repair
mechanism. A nightly run is not healthy merely because another lane ran, and an observer firing
before a product routine's due time plus grace is `NOT DUE`, not a product failure.
