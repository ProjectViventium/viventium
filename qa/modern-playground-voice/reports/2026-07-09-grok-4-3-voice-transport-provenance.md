# Grok 4.3 Voice Transport Provenance QA
<!-- qa-evidence-exempt: Historical local QA format retained without retroactively inventing evidence; current release acceptance is recorded separately. -->

Date: 2026-07-09
Result: PASS

## User-visible failure

An authenticated Modern Playground call transcribed the user's short greeting, then waited about
101 seconds and displayed/spoke the generic provider-failure fallback. The LLM stream completed with
zero token events. LiveKit, AssemblyAI STT, and xAI Eve TTS were healthy, so the failure was isolated
to the LibreChat model request.

## Root cause and fix

The main agent had correctly moved to `openAI/gpt-5.6-sol` with `useResponsesApi=true`. The dedicated
voice profile remained `xai/grok-4.3` with `reasoning_effort=none`, but the voice override retained
the OpenAI transport flag in the xAI parameter bag even though the voice profile had not selected it.
The same merge boundary could also retain a primary Responses-style reasoning object, so that
provider-specific edge is sanitized and covered independently.

The override now treats API transport as provider-owned state:

- inherited OpenAI Responses and reasoning fields are removed from the xAI voice request;
- the configured Grok 4.3 model and `reasoning_effort=none` remain unchanged;
- an explicit voice-level xAI Responses selection remains supported;
- Anthropic voice overrides also discard the OpenAI-only transport flag.

No xAI console change was made. Two minimal provider-health probes returned HTTP 200 for Grok 4.3
through both xAI Chat Completions and xAI Responses, showing that the installed key, account, model
access, and xAI service were healthy.

## Evidence run

Automated regression:

- The new live-shape GPT-5.6-primary-to-Grok-voice case failed before the fix because the resolved
  bag still contained inherited `useResponsesApi=true`.
- The explicit xAI Responses provenance case separately proves that a primary reasoning object does
  not override the voice profile's owned reasoning effort.
- After the fix, the focused suite passed 13/13, including preservation of an explicit xAI voice
  Responses selection.
- Adjacent provider-boundary suites passed 30/30 total, related `packages/api` tests passed 83/83,
  and the full voice-gateway suite passed 341 tests plus 48 subtests.

Real user path in Chrome:

1. Reloaded LibreChat from the patched checkout through its active development watcher.
2. Used the authenticated QA account to start a new Modern Playground call.
3. Confirmed the selected routes remained AssemblyAI listening, xAI Eve speaking, and the agent's
   dedicated Grok 4.3 voice model.
4. Opened the live transcript and sent a synthetic one-sentence prompt.
5. Observed the requested one-sentence Grok answer in the visible transcript.
6. Confirmed the browser's audio element was visible, unmuted, playing, and ready; gateway metrics
   recorded 1.61 seconds of xAI audio.

Sanitized runtime correlation:

- escaped stream: 101.040 seconds, final event, zero token events, provider-failure fallback;
- fixed stream: first token at 7.335 seconds, complete at 7.735 seconds, token events present;
- speaking route: xAI standalone TTS, 0.373-second provider TTFB, 1.61 seconds delivered audio;
- browser-visible answer matched the synthetic requested sentence;
- no configured model, STT provider, TTS provider, credential, or account setting was changed.

## Independent review

A review-only Claude Opus 4.8 second opinion found no must-fix correctness issue and agreed that a
provider-specific API mode should remain unset after a provider switch unless the target voice
profile explicitly owns it. It identified two residual risks rather than blockers: a future custom
provider needs the same explicit parameter-ownership audit, and an explicitly configured but invalid
target-provider value remains the user's responsibility. Neither applies to the proven Grok 4.3
profile, whose supported explicit/default paths have regression coverage.

## Safety

This report contains no API key, user/account identifier, call/session identifier, private transcript,
or machine-local path. The synthetic sentence is intentionally public-safe.
