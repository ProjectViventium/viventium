# Agent Streaming Usage QA Cases

## Case ID Convention

Use stable `STREAM-NNN` IDs for agent streaming usage cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `STREAM-001` | Streaming responses preserve usage metadata, final text, and persisted message state. | User-visible behavior matches source, docs, persisted state, and logs | web UI stream, API response, persisted message | `tests/release/test_background_agent_browser_qa_harness.py` plus user-grade QA when visible | NOT RUN (cataloged 2026-05-17; next feature run required) |
| `STREAM-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT RUN (cataloged 2026-05-17; next feature run required) |
| `STREAM-003` | Atomic conversation-scoped logical revisions supersede unfinished presentation across adapters. | A rapid second segment yields one current answer without stale errors or cross-chat interference. | web, Telegram, voice, GenerationJobManager, in-memory/Redis stores | claim/race/idempotency/stale-final tests plus real web/Telegram/voice runs | PASS 2026-08-11: real web, Telegram, and stable voice A/B/C paths plus Redis races passed ([report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `STREAM-004` | Presentation supersession never implicitly cancels or repeats durable work. | Interrupted speech/text disappears while committed effects and durable callbacks remain truthful. | tools/effects, GlassHive callbacks, background tasks, web/Telegram/voice | committed-effect, stale callback/TTS/follow-up, explicit-cancel contrast tests | PARTIAL 2026-08-11: presentation supersession passed live and durable-work/callback behavior passed automation; a real interrupted GlassHive/tool effect remains outstanding ([report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `STREAM-005` | Authenticated delivery acknowledgement validates owner, conversation, turn, revision, and adapter authority. | Only the real current adapter can commit/remove/fail a presentation. | shared adapter route and surface commits | forged-origin/revision/credential/ownership tests plus commit-point integration | PASS 2026-08-11: scoped-auth/forgery/Redis tests and real Telegram/voice commit paths passed ([report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `STREAM-006` | Superseded assistant content is absent after persistence/reload. | Refresh never resurrects unfinished B; user source segments remain intact. | web stream, Mongo conversation/messages, browser refresh | request persistence regressions and Playwright A/B/C refresh journey | PASS 2026-08-11: headed web refresh and Mongo revision/tombstone evidence passed ([report](../scheduling-cortex/reports/2026-08-11-consciousness-continuity-and-turn-coherence.md)). |
| `STREAM-007` | `CC-041`: adapter capabilities use the canonical stability and supersession enums through one interface. | New adapters compose without channel-name branches or invented states. | adapter interface, web, Telegram, voice, synthetic future adapter | schema/interface tests plus cross-adapter contract fixture | NOT RUN — cataloged 2026-08-30. |
| `STREAM-008` | `CC-046`: presentation commit is defined by durable completion on each adapter, never by preview. | A user sees committed state only after final Web persistence/stream completion, Telegram final send/edit, or Voice playback completion. | web, Telegram, voice, acknowledgement ledger | adapter commit-point tests plus real surface interruption controls | NOT RUN — cataloged 2026-08-30. |

## `STREAM-001` - Core User Flow

- Requirement: Streaming responses preserve usage metadata, final text, and persisted message state.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Exercise the feature through the real user surface, not only a unit test.
  2. Compare the visible result with source code, generated/runtime config, logs, persisted state, and the owning requirement doc.
  3. Capture a public-safe report with expected result, forbidden result, evidence, residual risk, and follow-up.
- Expected result: the feature behaves as documented and every supporting layer agrees.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_background_agent_browser_qa_harness.py` plus any narrower feature tests discovered during implementation.
- Last run: NOT RUN (cataloged 2026-05-17; not a substitute for the next real feature run).

## `STREAM-002` - Public-Safe Evidence Record

- Requirement: public QA artifacts must be reproducible and free of secrets, personal data, local paths, raw IDs, and private screenshots.
- Risk covered: a useful local QA run cannot be safely reviewed or published.
- Preconditions: a dated QA report is created for this feature.
- Steps:
  1. Review the report and related diffs for local absolute paths, account identifiers, tokens, raw logs, raw DB rows, private chats, and screenshots with private content.
  2. Keep raw/private evidence outside the public repo and summarize only public-safe counts, statuses, hashes, and conclusions.
  3. Link the report back to this case and the owning requirement doc.
