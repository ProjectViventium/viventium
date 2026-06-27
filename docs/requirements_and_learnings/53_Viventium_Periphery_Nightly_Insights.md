# Viventium Periphery And Nightly Insight Routines

**Status:** Approved direction; Phase 0 metadata path implemented 2026-06-25
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

Phase 0 implementation:

- Prompt Workbench exposes an authenticated per-scheduled-prompt metadata endpoint for private
  periphery sidecars.
- The endpoint returns sidecar filenames, relative private paths, timestamps, confidence/severity
  labels, stale/TTL fields, source-reference counts, scheduled-run-reference hashes, markdown
  existence, and content counts.
- The endpoint does not return markdown bodies, raw source refs, raw observations, raw risks, raw
  blind-spot text, raw opportunity text, local absolute paths, or private run detail text.
- Malformed sidecars are listed as invalid metadata with a reason instead of crashing or pretending
  insight exists.
- The built-in Workbench nightly prompt asks the existing private nightly worker to write one
  `risk_radar` sidecar pair for each run, including an honest low-signal/no-result artifact when
  strong evidence is missing.
- Workbench startup seeding reconciles the built-in nightly definition and scheduler task so the
  live scheduled run receives the sidecar contract after a managed Workbench restart.
- This is still not conscious-chat surfacing. It does not inject periphery into the main prompt or
  create a saved-memory key.

## Awareness Without Prompt Bloat

Risk, opportunity, and blind-spot artifacts should not be inserted into the main prompt by default.

The preferred first awareness mechanism is a small config-backed instruction, not a new saved-memory
key:

- Viventium may have private periphery scratchpads.
- When the user asks for blind spots, risks, opportunity costs, prior nightly insights, deep
  planning, or self-review, inspect the periphery index or ask a local worker to read the relevant
  private artifact.
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

## Snapshot Harness Requirement

Real insight quality cannot be evaluated on a messy live corpus without controls.

Before trusting nightly predictions, create a private snapshot harness that:

- snapshots memories, conversations, schedules, scratchpads, and recent run ledgers
- labels QA/test/synthetic conversations instead of deleting them
- creates synthetic and private-real eval cases
- keeps raw private content outside public QA
- reports public-safe counts, hashes, statuses, and conclusions only

The harness must test:

- no hallucinated evidence
- confidence calibration
- no unsupported current facts
- no unsupported medical claims
- stale artifact handling
- no direct memory writes
- no private leakage
- no nagging or intrusive surfacing
- no overfitting to one anecdote or one test phrase

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

1. The user approves the periphery architecture and surfacing policy. Status: approved for Phase 0.
2. Current nightly executor failures are classified and repaired or explicitly bounded. Status:
   classified for Phase 0; recent failures are terminal GlassHive callback/evidence-compliance
   failures, while the same canonical path also completed successfully on 2026-06-25.
3. Existing nightly reflection/cortex coverage is reviewed to avoid duplicate modules. Status:
   complete for Phase 0; reuse the current nightly reflection/cortex path first.
4. The private snapshot harness design is approved. Status: not implemented in Phase 0.
5. The first risk-radar pilot is run in propose-only mode. Status: not activated in Phase 0.
6. Health-pressure persistence is decided separately from risk-radar scratchpads. Status: separate
   design track; do not persist it through the periphery scratchpad path by default.
