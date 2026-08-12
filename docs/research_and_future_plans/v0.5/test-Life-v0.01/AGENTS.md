# Life — Canonical Agent Operating Rules

**Purpose:** keep every human and AI collaborator oriented, privacy-safe, evidence-grounded, and tidy
inside this Life folder.

**Authority:** this file is canonical for agent behavior in this tree. More specific `AGENTS.md`
files may add local rules but may not weaken privacy, evidence, authority, or confirmation rules.

## 1. Read before acting

For every mission:

1. Read this file.
2. Read `CURRENT.md`.
3. Read the closest project or area `README.md`.
4. Inspect the relevant source registry entries and their health.
5. Read only the smallest relevant Life slice before expanding.
6. If working in `Workspaces/<agent-type>/<date>-<slug>/`, read `MISSION.md`, `CONTEXT.md`, and
   `context/CONTEXT_MANIFEST.json`.

Knowing the whole person means having permissioned access to an organized whole—not injecting or
reading the entire Life tree for every task.

## 2. Protect authority and history

- A newer explicit current document or accepted decision outranks conflicting older history.
- Never delete or rewrite historical evidence merely because the conclusion changed.
- Keep **Fact**, **Assumption**, **Decision**, **Test**, **Result**, **Correction**,
  **Falsified/Limited**, and **Next Evidence Needed** distinct.
- A model-generated summary, pattern, or conclusion is derived until a human or approved governance
  flow accepts it.
- High-stakes legal, health, financial, safety, and relationship changes default to a proposal.
- Never make a summary look verbatim. Link it to its source and label uncertainty.
- Never interpret an unavailable source or failed retrieval as proof that no evidence exists.

## 3. Privacy and permissions

- Follow the sensitivity and access scope in source manifests and local folder rules.
- Default unknown personal material to private.
- Never copy private content into public artifacts, external prompts, logs, screenshots, or QA.
- Never store passwords, OAuth tokens, API keys, cookies, private keys, or secret-bearing URLs here.
- Credentials belong in the operating-system keychain or Viventium's approved runtime config.
- Do not broaden a mission's Life or source access because broader data might be useful.
- Do not send, publish, share, buy, delete, or make an irreversible external change without the
  user's explicit authorization and the active host's confirmation policy.
- Hidden chain-of-thought, private system prompts, and inaccessible platform internals are not
  portable context and must never be requested or fabricated.

## 4. Put each thing in one clear place

Use this routing order:

| Material | Canonical destination |
|---|---|
| Unclassified machine intake | `99_System/intake/` until classified |
| Identity, values, preferences, methods | `Self/` |
| A person or relationship or CRM view | `People/` or `People/CRM/` |
| Domain evidence or decisions | `Health/`, `Legal/`, `Finance/`, `Home/`, or `Learning/` |
| Outcome-oriented work | `Projects/<project>/` |
| Cross-project commitment or routine | `Plans/` |
| Communication view | `Communications/` |
| Calendar event, availability, or schedule projection | `Calendar/` |
| Social profile, publication, or activity projection | `Social/` |
| Place, location history, or travel context | `Places/` |
| Lived event, experience, or event timeline | `Events/` |
| Photo or video index | `Media/` |
| Detailed episodic conversation summary | `Memory/Conversations/` |
| Meeting, call, or imported transcript evidence | `Memory/Transcripts/` |
| Listen-only or ambient observation | `Memory/Ambient/` |
| Pattern, idea, conclusion, risk, opportunity, question | matching `Insights/` folder |
| Agent skill definition or writing guidance | `Skills/` or `Skills/How_To_Write/` |
| Capability inventory | `Tools/` |
| Local/external service inventory | `Services/` |
| Source setup or human-readable source view | `Sources/` |
| Generated dashboard/index | `Views/` |
| Cross-life decision or supersession trail | `Decisions_and_History/` |
| Temporary mission work | `Workspaces/<agent-type>/<date>-<slug>/` |
| Inactive retained history | `Archive/` |
| Schema, private run receipt, provenance, sync, proposal, index | `99_System/` |

Do not create `output/`, `outputs/`, `final/`, `misc/`, `tmp/`, or a second folder for the
same concept at the Life root. Use the active mission workspace, then promote accepted work.

## 5. Project work follows evidence to decision

Every substantial project should make the path inspectable:

`evidence → research → analysis → decisions → plans → artifacts → history`

- Evidence is source material and claim support.
- Research discovers and synthesizes sources.
- Analysis tests interpretations, tradeoffs, and alternatives.
- Decisions record what was chosen, why, when, by whom, and what would change it.
- Plans record commitments and next actions.
- Artifacts are user-facing final deliverables.
- History retains superseded states without controlling the present.

## 6. Conversation memory

For every eligible actual conversation across Viventium or another AI host:

1. Preserve the original source in its authoritative system.
2. Write a timestamped detailed summary under `Memory/Conversations/YYYY/MM/`.
3. Record source, durable source reference, timestamps, participants when known, goals, decisions,
   commitments, corrections, unresolved questions, important evidence/artifacts, sensitivity,
   confidence, and last-sync state.
4. Distinguish user-authored facts from assistant suggestions and later corrections.
5. Update or supersede the summary when the source changes; do not create duplicate competing truth.

Do not save every raw conversation as Markdown merely to claim completeness. Meeting, call, and
imported transcript evidence belongs under `Memory/Transcripts/`; Listen-Only and other ambient
evidence belongs under `Memory/Ambient/`. Those surfaces may link to a conversation, but they must
not be materialized as fake chat history. The summary is episodic memory and navigation, not a
transcript substitute.

## 7. Insights and night workers

