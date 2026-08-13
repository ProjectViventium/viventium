# Structured Telegram Delivery Disposition — 2026-08-13

## Summary

- Result: PARTIAL
- Build/source under test: isolated parent candidate pinned to the merged LibreChat and GlassHive changes
- Runtime/artifact under test: source-level candidates and isolated automated suites
- Environment: isolated clean component checkouts; installed local-prod activation deliberately deferred
- Related change: versioned, model-owned final delivery disposition for Telegram optional audio

The reviewed candidate replaces the optional text-sentinel-only boundary with a versioned final
delivery disposition. A capable provider returns `audio=skip` or `audio=eligible` as structured
metadata; LibreChat validates, persists, streams, and replays it; and the Telegram adapter applies
it before the existing voice-preference gate. Required missing or malformed metadata fails closed
to text-only. The legacy standalone `{SKIP_VOICE}` control remains the highest-precedence
rolling-upgrade compatibility path.

Automated, review, merge, and exact-pin gates pass. The post-merge installed Telegram Desktop path
has not yet run, so this report remains `PARTIAL` until activation and user-grade acceptance.

## Scope Run

| Case | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Provider emits a valid final disposition | PASS | GlassHive complete suite and LibreChat contract suites | Handles ordinary, fallback, and graph-handoff final speakers. |
| Required disposition is missing or malformed | PASS | Parent and Telegram contract tests | Delivery fails closed to text-only without changing visible answer text. |
| Metadata survives persistence, streaming, resume, and replay | PASS | LibreChat persistence and callback suites | Versioned metadata remains transport-only. |
| Actual request body carries Telegram audio eligibility | PASS | Builder-to-header integration test | The field reaches the same provider run that creates the final answer. |
| Exact nested merged commits are selected | PASS | Strict pinned-component validation | LibreChat and GlassHive resolve to their reviewed merge commits. |
| Installed Telegram Desktop explicit text-only flow | BLOCKED | Post-merge runtime not activated yet | Required before changing this report to a user-path pass. |
| Installed ordinary-audio and restart/replay flows | BLOCKED | Post-merge runtime not activated yet | Required to prove preference preservation and persistence. |

## Traceability

`feature -> requirement -> use case -> QA case -> expected result -> actual evidence -> remaining gap`

- Feature: model-owned optional Telegram audio delivery.
- Requirement: explicit text-only choices suppress optional audio without runtime prompt or keyword
  classification, while ordinary turns can still honor the saved Smart voice preference.
- Use case: send a text-only request with Smart voice enabled, then an ordinary conversational turn.
- QA cases: `TGVOICE-UC-007` and the structured-delivery cases in
  `qa/telegram-voice-replies/cases.md`.
- Expected result: text-only produces one clean text delivery and no audio; ordinary eligible output
  may produce one audio attachment; both remain correct after restart and replay.
- Actual evidence: the escaped pre-fix Telegram Desktop run failed; all source, contract, fallback,
  replay, validation, and pin tests for the structural fix pass.
- Remaining gap: activate the exact merged parent and components through the supported local-prod
  path, then run and correlate the two real Telegram Desktop journeys.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | GlassHive response envelope, LibreChat request/provider/persistence boundaries, parent compiler, and Telegram bridge/voice gate reviewed. |
| Docs and nested docs/repos | Telegram, prompt, installer, release-readiness, and component-inventory truth updated. |
| Tests and harnesses | Complete Telegram suite plus affected GlassHive, LibreChat, compiler, and cross-language contract suites passed. |
| Generated or shipped artifact | Compiler output and exact component locks validated; installed immutable artifact verification remains blocked on activation. |
| Logs, DB/state/persistence | Pre-fix failure was correlated end to end; post-fix live correlation remains blocked on activation. |
| Real user path | The escaped bug was reproduced in Telegram Desktop before the fix; the fixed candidate has not yet been installed or exercised there. |
| Review and hosted checks | Independent Codex and bounded Claude reviews approved after fixes; all hosted LibreChat checks passed. |
| Remaining gap | Installed text-only, ordinary-audio, warm-session, restart/replay, message-finalization, and delivery-ack evidence. |

Supporting evidence cannot replace required user-path evidence. Automated suites, logs, source
inspection, and merged commit identity therefore do not convert this report from `PARTIAL` to
`PASS`.

## User-Grade Evidence

