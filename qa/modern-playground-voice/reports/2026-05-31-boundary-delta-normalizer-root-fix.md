<!-- qa-evidence-exempt: Legacy or historical run note predates the V2 QA report template; retained as public-safe context, not a fresh completion claim. -->

# 2026-05-31 Boundary Delta Normalizer Root Fix

## Scope

This report covers the escaped Modern Playground / linked-chat corruption where streamed assistant
text could show internal no-response marker fragments or adjacent duplicate words.

The governing rule is `docs/requirements_and_learnings/01_Key_Principles.md`: deterministic
runtime output must be fixed at the runtime owner, not hidden with a later prompt or display patch.

## Root Cause

The broken path was:

`agent stream emits growing message snapshot -> LibreChat on_message_delta treats it as append-only
delta -> SSE/resumable job replay/content aggregation/TTS/display receive bad text -> final cleanup
is too late`.

The previous final-message cleanup shape was not sufficient because raw bad chunks could already
reach browser display, generation replay, TTS, persistence, or follow-up context before the final
message was sanitized.

## Fix

- `api/server/controllers/agents/callbacks.js` now creates a request-scoped text-delta normalizer
  and applies it at `GraphEvents.ON_MESSAGE_DELTA` before `emitEvent` and before `aggregateContent`.
- `api/server/services/viventium/voiceDeltaAggregation.js` owns the shared boundary normalizer.
  `auto` mode converts only safe cumulative snapshots to suffix deltas, including `{NTA}` marker
  progressions, normal whitespace/punctuation extensions, and mid-word snapshots such as
  `Hel` -> `Hello`, while preserving exact-doubling incremental repetition such as `ha` + `haha`.
- Non-voice chat remains `incremental` by default. Voice requests default to `auto`, and the voice
  gateway explicitly sends `viventiumTextDeltaMode: "auto"`.
- `api/server/services/Endpoints/agents/initialize.js` keeps only the missed-delta persistence
  repair as a safety net. It no longer owns duplicate/snapshot cleanup.
- The voice log/harness now distinguishes the SSE stream delta received by the gateway from the TTS
  delta and display delta. The gateway no longer runs a second cumulative-snapshot normalizer over
  the stream; LibreChat's message-delta boundary is the owner.
- The old duplicate-snapshot repair helper and its tests were removed so stale downstream cleanup
  cannot mask a boundary regression.
- The artifact inventory is now product-owned in
  `viventium_v0_4/LibreChat/api/server/services/viventium/voiceArtifactText.js`.
  `qa/modern-playground-voice/scripts/voice_artifact_contract.cjs` re-exports that module so the
  Chrome setup/inspect helper, automated browser harness, text regression, and runtime
  display/persistence cleanup share the same forbidden-condition list for punctuation-only chunks,
  raw links/emails, source labels, markdown/code scaffolding, inline markdown emphasis/decorative
  markers, unknown or voice-control tags, citation remnants, malformed no-response markers, known
  missing-space joins, and adjacent duplicate words.
- Post-fix live QA exposed one more owning-path gap: the first DB save for agent responses happens
  in `api/app/clients/BaseClient.js`, before the request-controller final normalization. Voice
  assistant messages are now sanitized before that first save, and the request-controller final
  path delegates to the same product-owned helper instead of carrying a separate cleanup copy.
- Shared no-response cleanup now strips known malformed internal marker artifacts at the speech
  sanitizer boundary while keeping whole-message no-response suppression strict. This is defensive
  last-mile cleanup; the stream boundary remains the root owner for snapshot corruption.
- ClaudeViv's final pass found that inline markdown emphasis and decorative markers were still
  outside both the voice TTS sanitizer and the artifact contract. The gateway now strips those
  speech-only markers while preserving math-like asterisks, and the shared contract now covers them
  as synthetic wildcard cases.
- The malformed no-response cleanup now avoids stripping template-variable shapes such as `${NTA}`,
  so the internal marker sanitizer is less likely to damage legitimate code-like text.
