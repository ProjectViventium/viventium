# QA

This folder is the public-safe QA operating system for Viventium. It is the place where expected
behavior, test cases, user-grade evidence, and regression history stay organized as the product
changes.

Use [`catalog.yaml`](catalog.yaml) to find a capability and its durable acceptance journey.
Consolidated `qa/<capability>/cases.yaml` files route to the existing detailed `sourceInventories`;
they do not replace those banks or claim execution. Candidate-bound reports own results.

## Operating Contract

- Quality is owned by every developer and AI agent touching the product, not by a later cleanup pass.
- Keep one living QA source of truth per feature or flow under `qa/<feature>/`.
- Before a non-trivial feature, bug fix, runtime change, installer change, or release claim:
  1. read the relevant `qa/<feature>/README.md` and `qa/<feature>/cases.md` when they exist
  2. add or update the cases for the behavior being changed
  3. run the smallest relevant automated tests
  4. run user-grade QA for every affected user-visible surface
  5. save a public-safe result report under the feature folder
- A bug is not fully fixed until the production miss is promoted into a reusable synthetic regression
  case, with expected outcome and rerun instructions.
- Existing QA scope must be revisited when touched code can affect that feature. Do not create a new
  isolated report and leave the living feature cases stale.

<a id="real-surface-proof"></a>
<a id="surface-gates"></a>
<a id="supporting-evidence"></a>

## Full-View Evidence Gate

This is the prompt every developer and AI agent must satisfy before saying user-visible work is done:

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

1. Name the feature, owning requirement, user use case, QA case ID, expected result, actual evidence,
   and remaining gap or residual risk.
2. Use the feature like a user through the real product surface: browser/computer, Telegram, voice,
   installer, CLI, MCP/tool, scheduler, GlassHive, or the applicable public entrypoint.
3. Inspect supporting evidence from the owning code path, docs and nested docs/repos, scripts or QA
   harnesses, logs, DB/state/persistence, generated config, shipped/prebuilt artifacts, and runtime
   outputs when those surfaces apply.
4. Compare the visible UI/UX or delivered result with the supporting evidence and the documented
   expected behavior.
5. Record exactly what was run, what was not run, what evidence proves the result, and what fix
   remains for any mismatch.

If a required real user path cannot be run, the result is `BLOCKED` or `PARTIAL`, not pass. Mocks,
unit tests, API responses, logs, DB rows, source inspection, or another model's review can support
the finding, but they cannot replace required user-path evidence.

`CORE-009` requires direct, current, candidate-bound evidence for every claim that work was accepted,
running, completed, delivered, recovered by fallback, backed by memory/tools, routed through a named
model or Feeling state, or ready for release. A neighboring subsystem, historical pass, planned
callback, log-only inference, or merely reachable process cannot prove a different claim.

<a id="traceability"></a>

## Source-Audit And Alignment Contract

The public-safe source-family receipt is
[`requirement_source_coverage.yaml`](../docs/requirements_and_learnings/requirement_source_coverage.yaml).
Exact task pointers, prompts, screenshots, attachments, message hashes, and per-message dispositions
remain in a private verified annex. The public receipt is a hand-maintained audit artifact; it is not
the generated product/service registry and cannot prove wording that was not retained. It is also
not the 360-row stable-ID inventory; exact ID-by-ID coverage remains private. Authorized maintainers
can locate receipt `VSA-2026-08-30` in the project's private companion repository under curated
private docs; request access from the repository owner. The private 360-row crosswalk is the exact
per-requirement inventory for expected behavior, provenance,
disposition, owner, acceptance target, current canonical evidence, and remaining gap. It has
separate owner-path, natural-use-case, QA-case, and join-status fields. Every unresolved join has a
stable `MISSING-JOIN-<requirement-id>` record; a named subsystem is not mislabeled as an exact owner
path, and an absent QA case is not invented. The public file stays at source-family granularity so
it does not duplicate product truth or expose private source material.

