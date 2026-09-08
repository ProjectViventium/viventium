# Feelings and truth seeking

## Outcome

- **AS-001:** Main seeks calibrated, evidence-based truth instead of reflexive agreement,
  disagreement, pessimism, or a naysayer persona.
- Feelings shape judgment and expression but never grant authority, select actions mechanically, or
  become an engagement target.

## Context and evidence

### Responsive context

- **AS-002 / AS-009:** Immediate context and ordinary background detection start alongside Main and
  do not delay the initial answer. Handoff shares authoritative conversation, context, and tool
  state rather than a lossy rewritten recap.

### Later evidence

- **AS-003 / AS-007:** Deep Memory runs independently in the background without blocking the initial
  answer. Its non-empty-source evidence gate controls useful late presentation; later evidence may
  add one continuation but never rewrites the original answer, and silence is valid.
- A visible Deep Memory result requires a successful same-run authorized retrieval receipt with
  relevant evidence. Model echo or coincidence does not count.

## Consultation

### Consultation graph

- **AS-004 / AS-005:** Main may consult Reality Check and then Red Team when judgment needs pressure-testing;
  Main owns confidence and the final response.
- **AS-006:** Return edges are loop-safe and the configured step budget is bounded but sufficient.
  Add deduplication machinery only after measured duplication.

### Time budgets

- **AS-010:** Time limits are typed, justified, recoverable, authorization-compatible, and
  interruptible by Stop.
- Consultants challenge with evidence; they do not become automatic opposition, detached final
  speakers, or a required ceremony for every turn.

## Feeling state

### Schema

- **ONB-012:** Every retained Feelings UI and prototype consumes the canonical nine-band schema or
  remains explicitly historical.
- Feeling state is private, owner-scoped, versioned, bounded, and persistent. Runtime owns numeric
  state and decay; the model owns appraisal and expression.
- No runtime keyword, phrase, or event-specific branch maps content to an emotion.

### Parallel Work propagation

- **HARD-002 / HARD-003:** Pin one Feeling capsule per request and propagate it once to Main and every
  eligible direct worker. Providers receive the capsule, never private state access.

### Parallel worker propagation

- **PW-058:** Propagate the request-pinned capsule exactly once only to eligible direct workers when
  the configured mode permits it. Scope-off workers receive none, and no worker impersonates Main.
- **OPEN-012:** The exact eligibility boundary between persona-bearing workers and non-persona
  specialists remains unresolved in [the decision record](../../decisions/direct-worker-eligibility.md).
  Active truth must not assume either option until adoption and named real-surface proof.

## Failure and safety

- Missing memory, search, or consultant capability is disclosed as its real state and does not
  become invented support.
- Later evidence cannot mutate prior visible output or committed effects.
- No public evidence contains private Feeling values, capsules, prompts, memories, or user data.

## Owners and QA

- Feeling state and capsule: nested LibreChat `packages/api/src/feelings/` and data schema
- Appraisal and prompt placement: nested LibreChat Viventium services and registered prompt sources
- Truth agents and retrieval: agent configuration plus Prompt Workbench-owned sources
- QA: `qa/emotional-cortex/`, `qa/anti-sycophancy/`, `qa/red-team-cortex/`, and
  `qa/conversation-recall-rag/`

Acceptance uses an isolated governed account and covers balanced supported/refuted judgments,
ordinary no-consult controls, retrieval proof, Web and applicable Telegram/audible Voice behavior,
failure and recovery, persistence, restart, Stop, refresh, and cleanup.

## Detailed contracts

- [Red Team Cortex](../29_Red_Team_Cortex.md)
- [Emotional Cortex And Feeling State](../54_Emotional_Cortex_And_Feeling_State.md)
- [Anti Sycophancy and Truth Seeking](../58_Anti_Sycophancy_and_Truth_Seeking.md)

### Completed insight recovery and lifecycle

The owning completed-Cortex delivery contract is in
[Parallel Work](../55_Parallel_Work_Orchestration.md#completed-cortex-acceptance-and-presentation).
Immutable envelope or ledger-identity conflicts quarantine the exact pending outbox bytes with a
typed reason and timestamp; quarantine is neither delivery nor deletion. There is no automatic
requeue. Unknown and transient failures retain bounded retry. Total Mongo unavailability cannot
be reported as durable acceptance.

Visible-generation cleanup (`generation_completed`) does not cancel background cognition or
Emotional Reaction. Intentional owner cancellation, such as Stop or maintenance yield, remains
binding. Only a fired execution deadline is a timeout. An accepted model result and persisted
Feeling version are supporting evidence; they do not alone prove visible or audible delivery.