- Approved worker definitions live in `Insights/Workers/`.
- Each run writes its private, serializer-redacted manifest and terminal receipt under
  `99_System/night-runs/`; not every agent receives access to that system area.
- Run receipts state source coverage, changes observed, outputs, confidence, failures, blocked
  sources, stale inputs, and remaining work.
- Promote substantive results to the matching insight folder; do not leave the only useful result
  buried in a run log.
- Keep observation, inference, hypothesis, risk, opportunity, and conclusion distinct.
- Every non-trivial claim needs a source reference or an explicit uncertainty label.
- Night workers propose high-stakes or canonical changes; they do not silently apply them.
- Full-world coverage means inventory-wide health and delta checks plus bounded deep reads. Do not
  reread every unchanged byte nightly. Use periodic full audits to detect checkpoint drift.
- Every promoted insight preserves source refs, confidence, blind spots, opportunity costs, what
  would make it wrong, and when it may surface; folders do not replace the sidecar contract.
- Morning Briefs are pull-only by default. Proactive delivery requires an approved opt-in surfacing
  mode, and briefs are never raw worker logs.

## 8. GlassHive and other agent missions

### Shared Viventium conversation mode

A normal Viventium conversation running through a harness is not a delegated GlassHive mission.
In conversation mode, work naturally from the exact selected folder, answer questions, ask useful
clarifying questions, and use native tools when they help. Create or edit user work in Life only
when the user's task calls for it. Do not create `CLAUDE.md`, `CODEX.md`, harness prompts, mission
folders, receipts, evidence scaffolds, runtime logs, transcripts, `.git`, or a `FINAL REPORT:` block
merely because the conversation is harness-backed. Runtime state belongs in Viventium's private
Application Support state.

### Explicit delegated mission mode

Every delegated mission runs inside a worker-created
`Workspaces/<agent-type>/<YYYY-MM-DD>-<slug>/`. Do not work loose in the Life root. The parent waits
for the exact returned `workspace_dir` before writing the context bundle. Host-native execution may
use this Life root directly; sandbox execution receives only its bounded mount/bootstrap material.

The parent host must create:

- `MISSION.md`: exact user goal, constraints, success condition, permissions, and completion gate;
- `CONTEXT.md`: short orientation and read order;
- `context/CONTEXT_MANIFEST.json`: immutable bundle metadata and included/excluded scope;
- `context/conversation.jsonl`: full visible conversation and visible tool evidence the parent is
  authorized to share;
- `context/attachments.json` and `context/life_refs.json`: source-linked inputs;
- `context/deltas.jsonl`: append-only, attributed corrections after the immutable initial bundle;
- bounded `evidence/`, `work/`, `questions/`, `deliverables/`, and `receipts/` folders.

The worker must:

1. Treat the user's goal and explicit constraints as authoritative.
2. Use the simplest capable path and native tools available to its host.
3. Read the manifest before assuming context or capability exists.
4. Keep downloads, scratch work, logs, and partial files inside the mission.
5. Write typed questions under `questions/` only with an actual callback/checkpoint transport; a
   silently waiting file is not a working question round-trip.
6. Check its output against the mission and inspect the actual deliverables before reporting success.
7. Return one `receipts/MISSION_RECEIPT.json` describing evidence, deliverables, changes, assumptions,
   failures, risks, proposed Life promotions, and the independent GlassHive evidence-harness result.
8. Never promote a conclusion, overwrite current canon, or move files outside the mission without an
   approved rule or explicit user instruction.
9. Finish with the line-anchored `FINAL REPORT:` marker required by the GlassHive completion
   contract.

The parent agent must not trust a final sentence alone. It should inspect the receipt, deliverables,
and relevant evidence; challenge material assumptions when needed; then explain the result in its
own voice.

### Full-context boundary

Copy the complete visible history available to the calling surface, including visible tool calls,
results, failures, attachments, constraints, and relevant Life references. Do not copy credentials,
hidden reasoning, private system prompts, or unrelated private data. Append later user corrections
as attributable deltas rather than silently rewriting the original bundle.

If a Feeling capsule is eligible, its content appears once at the tail of the worker instruction
artifact. The context manifest may carry only its reference and hash, never a duplicate capsule.

## 9. Source and sync rules

- `99_System/sources.yaml` is the private source registry.
- Each source declares logical ID, category, method, permission, authority, freshness, retention,
  and health.
- Large archives normally remain at their source; Life stores durable references, checksums,
  indexes, selected imports, and provenance.
- Every sync or collection attempt creates a receipt, including healthy empty results.
- Distinguish unavailable, auth missing, permission denied, timed out, rate limited, unsupported,
  stale, failed, and successful empty states.
- Never claim a source was read or an external action happened without provider/tool evidence.
- Pause and removal must be explicit. Removal of a source registration does not silently erase
  accepted Life artifacts or source history.

## 10. Delivery and final self-check

Before declaring a mission complete:

- Re-read the exact request and success condition.
- Inspect every claimed deliverable as a user would.
- Confirm important claims trace to evidence.
- Confirm current/history and fact/assumption distinctions survived.
- Confirm no secrets, private leakage, unrelated content, absolute machine paths, or duplicate roots
  were introduced.
- Confirm useful outcomes were placed canonically and temporary work remains in the workspace.
- Confirm the GlassHive evidence harness result is present for a GlassHive mission; worker checkboxes
  do not independently prove success.
- Emit the line-anchored `FINAL REPORT:` marker only when an explicit delegated mission contract
  requires it; never add it to ordinary Viventium conversation-mode replies.
- Report what was completed, what was not run, what remains blocked, and what needs user approval.

For a GlassHive completion, the terminal final section begins exactly as:

```text
FINAL REPORT:
```
