# Listen Only Mode QA Cases

## Case ID Convention

Use stable `LISTEN-NNN` IDs for listen only mode cases.

## Case Catalog

| Case ID | Requirement | User Outcome | Surfaces | Automation | Last Run |
| --- | --- | --- | --- | --- | --- |
| `LISTEN-001` | Listen-Only remains absolutely silent and executes no agent/work plane, including when speech addresses Viventium or requests urgent action. | The user gets passive transcription without surprise response or action | voice UI/audio, transcript, task/tool/controller/cortex/memory/recall state | voice route/gateway/playground focused suites plus user-grade QA | `PARTIAL` 2026-08-09; focused contract remediation exists, full post-change audible/persistence run pending |
| `LISTEN-002` | Public QA evidence is sanitized and reproducible | A PR reviewer can verify the behavior without private/local data | QA report, git diff, logs summary, generated artifacts | Public-safety scan plus relevant release tests | NOT YET RUN (cataloged 2026-05-17; next feature run required) |
| `LISTEN-003` | Automatic speaker separation never turns provider labels into identity or authority. | Same-mic voices are separated when supported and ambiguity is shown as `Unknown` | call captions, persisted segments/session state, post-call transcript | speaker-segment/multi-track suites plus aligned audio bank | `PARTIAL` 2026-08-09; focused automation exists, real audio bank pending |
| `LISTEN-004` | Listen-Only evidence remains soft and post-call only. | Ambient speech cannot immediately rewrite durable memory or count multiple speakers as corroboration | message metadata, hardener input/output, memory and recall state | voice persistence and memory-hardening regressions | `PARTIAL` 2026-08-09; focused policy checks exist, real post-call hardener path pending |

## `LISTEN-001` - Core User Flow

- Requirement: Listen-Only always stays silent and transcript-only. Direct address, tool requests,
  urgency, or safety language does not grant TTS, tools, Agents controller, cortex, live memory,
  Meilisearch injection, or ordinary recall authority.
- Risk covered: implementation, docs, and user-visible behavior drift apart.
- Preconditions: local Viventium runtime or the specific feature harness is available with synthetic, public-safe data.
- Steps:
  1. Switch an active Call to Listen-Only without reconnecting and speak ordinary ambient content.
  2. Directly address Viventium, request a tool/side effect, and use a synthetic urgent/safety-shaped
     request. Introduce a second speaker and overlap.
  3. Confirm zero audible assistant output and zero task/tool/controller/cortex/live-memory/recall
     execution while transcript segments persist with correct uncertainty.
  4. Switch back to Call, refresh linked chat, and run post-call hardening; verify ambient rows never
     enter live context and remain one soft evidence source.
- Expected result: Listen-Only remains transcript-only and silent in every branch. Switching mode
  preserves one RTC room; ambient evidence is visible later but has no live authority.
- Forbidden result: direct address, urgency, or a guessed speaker identity triggers speech, tools,
  memory, recall, or side effects; diarized speakers become multiple corroborating sources.
- Forbidden result: backend logs, mocks, source inspection, or model completions are treated as full acceptance when a user-visible surface exists.
- Evidence to capture: sanitized visible result, supporting command/test result, generated/runtime state summary, and docs/case links.
- Automation: `tests/release/test_prompt_architecture_eval_harness.py` plus any narrower feature tests discovered during implementation.
- Last run: `PARTIAL` — 2026-08-09 — focused source/automated remediation only; real audible,
  persistence, mode-switch, and post-call evidence remains pending.

## `LISTEN-003` - Automatic Speaker Separation And Abstention

- Exercise AssemblyAI same-mic single/two-speaker, overlap, short/unstable speech, and a configured
  local-only route without an approved shared-mic diarizer; also join a separate participant track.
- A second speaker on one track permanently revises every speaker on that track to unverified for
  the session. Provider labels stay call-scoped; uncertain cases are `Unknown`; separate tracks stay
  distinct. No label can authorize an action or infer a name/voiceprint.
- Evidence: visible captions, complete persisted `speakerSegments`, `SpeakerSessionStateV1`
  revision, refresh/export, route/egress audit, and aligned audio scoring.
- Last run: `PARTIAL` — 2026-08-09 — focused speaker tests only; real aligned audio/user path pending.

## `LISTEN-004` - Post-Call Soft Memory Evidence

- During Listen-Only, prove zero live memory writer and ordinary recall ingestion. After hangup,
  process multiple segments/speakers from one call through the hardener.
- Expected: one call counts as one soft source; no ambient row alone becomes owner-authored stable
  memory; late speaker revisions apply before hardening; unavailable terminal/suppression/speaker
  truth fails closed.
- Last run: `PARTIAL` — 2026-08-09 — focused policy automation only; real post-call hardener and DB
  evidence pending.

## `LISTEN-002` - Public-Safe Evidence Record

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
- Last run: NOT YET RUN (cataloged 2026-05-17; run on each new public report).

## Natural User Use Case Checklist

These rows are the minimum natural-user checklist gate for Listen Only Mode. Add narrower feature-specific
rows before claiming a pass when the feature behavior changes.

| Use Case ID | Natural user action | Requirement / case link | Real surface to use | Supporting evidence to compare | Expected visible result | Last run |
| --- | --- | --- | --- | --- | --- | --- |
| `LISTEN-UC-001` | Switch to Listen-Only and speak ambient, directly addressed, tool-requesting, and urgent synthetic turns. | `06_Voice_Calls.md` / `LISTEN-001` | real call audio/UI and linked chat | audible output, task/tool/controller/cortex/memory/recall counters, transcript, RTC identity | Every turn remains silent/transcript-only and the mode switch does not reconnect. | `PARTIAL` 2026-08-09; real user path pending |
| `LISTEN-UC-004` | Speak with another person on one microphone, then refresh and finish the call. | `LISTEN-003`, `LISTEN-004` | real call captions, linked chat, post-call hardener | segment/session revisions, Unknown state, DB/export, memory evidence count | Speakers are separated or safely Unknown; no identity/authority inference; one call remains one soft source. | `PARTIAL` 2026-08-09; real audio/post-call path pending |
| `LISTEN-UC-002` | On QA report, git diff, logs summary, generated artifacts, create or review the public QA evidence record with setup/auth/config, empty-state, degraded-dependency, and privacy checks. | owning requirement for `LISTEN-002` / `LISTEN-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to LISTEN-002. | The user sees an honest setup, retry, or degraded-state result for LISTEN-002; no fake success is accepted. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
| `LISTEN-UC-003` | After creating the public QA evidence record, rerun the scan after any retry, report update, or linked artifact change. | owning requirement for `LISTEN-002` / `LISTEN-002` | QA report, git diff, logs summary, generated artifacts | Source, owning requirement doc, case steps, logs, DB/state, generated config, and shipped artifact evidence that apply to LISTEN-002. | LISTEN-002 remains correct after the persistence or parity step and final wording matches evidence. | NOT YET RUN (cataloged 2026-05-18; next feature run required) |
