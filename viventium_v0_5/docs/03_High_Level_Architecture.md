# Viventium V0.5 High-Level Architecture

> **Pattern:** a local, user-owned personal continuity system around replaceable frontier agent
> bodies. **Status:** proposed and under product-owner review.

## The system in one sentence

Viventium senses the authorized parts of a person's world, maintains a portable persistent self,
assembles the right context and cognition for the present moment, acts through the best available
agent bodies, and compounds what it learns while the person is away.

## The hierarchy

| Boundary | Category | What belongs here |
|---|---|---|
| **Outside Viventium** | The person's world | Communications, calendars, files, notes, projects, social activity, health, media, browser research, and AI conversations |
| **Outside Viventium** | Replaceable intelligence | Codex, Claude, ChatGPT, external GlassHive execution workers, and future local/open agents with their native models, tools, browsers, computers, and connectors |
| **Viventium experience** | One relationship, four control doors | MIND, CONNECT, CHARACTER, AUTOMATIONS, plus persistent voice/presence across them |
| **Viventium continuity plane** | Sense and remember | Connection & Presence, source registry, consent, collection/sync workers, health, provenance, receipts, and canonical `Life/` placement |
| **Viventium portable self** | Know and be | `Life/` contains source-linked personal truth; `Brain_Pack/` contains Character, cortices, automations, policies, and evals |
| **Viventium cognitive plane** | Understand, feel, and think | Selective context compiler, one conscious agent, persistent Feelings, activation, and independent background cortices |
| **Viventium work plane** | Act and return evidence | Agent-body adapter, Viventium-owned GlassHive continuity bridge, mission workspaces, questions/deltas, evidence, results, parent evaluation, and receipts |
| **Viventium compounding plane** | Learn while away | Automations, source coverage, delta processing, Sleep Growth, synthesis, challenge, proposals, Insights, and Morning Briefs |
| **Viventium trust plane** | Keep the person in control | Local-first storage, open formats, least privilege, provenance, freshness, health, interruption, approval, correction, export, and deletion |
| **Local runtime state** | Operate without polluting portability | Credentials, provider sessions, databases, indexes, queues, caches, logs, Current Feelings, and active-run state |

This hierarchy keeps the ownership boundary honest: Viventium owns continuity and coordination, not
the entire external world and not every intelligence body.

## The single living loop

```text
THE PERSON
   ⇅ messaging · voice · MIND · native AI surfaces

WORLD SOURCES → CONNECTION & PRESENCE → LIFE
                                        ↓
                         LIFE + BRAIN PACK + LIVE STATE
                                        ↓
                           SELECTIVE CONTEXT COMPILER
                                        ↓
               CHARACTER + FEELINGS → CONSCIOUS AGENT
                                         ↕
                              INDEPENDENT CORTICES
                                        ↓
                     AGENT BODY / GLASSHIVE MISSION BRIDGE
                                        ↓
                         RESULT + EVIDENCE + EVALUATION
                                        ↓
                       LIFE/WORKSPACES + MIND + CHANNELS
                                        ↓
      AUTOMATIONS / SLEEP GROWTH → INSIGHTS / PROPOSALS / MORNING BRIEF
                 ├──────────────→ LIFE
                 └──────────────→ THE PERSON / NEXT MOMENT
```

## How each product door maps to the system

| Door | Controls and reveals | It does not own |
|---|---|---|
| **CONNECT** | Connection & Presence: sources, routes, consent, health, freshness, receipts, and Life destinations | Every provider's credential or integration implementation |
| **CHARACTER** | Brain Pack Character plus live Feelings: identity, Nature, ranges, voice, and advanced expression/listening routes | Generic model intelligence |
| **MIND** | The live conscious relationship: conversation, Feelings Current, reactions, cortex activation/contribution, evidence, and correction | The whole Life corpus in every turn |
| **AUTOMATIONS** | Schedules, source coverage, GlassHive missions, Sleep Growth, approvals, history, recovery, Insights, and Morning Briefs | A second hidden decision authority |

Persistent voice and presence are app-shell state, not a fifth destination. Telegram and other
messaging channels are daily surfaces into the same relationship.

## Connection & Presence

This is Viventium's local source-control layer, not a new connector empire.

It owns:

- a registry of sources and channels;
- the user's exact read/write/listen/presence consent;
- which mature route is used: native account, signed-in app/browser, official API, export, or folder;
- coverage, freshness, health, failure class, provenance, and receipts;
- canonical placement into Life or a source-linked external reference.

The provider, host, browser, operating system, or mature adapter keeps credentials and performs its
native integration. Viventium records what was authorized, what evidence arrived, what changed, and
where the accepted projection belongs.

## The portable persistent self

```text
Viventium/
├── Life/                         # what Viventium knows and why
│   ├── CURRENT.md
│   ├── Self/  People/CRM/  Health/  Legal/  Finance/  Home/  Learning/
│   ├── Calendar/  Social/  Places/  Events/
│   ├── Projects/  Plans/  Decisions_and_History/
│   ├── Communications/Email/  Communications/Calls/  Communications/Chats/
│   ├── Media/Photos/  Media/Video/
│   ├── Memory/Conversations/  Memory/Transcripts/  Memory/Ambient/
│   ├── Insights/  Skills/  Tools/  Services/  Sources/  Views/
│   ├── Workspaces/  Archive/
│   └── 99_System/intake/  99_System/night-runs/
└── Brain_Pack/                   # who Viventium is and how it thinks
    ├── Character/
    ├── Cortices/
    ├── Automations/
    ├── Policies/
    └── Evals/
```