- Expected result: the public report proves the behavior without leaking private/local data.
- Forbidden result: a report includes private transcripts, account identifiers, raw runtime dumps, local home paths, tokens, or secret-bearing command lines.
- Evidence to capture: public-safety scan result and link to the sanitized report.
- Automation: public-safety pattern scan plus relevant release tests.
- Last run: NOT RUN (cataloged 2026-05-17; run on each new public report).

## `STREAM-007` - Structural Adapter Capability Contract

- Requirement: `CC-041` and `docs/requirements_and_learnings/09_Agent_Streaming_Usage.md`.
- Risk covered: core branches on channel names or an adapter invents an incompatible stability or
  supersession value.
- Preconditions: the shared adapter interface and web, Telegram, voice, and synthetic future-adapter
  fixtures are available.
- Steps:
  1. Validate `segment_stability` accepts only `immediate` or `provisional`.
  2. Validate `supersede_scope` accepts only `response_and_authoring` or `response_only`.
  3. Register a synthetic adapter through the interface and scan core routing for name branches.
- Expected result: every adapter declares the canonical structural shape and core remains
  channel-agnostic.
- Forbidden result: free-form enum values, name-based core routing, or a future adapter requiring a
  complaint-specific core change.
- Evidence to capture: schema results, adapter declarations, branch scan, and synthetic adapter run.
- Automation: shared adapter schema/interface contract tests.
- Last run: NOT RUN — cataloged 2026-08-30.

## `STREAM-008` - Adapter-Specific Presentation Commit Points

- Requirement: `CC-046` and `docs/requirements_and_learnings/09_Agent_Streaming_Usage.md`.
- Risk covered: preview text or partial speech is treated as a durable presentation commit.
- Preconditions: Web, Telegram, and Voice adapters expose delivery acknowledgement and controlled
  pre-commit interruption.
- Steps:
  1. Interrupt Web before final persistence or successful stream completion.
  2. Interrupt Telegram before the successful final send/edit and Voice before playback completes.
  3. Complete each surface once and compare its acknowledgement with durable presentation state.
- Expected result: Web commits only after final persistence plus stream completion; Telegram after
  final send/edit; Voice after playback completion. Preview and partial speech remain uncommitted.
- Forbidden result: a preview, partial edit, queued audio, or partial playback records a commit.
- Evidence to capture: logical turn/revision, adapter events, persisted state, final send/edit
  receipt, playback completion, and visible/audible result.
- Automation: adapter commit-point and interruption contract tests plus real-surface QA.
- Last run: NOT RUN — cataloged 2026-08-30.

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Agent Streaming Usage. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `STREAM-UC-001` | On web UI stream, API response, persisted message, verify that streaming responses preserve usage metadata, final text, and persisted message state. | owning requirement for `STREAM-001` / `STREAM-001` | web UI stream, API response, persisted message | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to STREAM-001. | User-visible behavior matches source, docs, persisted state, and logs | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `STREAM-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `STREAM-002` / `STREAM-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to STREAM-002. | The user sees an honest setup, retry, or degraded-state result for STREAM-002; no fake success is accepted. | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `STREAM-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `STREAM-002` / `STREAM-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to STREAM-002. | STREAM-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT RUN (cataloged 2026-05-18; next feature run required) |
| `STREAM-UC-004` | Add a synthetic future delivery adapter and run one revision through it without editing core routing. | `CC-041` / `STREAM-007` | adapter interface and synthetic adapter harness | declared enum values, schema validation, core branch scan, and revision receipt | The adapter works through the shared structural interface with only canonical enum values and no channel-name branch. | NOT RUN — cataloged 2026-08-30. |
| `STREAM-UC-005` | Deliver one current revision, replay forged owner/adapter/turn/revision acknowledgements, and inspect the presentation state. | `CC-045` / `STREAM-005` | shared acknowledgement route and one real adapter | authenticated logical turn, revision, disposition, presentation reference, and rejected forgeries | Only the authenticated current adapter can record `committed`, `partial_removed`, or `failed`; every mismatched acknowledgement fails closed. | NOT RUN — cataloged 2026-08-30. |
| `STREAM-UC-006` | Interrupt Web, Telegram, and Voice once before their final commit point, then complete one delivery on each surface. | `CC-046` / `STREAM-008` | real Web, Telegram, and Voice delivery | persistence/stream completion, final send/edit receipt, playback completion, and interruption trace | Preview text and partial speech do not commit; each surface commits only at its documented durable completion point. | NOT RUN — cataloged 2026-08-30. |