- A later ClaudeViv acceptance review found three more drift risks before final acceptance:
  non-voice `content -> text` persistence backfill had been accidentally gated behind voice mode,
  Python TTS sanitizers were not contract-checked against the JavaScript artifact inventory, and
  bare dot-heavy technical tokens could be over-sanitized. Non-voice backfill is restored, the
  LiveKit and Telegram Python TTS tests now load the same JavaScript artifact contract for
  sanitizer-owned classes, and `.NET`/`asp.net`/`node.js`/version-like tokens are preserved while
  full URLs and `www.` links are still converted.
- Post-restart browser QA exposed a separate cold-start dispatch race: the call was created before
  the voice worker registered, LiveKit logged that no worker was available, and the room never
  recovered. The modern playground now performs bounded dispatch reclaim when a call-session room is
  connected but no agent participant appears, and forced dispatch creation treats `ListDispatch`
  cleanup as best-effort so a transient local `503` cannot block the useful `CreateDispatch`.

This is a root-path fix because the stream contract is normalized before fan-out, not after visible
or persisted corruption has already escaped.

## Tests Run

| Check | Result | Evidence |
| --- | --- | --- |
| LibreChat focused boundary/callback/client Jest | PASS | 4 suites, 136 tests |
| LibreChat broader related Jest | PASS | 5 suites, 95 tests from the earlier same-turn run |
| Voice gateway sanitizer/buffer/fallback tests | PASS | 139 tests and 48 subtests, including shared-contract parity, malformed marker, inline markdown, dot-heavy token, and punctuation cases |
| Shared no-response tests | PASS | 8 tests via `uv run --with pytest ...` |
| Telegram TTS/preview parity tests | PASS | 60 tests via `uv run` from the Telegram project |
| Text artifact regression script | PASS | `contract=2026-05-31.3`, 27 synthetic wildcard cases |
| JS/Python syntax checks for touched runtime files | PASS | `node -c` and `py_compile` clean |
| Agent starter typecheck | PASS | `pnpm -C viventium_v0_4/agent-starter-react exec tsc --noEmit` |
| Voice playground dispatch + QA public-safety release contracts | PASS | 30 tests via `uv run --with pytest ...` |
| Active runtime checkout and health | PASS | Runtime owner is the checkout under test; API `3180`, web `3190`, and playground `3300` responded |
| Chrome Modern Playground user path | PASS | Started call, opened transcript, sent synthetic markdown-heavy prompt, visible assistant rendered `bold italic rule Done`, one assistant row persisted, zero persisted artifacts, TTS provider completed |
| Automated browser Modern Playground harness | PASS | `ok=true`, call created, Start clicked, transcript toggled, prompt sent, agent ready, input enabled, visible expected response, one assistant row persisted, zero page/persisted artifacts, provider metrics completed |
| Redis stream replay integration | BLOCKED | Redis on `127.0.0.1:6379` was unavailable, so replay acceptance is not proven |

## Real Browser Evidence

Latest post-cleanup Chrome and automated-browser runs used synthetic text only and sanitized hashes in
saved artifacts.

- Chrome route exercised: call creation, Chrome open, Start, transcript toggle, prompt send, visible
  assistant response, DB/log inspection, and cleanup.
- Automated route exercised: call creation, browser open, Start, transcript toggle, prompt send,
  agent ready, input enabled, visible assistant response, DB/log inspection, and cleanup.
- Latest post-restart automated route used a synthetic marker/dot-heavy prompt covering Markdown
  emphasis markers plus `.NET`, `asp.net`, `v1.2A`, `U.S.A.`, `node.js`, and missing sentence
  spacing (`Done.Next`).
- Persisted assistant rows: 1.
- Page artifact counts: all zero, including internal no-response marker and adjacent duplicate word.
- Persisted assistant artifact counts: all zero.
- TTS provider metrics were observed once with `cancelled=false` and the expected cleaned character
  count. The default local runtime has latency logging enabled but not TTS-input debug text logging,
  so the final passing harness reports `ttsTextArtifactEvidence=provider_metric_visible_persisted`
  rather than pretending optional debug chunk text was present.