Life is not a raw-data dumping ground. It holds human-readable projections, manifests, summaries,
source references, accepted truth, decisions, and evidence links. Large raw archives may remain in
their provider or private object store. Recall/vector indexes are derived runtime state.

`Life/Skills/`, `Life/Tools/`, and `Life/Services/` inventory what exists in the person's world and
the evidence about it. Brain Pack declares which capabilities Viventium may use and how a cortex or
automation behaves. World truth and behavioral capability are not the same category.

Brain Pack is not a runtime database. It contains editable, portable doctrine and tests. Character
stores Nature and voice choices; Current Feelings and reaction trails remain live state. Cortex and
automation files compile into small typed manifests rather than becoming a new workflow language.

`Communications/Email/` is the only human-facing email home. `99_System/intake/` is unclassified
machine intake, not a second Inbox concept.

## The live conscious/subconscious turn

1. A request arrives through MIND, Telegram, voice, or a supported native host.
2. Viventium resolves the current permission, source-health, Life, Brain Pack, memory/recall, and
   surface context into the smallest relevant request envelope.
3. One request-pinned Character/Feeling state shapes the eligible conscious speaking boundary.
4. Fast Phase A activation identifies relevant cortices without blocking the main answer.
5. The conscious agent answers through a selected native body.
6. Independent cortices work in parallel as evidence producers. They do not become extra personas
   and do not inherit the conscious mood.
7. Phase B adds a visible correction or insight only when it contributes new value; otherwise it is
   silent.
8. The UI and receipts preserve activation, status, evidence, interruption, result, and failure
   without exposing internal reasoning.

## GlassHive mutual-context work

GlassHive is not “an MCP tool that disappears with the task.” Viventium owns the mission bridge:

1. Create one mission identity and workspace.
2. Send the complete visible, authorized task context: conversation, attachments, constraints,
   success conditions, verified tool evidence, and relevant `life://` references.
3. Bootstrap the worker with how to navigate the bounded Life/Workspace and where to place work.
4. Exchange attributable questions, answers, approvals, cancellations, and context deltas.
5. Return deliverables, evidence, status, result digest, and a machine-readable receipt.
6. Let the parent inspect the actual work and evidence before speaking for it.
7. Promote accepted deliverables or conclusions into their canonical Life location; keep run state
   and raw worker plumbing outside Life.

Copying conversation history helps fidelity but does not create synchronization by itself. Mission
identity, bounded references, a delta channel, durable callbacks, evidence receipts, and parent
evaluation are the continuity contract.

## Automations and Sleep Growth

The compounding loop is:

`source inventory → coverage/health → changed evidence → selective context → cortex/worker thought → synthesis → challenge → governed proposal → Insights → Morning Brief`

Scheduling owns cadence, catch-up policy, interruption, and run ledgers. The insight module owns its
evidence contract, artifact, retention, and surfacing policy. GlassHive and cortices are reused as
thinking substrates rather than duplicated as a second overnight agent stack.

“Scan the whole Life” means complete inventory coverage with delta-first processing and periodic
full audits. It does not mean rereading every unchanged byte or injecting every private artifact
into one model context. High-stakes conclusions and durable memory changes remain proposals until
accepted.

## Replaceable agent bodies

Codex, Claude, ChatGPT, GlassHive workers, and future local/open agents own their native:

- models and reasoning;
- tools, skills, connectors, browser, computer, shell, and files;
- authentication and provider-specific execution;
- streaming and long-running work behavior.

Viventium passes bounded context, permission, state, and success conditions in; it receives results,
evidence, changes, and receipts out. It does not flatten every body into the lowest common
denominator or recreate their integration catalogs.

## LibreChat's exact role

LibreChat is the current compatibility substrate, not the V0.5 product hierarchy.

Reuse its working conversation records, agent APIs, auth paths, streaming, tools, and existing
Viventium integrations behind stable local contracts while the new experience is proven. Keep its
general UI as an operator/fallback surface. Gradually extract only the Viventium-owned continuity
services whose portability or user experience is materially improved by separation.

## Least-resistance implementation pattern

1. Add a thin local desktop control shell with MIND, CONNECT, CHARACTER, and AUTOMATIONS.
2. Place small stable Viventium contracts in front of existing Feelings, voice/channels,
   memory/recall, scheduler, cortex, GlassHive, and LibreChat services.
3. Use native agent bodies and their integrations through explicit context/result envelopes.
4. Build the local `Life/` projection and `Brain_Pack/` compiler as user-owned formats.
5. Prove one complete continuity loop before expanding the connector catalog or extracting more
   infrastructure.

The architecture succeeds when changing the primary model or host does not erase the relationship,
world model, Character, cortices, automations, overnight learning, evidence, or user control.