| Requirement ID | Contract | Acceptance owner |
| --- | --- | --- |
| `GOV-004` | Keep a private source/message ledger and a public-safe source-family, requirement, QA, evidence, and gap receipt. | `QASYS-002`, `DOCIMPL-001` |
| `GOV-005` | Map each retained requirement to one current owner, natural use case, QA case, expected result, actual evidence, and remaining gap. | `QASYS-002`, `QASYS-004` |
| `GOV-006` | Label current truth, history, proposals, superseded ideas, review findings, uncertainty, and open choices distinctly. | `DOCIMPL-001` |
| `GOV-007` | Revalidate against primary sources before correcting contradictions, stale status, broken links, owner gaps, or overclaimed evidence. | `QASYS-002`, `DOCIMPL-001` |
| `GOV-008` | Owning sources must give future developers the relevant background, goal, exact behavior, edge cases, integration boundaries, and development constraints. | `DOCIMPL-001`, `DOCIMPL-007` |
| `GOV-009` | “Fully aligned” means no recoverable requirement is missing, contradicted, assigned to the wrong owner, backed only by stale evidence, or represented by an overclaimed result. | `QASYS-002`, `QASYS-004` |
| `GOV-010` | Prefer the smallest reusable structural correction and sparse, obvious UI; do not turn one complaint, prompt, provider, or machine into a special-case product branch. | `DOCIMPL-001` |
| `GOV-011` | Prove the affected real Browser/Desktop/Telegram/Voice path and its supporting code, docs, state, logs, generated/shipped artifacts, and runtime identity when applicable, then report the result briefly and truthfully. | `QASYS-004`, `DOCIMPL-007`, `CORE-015` |
| `GOV-012` | When iterative independent review is requested, run at least two fresh-context reviews and revise between them. Continue toward the 8/10 bar for at most four loops; never inflate a score or claim completion only to cross the bar. After that loop, run any separately requested Claude review-only pass as a distinct review and reconcile its findings without treating it as test evidence. | `QASYS-010`, `QASYS-UC-004`, review receipt, and affected QA owners |
| `GOV-013` | Persist through routine local blockers by using already-authorized local setup, browser, and computer paths. Do not ask the user to repeat ordinary in-scope setup, broaden authority, or bypass a real approval or security boundary. | `QASYS-023`, `QASYS-UC-017` |
| `GOV-015` | A user-facing placement or design change requires product-specific visual judgment plus real responsive, light/dark, interaction, keyboard, and accessibility QA. Independent design review supports but never replaces the user path. | `QASYS-024`, `QASYS-UC-018` |
| `GOV-021` | Retain only a sourced behavior, safety, compatibility, or user-experience gate; do not add ceremonial checks, date-bump stale cases, recreate historical reports, broaden architecture without a proved need, or relabel unrun work to make coverage look complete. | `QASYS-002`, `QASYS-004` |
| `GOV-022` | Match inspection and verification to the owning trigger-to-visible-result flow and its real blast radius. | `QASYS-004`, `DOCIMPL-001` |

An opaque source alias and digest prove only that the public family is joined to the retained private
source set. They do not disclose private text, replace exact-message eligibility checks, turn a
screenshot label into a requirement, make dirty bytes durable, or convert an unrun product case to
`PASS`.

## Feature Inventory And Natural Use-Case Gate

QA starts from the full feature map, not from the one symptom that happened to be reported. Before a
feature, bug, runtime, installer, or release task is accepted:

1. Build or refresh the checklist from the complete feature inventory in
   [`docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md`](../docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md),
   [`qa/feature-user-use-case-checklist.md`](feature-user-use-case-checklist.md), the owning
   requirement docs, nested repo docs, scripts, tests, and runtime surfaces.
2. For every affected feature, enumerate the natural user use cases a real user would obviously try:
   happy path, first-run/empty state, connected-account or missing-auth state, degraded dependency,
   retry/recovery, interruption/cancel/update, persistence/reload/restart, cross-surface parity,
   generated or shipped artifact verification, and public/private safety.
3. Treat that list as a checklist. Each applicable use case must be `PASS`, `FAIL`, `BLOCKED`, or
   `PARTIAL` with evidence. Unrun use cases stay visible; they do not disappear into a summary.
4. Execute the checklist like a user on the real surface when the feature is user-visible:
   browser/computer, voice/LiveKit, Telegram, installer, CLI, MCP/tool, scheduler, GlassHive, or the
   supported public entrypoint.
5. Observe the screen or delivered result and compare it with logs, DB/state, source, generated
   config, scripts, nested docs/repos, and shipped artifacts that own or prove the behavior.
6. If a feature depends on local infrastructure, record that prerequisite as its own checklist item.
   For example, local Web Search requires Docker-backed SearXNG/Firecrawl unless hosted providers are
   configured. "Docker is off" is a distinct finding that must be caught before accepting a vague
   user-visible "search failed" answer.

An escaped user-visible failure must add a synthetic public-safe regression case to the owning
`qa/<feature>/cases.md` and, when it crosses surfaces, to each affected owner. For example, a voice
call asking the agent to look something up is not only a playground case and not only a web-search
case; it is the intersection of voice, web search, agent capability config, tool-call persistence,
logs, and user-facing wording.

## Feature Folder Standard