- The latest dot-heavy run observed provider metrics with `cancelled=false`, zero page artifacts,
  zero persisted artifacts, and zero browser console errors.
- The run was a semantic PASS after provider repair: the visible assistant response matched the
  requested synthetic answer shape after voice-surface cleanup.
- A first post-restart harness attempt failed before prompt send because dispatch was created before
  the voice worker registered. After the dispatch reclaim/fallback fix, the follow-up harness and
  Chrome runs reached agent-ready input and clean visible/persisted/TTS artifact scans.

This proves the patched runtime path did not leak the reported corruption in the exercised browser
run. It does not prove Redis-backed replay behavior until Redis is available for that integration
case.

## Primary Research Cross-Check

This fix was cross-checked against primary docs rather than only local test behavior:

- MDN's Server-Sent Events guide defines the transport as `text/event-stream` messages separated by
  blank lines, with `data:` fields delivered as event payloads. That supports treating the
  LibreChat SSE boundary as the first fan-out point that must normalize malformed cumulative
  snapshots before replay, display, TTS, persistence, or downstream context see them.
  Source: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- OpenAI's streaming guide describes processing the beginning of model output while the rest is
  still generating over SSE. That matches the intended append-only delta contract and argues
  against a final-message-only sanitizer as the root fix.
  Source: https://developers.openai.com/api/docs/guides/streaming-responses
- LiveKit's text/transcription docs distinguish synchronized transcription behavior from sending
  text as soon as it is available. That supports keeping browser display/transcription behavior
  honest and testing the actual visible LiveKit path, not only persisted final messages.
  Source: https://docs.livekit.io/agents/multimodality/text/
- Cartesia's Sonic docs warn that streamed text and SSML-like tags require buffering complete tag
  values, and that punctuation/terminal text shape affects TTS quality. That supports centralizing
  forbidden marker/tag/symbol conditions in one contract and keeping provider-specific voice-control
  tags out of generic speech text unless explicitly owned by that TTS path.
  Sources:
  https://docs.cartesia.ai/build-with-cartesia/sonic-3/ssml-tags and
  https://docs.cartesia.ai/build-with-cartesia/capability-guides/stream-inputs-using-continuations

## Remaining Gaps

- Redis-backed generation replay remains BLOCKED until Redis is available for the integration test.
- Optional TTS debug text evidence still requires `VIVENTIUM_VOICE_LOG_TTS_INPUTS=1`. The default
  acceptance harness now labels that evidence level explicitly instead of hiding the distinction,
  and Python sanitizer parity is covered by contract-loaded unit tests.

## Second Opinion

Claude Opus review was run review-only. The first final-state review confirmed the old downstream
shape had been collapsed into a single LibreChat message-delta boundary owner and found no remaining
duplicate-repair references or gateway-side snapshot normalizer. It did flag a real `auto`-mode edge:
mid-word cumulative snapshots such as `Hel` -> `Hello`. That edge was fixed afterward and covered by
the focused boundary regression.

ClaudeViv then ran a max-effort review-only pass after the Chrome/research/contract work. It agreed
that the message-delta boundary fix is a real root-owner improvement and not the old
patch-over-patch shape, but said it is still compensating for a snapshot-emitting stream rather than
fixing that emitter. It also found actionable gaps: inline markdown emphasis/decorative markers were
absent from both the contract and the voice TTS sanitizer, `${NTA}`-style template variables could
be damaged by the malformed-marker cleanup, non-voice content-only responses could lose their text
backfill, Python TTS sanitizers were separate implementations without contract-loaded parity tests,
and dot-heavy technical tokens risked over-sanitization. Those gaps were fixed or bounded with
focused tests; the remaining explicit non-PASS item is Redis replay infrastructure availability.

## Public Safety

This report intentionally uses synthetic prompts, sanitized hashes, relative repo paths, and no call
IDs, private transcripts, local user paths, credentials, or secret-bearing log excerpts.
