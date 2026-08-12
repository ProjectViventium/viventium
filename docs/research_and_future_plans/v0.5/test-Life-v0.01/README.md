# Life v0.01 — Public-Safe Template

This folder is a concrete draft of the Viventium `Life/` contract. Copy it to a private,
user-controlled location to try the information architecture. The copy in this repository contains
only templates and synthetic examples.

## Start here

1. Read [`AGENTS.md`](AGENTS.md). It is the canonical operating contract for every agent.
2. Edit [`CURRENT.md`](CURRENT.md) into a short map of what is true and active now.
3. Register sources in a private copy of `99_System/sources.yaml`, using
   [`99_System/sources.example.yaml`](99_System/sources.example.yaml) as the public-safe shape.
4. Machine intake may wait under `99_System/intake/`; classify useful material into its
   human-facing home instead of maintaining a competing root inbox.
5. Run agent work inside `Workspaces/<agent-type>/<date>-<slug>/`, then promote only accepted outcomes.

## Folder map

| Folder | Job |
|---|---|
| `Self/` | Identity, values, preferences, boundaries, methods, and personal history |
| `People/` | Relationship context, commitments, and personal CRM views, including `People/CRM/` |
| `Health/` | Health evidence, goals, trends, and user/clinician context |
| `Legal/` | Legal documents, cases, obligations, and evidence |
| `Finance/` | Financial records, plans, decisions, and evidence |
| `Home/` | Household, property, possessions, and domestic operations |
| `Learning/` | Learning goals, notes, curricula, and knowledge maps |
| `Projects/` | Active outcome-oriented work with evidence → research → analysis → decisions → delivery |
| `Plans/` | Cross-project goals, commitments, schedules, routines, and scenarios |
| `Communications/` | Email, chat, call, meeting, Listen-Only, Wing Mode, and transcript views |
| `Calendar/` | Source-linked events, availability, commitments, and calendar views |
| `Social/` | Source-linked social profiles, activity, relationships, publications, and media references |
| `Places/` | User-approved places, location history, travel context, and geographic evidence |
| `Events/` | Lived events and experiences, participants, timelines, evidence, and memories |
| `Media/` | Photo and video indexes or references; large originals remain with their authoritative library |
| `Memory/` | Human-browsable projections split into actual conversations, transcript evidence, and ambient evidence |
| `Insights/` | Human-facing nightly/deliberate patterns, ideas, conclusions, risks, opportunities, questions, and worker definitions |
| `Skills/` | Reusable agent skill manifests and instructions, including `Skills/How_To_Write/` |
| `Tools/` | Available tool/capability inventory, scopes, owners, and health |
| `Services/` | User-owned local/external services and logical endpoints; no secrets |
| `Sources/` | Human-readable source views and import notes |
| `Views/` | Generated single-pane dashboards, indexes, and Morning/Current views |
| `Decisions_and_History/` | Cross-life decisions, rationale, tests, results, corrections, and supersession |
| `Workspaces/` | Bounded agent and GlassHive missions |
| `Archive/` | Deliberately inactive material retained as history |
| `99_System/` | Schemas, source registry, provenance, sync, proposals, private run receipts, and derived indexes |

Email knowledge belongs under `Communications/Email/`. A connected email inbox is a source, not a
second root taxonomy. Temporary unclassified machine intake belongs under `99_System/intake/`.

## Authority model

Life is canonical only for human-authored or explicitly accepted Life artifacts. It is a federated
single pane over systems that keep their own authority:

- chat providers own original message trees;
- saved memory owns compact personalization facts;
- transcript stores own original transcripts;
- recall/search indexes are rebuildable derived state;
- the scheduler owns recurrence and delivery ledgers;
- GlassHive owns mission runtime state;
- keychain/runtime config owns credentials.

Life may reference, summarize, organize, or accept projections from those stores. It must not
silently rewrite them or pretend a generated summary is the source.

Deleting a Life projection is not cross-store forgetting. A deletion workflow must separately
target and verify every Viventium-owned store in scope.

## Naming and portability

- Use simple, descriptive names.
- Timestamp episodic or run artifacts in UTC:
  `YYYY-MM-DDTHHMMSSZ--source--short-slug.ext`.
- Use logical references such as `life://Projects/example/decisions/decision.md` in portable
  metadata. Physical paths are local implementation details.
- Keep indexes and caches rebuildable.
- Never store tokens, passwords, cookies, private keys, or credential-bearing URLs in Life.

## Status

This public-safe fixture is the additive bootstrap source for the current canonical Viventium LIFE
folder. Installation copies only missing content into the private user-controlled folder and never
overwrites personalized files. It excludes `CLAUDE.md`, `CODEX.md`, `.git`, delegated-mission
scaffolding, run receipts, and runtime logs; the template version is recorded in private Viventium
Application Support state. The broader V0.5 source-sync, night-worker, and Insights thesis remains a
design proposal and is not activated by this bootstrap.