New or actively touched feature QA folders should converge on this shape:

- `qa/<feature>/README.md` - scope, owning docs, surfaces, environments, quality bar, and latest status
- `qa/<feature>/cases.md` - durable test case catalog with case IDs, expected outcomes, automation, and
  last-result pointers
- `qa/<feature>/coverage.md` - optional coverage matrix for case-heavy features that need
  requirement/agent/surface-to-case traceability
- `qa/<feature>/reports/YYYY-MM-DD-<short-topic>.md` - dated execution evidence and residual risks
- `qa/<feature>/artifacts/` - optional public-safe screenshots, traces, or sanitized snippets

Legacy folders may still have a flat `report.md`. When touching them, keep existing links working and
add missing `cases.md` or `reports/` structure instead of scattering another standalone note. Track
remaining legacy gaps in [`_migration.md`](_migration.md).

Use the templates in [`_templates/`](_templates/) when creating or refreshing a QA area.

## Required Case Metadata

Each case should make these fields obvious:

- `Case ID`: stable, feature-prefixed, and reusable in code comments or test names
- `Requirement`: link to the owning requirements doc or feature section
- `User Outcome`: what the user must see, receive, hear, or be able to do
- `Surfaces`: Web UI, Telegram, Voice, Scheduler, installer, MCP, CLI, or API
- `Preconditions`: account state, connected services, fixtures, flags, and runtime assumptions
- `Steps`: human-repeatable steps, plus automation command when available
- `Expected Result`: visible pass criteria, persistence criteria, and any forbidden output
- `Evidence`: where to find sanitized reports, logs, screenshots, traces, hashes, or DB counts
- `Last Run`: a structured record containing:
  - `Status`: one canonical overall result: `PASS`, `FAIL`, `PARTIAL`, or `BLOCKED`; use `NOT RUN`
    only before any candidate execution exists
  - `Date` and `Environment`: dev, installed local production, clean install, or another named
    supported surface
  - `Artifact identity`: source/nested commit, parent pin, built artifact, and active installed
    artifact identity when applicable
  - `Actual user path`: what was clicked, spoken, heard, viewed, refreshed, or delivered
  - `Visible/audible evidence`: the user-facing outcome that proves or disproves the requirement
  - `Supporting evidence`: relevant network, logs, DB/state, generated config, and artifact parity
  - `Not run / residual gap`: every required branch or surface still missing
  - `Report`: the dated public-safe result link

Focused automation may be recorded as a supporting sub-result. If the case requires a real user
path and that path was not run, the overall Last Run remains `PARTIAL` or `BLOCKED`; an automated
pass is never promoted to user-grade `PASS`.

Qualified labels such as `PASS-AUTOMATED`, `PASS-LIVE`, `FAIL-ANALYSIS`, or `PARTIAL-SOURCE` may
describe supporting layers in prose or dedicated evidence columns. They must not replace the one
canonical overall result. `PENDING` is not a status; use `NOT RUN` and name the missing candidate or
prerequisite.

Every `NOT RUN` overall result records its immutable first-cataloged date inline as
`cataloged YYYY-MM-DD` or, for a machine-readable owner, as `catalogedOn`. A documentation review
must never reset that date. Cataloged `NOT RUN` debt older than 90 days is indexed in
[`stale-case-triage.yaml`](stale-case-triage.yaml). Re-triage does not change the original catalog
date or imply execution. The deterministic gate enforces review age plus exact stale-marker counts
and marker-line digests. It detects current source/manifest drift; review and protected history must
reject a coordinated reset of both the original date and its manifest entry. Reviewing this debt during
the owning feature's next change is a separate process obligation; the manifest does not pretend the
test can infer when that change occurs.

## User-Grade QA Bar

Mocked or unit-only checks are not enough for user-facing behavior. For browser-visible flows, use
Playwright CLI or an equivalent real-browser harness. The acceptance loop is:

`real browser prompt/action -> visible UI outcome -> inspect expanded/detail states -> refresh or
persistence check when relevant -> backend/log/DB confirmation -> final model/runtime wording does
not contradict the visible state`

Logs, DB rows, API responses, source inspection, model completions, and unit tests are supporting
evidence, not substitutes for any required visible-UI, detail-state, persistence, or wording step.
Skipping the visible browser step is not acceptable for browser-visible behavior even when backend
evidence says the operation succeeded.

For example, background-agent cards are not accepted just because logs say Phase B ran. QA must prove
the browser shows named cards, expanded cards contain the expected result/status, persistence survives
reload when required, stored message parts match the visible surface, and the main answer does not
claim the background work has not run.