- Surface exercised: Telegram Desktop was exercised for the aligned pre-fix reproduction; the fixed installed Telegram path is blocked until supported activation.
- Real user path: a synthetic explicit text-only request reproduced the escaped bug; the same request plus an ordinary conversational turn must be repeated after activation.
- Visible outcome: pre-fix text arrived with a forbidden audio attachment; no post-fix visible result is claimed yet.
- Expanded/detail state: the pre-fix open Telegram chat showed separate text and audio deliveries; post-fix message and audio detail inspection remains blocked.
- Persistence/reload result: pre-fix state finalized successfully; post-fix warm-session and restart/replay persistence remain blocked.
- Backend/log/DB confirmation: the pre-fix provider output omitted the optional sentinel and the voice gate sent audio; post-fix structured metadata and delivery acknowledgement remain to be correlated live.
- Final model/runtime wording check: the structural contract keeps semantic choice model-owned and adds no runtime prompt or keyword intent classifier; live fixed-runtime wording remains to be inspected.
- Substitution check: tests, reviews, logs, source inspection, and exact pin evidence support the candidate but cannot replace the required post-activation Telegram Desktop run.

## Automated Evidence

- GlassHive complete runtime suite: PASS after final header and tool-call compatibility fixes.
- Telegram complete suite: `425 passed`.
- LibreChat focused package contract and agent suites: `61 passed`.
- LibreChat API callback, persistence, and delivery suites: `51 passed`.
- LibreChat data-provider schema suite: `66 passed`.
- Real request-body builder to placeholder/header integration: PASS.
- Parent compiler plus cross-language delivery-control contract: PASS.
- Broad parent release suite: PARTIAL. The first isolated run passed `2589` and skipped `37` but
  reported `66` failures. A dependency-aware rerun cleared `40` of the `65` cached failures; the
  remaining `25` require prerequisites not assembled in this source-only parent candidate
  (Prompt Workbench FastAPI dependencies, a built LibreChat API `dist`, transitive native Node
  dependencies, or config-disabled voice component source). None exercises a changed
  delivery-disposition file. Hosted and installed-runtime gates remain authoritative for those
  assembled surfaces.
- Package build, formatting, diff checks, and secret scans: PASS.
- Independent Codex review: APPROVE after cross-provider edge cases were fixed.
- Independent bounded Claude review: APPROVE after the missing real-run audio-eligibility field was
  fixed and covered at the builder-to-header boundary.
- Hosted LibreChat checks: PASS, `13/13`; merged as
  `24289a2834aad5e620b6a4878bd20404a26b5106`.
- GlassHive merged as `c16230fed7351a6b08606b6f3d99ae57246c7aa6`.
- Parent lock and Native LibreChat manifest reference the exact merge commits; strict pinned-component
  validation passes in the isolated parent candidate.

## Findings

### Escaped bug and root cause

An aligned Telegram turn containing an explicit text-only constraint returned correct visible text
but also sent one audio attachment. Source, generated prompts, active processes, and the installed
Telegram artifact matched the reviewed runtime. The capable worker received the optional-audio
instruction but omitted the optional text sentinel, leaving the adapter to apply the standing Smart
voice preference. A hard delivery decision therefore could not safely depend on optional visible
text markup.

### Reviewed contract

1. The compiled LibreChat capability registry declares version 1 only for providers that guarantee
   final delivery metadata.
2. Telegram audio eligibility is carried as structured request metadata into the actual agent run
   and provider header; no prompt or user-text classifier is used.
3. Primary, fallback, and graph-handoff routes retain the declared capability owner even when the
   wire provider is normalized.
4. Each capable non-tool terminal model result replaces the earlier capture; tool-call hops retain
   it. A later non-capable terminal speaker invalidates an already-required capture so delivery
   fails closed.
5. Final metadata survives message persistence, streaming, resume, and replay.
6. Telegram precedence is: legacy explicit skip; valid structured skip or eligible; required invalid
   or missing metadata as text-only; optional absent metadata as rolling-upgrade legacy behavior.

### Post-activation acceptance

Using synthetic non-personal text, verify the running parent, LibreChat, GlassHive, compiled config,
and immutable Telegram artifact match the reviewed merge commits. With Smart voice enabled:

1. Send an explicit text-only request; expect one complete text result and no audio.
2. Send ordinary conversation; expect the saved preference to remain effective when the model
   returns `audio=eligible`.
3. Repeat after API and Telegram restart and once on a warm conversation.
4. Correlate each visible result with the final structured disposition, clean persisted assistant
   row, `unfinished=false`, no error, and committed delivery acknowledgement.
5. Fail acceptance for missing required metadata that permits audio, visible control markup,
   duplicate delivery, or source/runtime/pin drift.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session or call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
