# Structured Telegram Delivery Disposition — 2026-08-13

## Summary

- Result: PASS for the installed structured-disposition acceptance scope
- Build/source under test: merged parent `7710356a6043893f91d9f4b301d3a9d99d8c9a8f`
- Runtime/artifact under test: installed local prod with merged LibreChat `24289a2834aad5e620b6a4878bd20404a26b5106`, GlassHive `c16230fed7351a6b08606b6f3d99ae57246c7aa6`, and the compiler-produced immutable Telegram component
- Environment: clean dedicated runtime checkout activated through the supported transactional local-prod path
- Related change: versioned, model-owned final delivery disposition for Telegram optional audio

The reviewed candidate replaces the optional text-sentinel-only boundary with a versioned final
delivery disposition. A capable provider returns `audio=skip` or `audio=eligible` as structured
metadata; LibreChat validates, persists, streams, and replays it; and the Telegram adapter applies
it before the existing voice-preference gate. Required missing or malformed metadata fails closed
to text-only. The legacy standalone `{SKIP_VOICE}` control remains the highest-precedence
rolling-upgrade compatibility path.

Automated, review, merge, exact-pin, installed-artifact, and real Telegram Desktop gates pass. With
Smart voice enabled, an explicit text-only turn produced text with no audio, an ordinary turn
produced text plus one audio attachment, and a second text-only turn still suppressed audio after a
supported full-stack restart. Each response finalized without error and carried a committed external
delivery acknowledgement.

## Scope Run

| Case | Result | Evidence | Notes |
| --- | --- | --- | --- |
| Provider emits a valid final disposition | PASS | GlassHive complete suite and LibreChat contract suites | Handles ordinary, fallback, and graph-handoff final speakers. |
| Required disposition is missing or malformed | PASS | Parent and Telegram contract tests | Delivery fails closed to text-only without changing visible answer text. |
| Metadata survives persistence, streaming, resume, and replay | PASS | LibreChat persistence and callback suites | Versioned metadata remains transport-only. |
| Actual request body carries Telegram audio eligibility | PASS | Builder-to-header integration test | The field reaches the same provider run that creates the final answer. |
| Exact nested merged commits are selected | PASS | Strict pinned-component validation | LibreChat and GlassHive resolve to their reviewed merge commits. |
| Installed Telegram Desktop explicit text-only flow | PASS | Synthetic post-activation turn, visible Telegram result, voice-gate telemetry, and persisted message metadata | Smart voice remained enabled; structured `audio=skip` suppressed TTS and audio. |
| Installed ordinary-audio preference flow | PASS | Synthetic control turn, visible text plus one audio attachment, TTS/audio telemetry, and persisted message metadata | Structured `audio=eligible` preserved the saved Smart voice preference. |
| Installed restart/persistence flow | PASS | Supported stop/launch, new process identities, repeated synthetic Telegram turn, and persisted acknowledgement | After restart, structured `audio=skip` again produced exact text and no audio. |

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
- Actual evidence: the escaped pre-fix Telegram Desktop run failed; the exact merged parent and
  components were then activated and the text-only, ordinary-audio, and post-restart journeys passed
  with visible, log, artifact, and database correlation.
- Remaining gap: none for the structured-disposition acceptance scope. The broader explicit-audio
  and injected stream-interruption variants in `TGVOICE-UC-010` remain separate regression coverage.

## Full-View Evidence Checklist

| Evidence surface | Result / sanitized pointer |
| --- | --- |
| Code owning path | GlassHive response envelope, LibreChat request/provider/persistence boundaries, parent compiler, and Telegram bridge/voice gate reviewed. |
| Docs and nested docs/repos | Telegram, prompt, installer, release-readiness, and component-inventory truth updated. |
| Tests and harnesses | Complete Telegram suite plus affected GlassHive, LibreChat, compiler, and cross-language contract suites passed. |
| Generated or shipped artifact | Compiler output and exact component locks validated; the active Telegram process ran from the compiler-produced immutable component, and API/UI/GlassHive processes ran from the clean merged checkout. |
| Logs, DB/state/persistence | All three post-fix turns had valid version-1 dispositions, `unfinished=false`, no message error, and committed delivery acknowledgements. |
| Real user path | Telegram Desktop visibly showed text-only without audio, ordinary text plus one audio attachment, and post-restart text-only without audio. The local browser login surface also rendered after restart with zero console errors. |
| Review and hosted checks | Independent Codex and bounded Claude reviews approved after fixes; all hosted LibreChat checks passed. |
| Remaining gap | None for this installed acceptance. Broader explicit-audio and forced stream-interruption variants remain tracked under `TGVOICE-UC-010`. |

Supporting evidence did not replace the user path: acceptance used Telegram Desktop itself, then
correlated the visible result with the installed artifact, runtime logs, and persisted message state.

## User-Grade Evidence

- Surface exercised: installed Telegram Desktop, local-prod API, compiler-produced Telegram artifact, Mongo persistence, runtime logs, and the local browser login surface.
- Real user path: with Smart voice enabled, a synthetic explicit text-only request, an ordinary short conversational request, and a second text-only request after restart were sent through Telegram Desktop.
- Visible outcome: text-only turns produced one clean text result and no audio; the ordinary control produced one concise text result and one three-second audio attachment.
- Expanded/detail state: the open Telegram chat showed the expected text/audio attachment counts and no visible transport markup.
- Persistence/reload result: all assistant rows finalized with `unfinished=false`, no error, a valid model-owned disposition, and a committed acknowledgement; the post-restart turn proved the behavior survives process replacement.
- Backend/log/DB confirmation: the two text-only turns logged `skipped_structured`; the ordinary turn logged `sent`, completed TTS, and completed audio delivery. Persisted dispositions were `skip`, `eligible`, then `skip`.
- Final model/runtime wording check: concise visible replies matched the request. Live prompt-frame telemetry stayed in the normal tens-of-thousands range rather than the earlier 200,000-plus-token failure class.
- Substitution check: the pass is based on the real post-activation Telegram Desktop path; automated tests and source review are supporting evidence only.

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

### Post-activation acceptance result

Using synthetic non-personal text, the running parent, LibreChat, GlassHive, compiled config, and
immutable Telegram artifact matched the reviewed merge commits. With Smart voice enabled:

1. Explicit text-only request: PASS; one complete text result, `audio=skip`, no TTS, no audio.
2. Ordinary conversation: PASS; `audio=eligible`, one concise text result, one audio attachment.
3. Supported restart and repeat: PASS; new API and Telegram processes loaded the same reviewed
   checkout/artifact, and text-only again suppressed audio.
4. Persistence correlation: PASS; every assistant row was complete, error-free, and acknowledged.
5. Forbidden outcomes: PASS; no required-metadata escape, visible control markup, duplicate
   assistant delivery, or source/runtime/pin drift was observed.

## Public-Safety Review

- [x] No secrets, tokens, passwords, cookies, or credential-bearing command lines.
- [x] No private chats, prompts, attachments, screenshots with private content, personal emails, account identifiers, or customer data.
- [x] No conversation IDs, message IDs, session or call IDs, Telegram chat IDs, Mongo `_id` values, or raw provider request/response IDs.
- [x] No local absolute paths, hostnames, machine names, stack traces with private paths, DB exports, App Support state, or raw runtime dumps.
- [x] Private evidence is summarized with sanitized counts, hashes, timestamps, and conclusions only.