For non-browser surfaces, use the closest real user loop:

- Telegram: send/receive through the bot path, then verify delivery ledger and stored message parts.
- Voice or LiveKit: run the actual call/playground path, then verify synthetic or sanitized
  transcript evidence, latency, interruption, and final spoken/text state. For TTS/STT,
  browser-audio, voice routing, transcription, interruption, or observability changes, first prove
  the changed code/config is present in the active runtime artifact being tested: source checkout,
  generated config, built artifact, and installed/running process as applicable. Record public-safe
  timestamped evidence of what was heard or delivered and correlate it with logs, DB/state, generated
  config, and owning code before marking `PASS`. Instrumentation-only confidence, source inspection,
  logs, DB rows, unit tests, model review, Claude review, or "the next call should show it" is
  `PARTIAL`, not acceptance. See `qa/modern-playground-voice/cases.md` `MPV-014` for the reusable
  post-change voice-fix acceptance case.
- Scheduler: create or trigger the schedule through the product path, then verify execution, delivery,
  ledger, and catch-up behavior.
- Installer or CLI: run the public command, then verify the installed/running artifact rather than only
  source code.
- MCP/tool flows: verify the model-visible tool contract, auth state, tool result, final answer, and
  failure copy.

For evidence-retrieval tools such as web search, QA must prove whether "no answer" means a successful
empty search or an operational failure. Required failure classes include provider unavailable,
timeout, rate limit, auth/config missing, request rejected, unsupported configuration, and local
prerequisite unavailable. Named-entity/contact/date/current-fact lookups must exercise the documented
browser or local-delegation fallback when the primary search provider fails.

<a id="blast-radius"></a>

## Regression Selection

For every change, run impacted scopes by tracing:

- `trigger -> config/compiler -> runtime -> persistence -> user-visible output`
- changed files to owning feature docs and QA folders
- affected surfaces: Web UI, Telegram, Voice, Scheduler, MCP, installer, CLI, and API
- affected delivery surfaces: source, nested component, compiled artifact, shipped bundle, live runtime

If uncertainty remains, run the broader feature suite and record the residual risk. Do not downgrade a
user-visible failure to "logs looked good."

Rerun cadence:

- rerun impacted feature cases on every change to that feature's owning code, config, prompts, runtime
  wiring, generated artifacts, or delivery surface
- rerun the full feature suite before any release-readiness or production-signoff claim
- refresh `Last Run` whenever a case is rerun; stale pass results are evidence history, not current
  acceptance

## Cleanup

Follow the owning [evidence-before-cleanup contract](../docs/requirements_and_learnings/55_Parallel_Work_Orchestration.md#evidence-before-cleanup-contract).
Keep required proof before removing exact synthetic fixtures; record incomplete cleanup as an open
result in the owning case report.

## Public-Safe Evidence

QA artifacts in this repo must be public-safe:

- no secrets, tokens, passwords, cookies, or credential-bearing command lines
- no private prompts, private chats, customer data, personal emails, attachments, screenshots with
  private content, or raw transcripts
- no account identifiers, conversation IDs, message IDs, session/call IDs, Telegram chat IDs, Mongo
  `_id` values, or raw provider request/response IDs
- no local absolute home paths, hostnames, machine names, stack traces with private paths, database
  exports, App Support state, live runtime dumps, or raw runtime dumps
- use synthetic non-personal prompts and placeholders such as `/path/to/viventium`,
  `~/Library/Application Support/...`, `<qa-user>`, and `example.com`
- keep private/raw evidence only in the approved private location and summarize it here with sanitized
  counts, hashes, timestamps, pass/fail results, and conclusions

## External Practices Folded In

This QA contract intentionally follows current public guidance:

- [Playwright](https://playwright.dev/docs/best-practices) recommends testing user-visible behavior,
  controlling data, and using web-first assertions.
- [OpenAI eval guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
  emphasizes continuous evaluation on every change and growing eval sets over time.
- [Anthropic eval guidance](https://platform.claude.com/docs/en/test-and-evaluate/eval-tool) emphasizes
  rerunning full eval suites after prompt changes, comparing versions, and grading quality.
- [Anthropic's agent-evals guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  emphasizes explicit success criteria, regression suites, production monitoring, and transcript review.
- [GitLab's quality model](https://handbook.gitlab.com/handbook/engineering/testing/) treats testing as
  everyone's responsibility, integrated throughout development, with risk-focused end-to-end coverage.
- [Regression-testing practice](https://istqb-glossary.page/regression-testing/) requires rerunning
  previously passing behavior after changes to detect defects introduced in unchanged areas.
