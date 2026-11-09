# Phone call access and audio — scoped result

## Summary

QA mode: blast-radius. This report covers trusted LAN entry, microphone startup, the explicit
native LiveKit option and the newly reported phone-speaker defect. It does not replace earlier
Queen/worker or voice endurance acceptance.

## Findings

- Local call names resolve to the serving computer's private address. Public-trust HTTPS needs no
  client certificate/profile; the call page and media connect directly over the LAN.
- The native SDK completes microphone permission before dispatch/ICE, then stops temporary capture
  before the SDK owns the sole published microphone. Concurrent recovery shares startup; End,
  denial, timeout and late grants release capture. Saved mute is respected.
- `runtime.network.livekit_runtime: native` selects the verified, pinned self-hosted LiveKit server.
  Docker remains the default and supported alternative. Signaling is loopback-only; native media
  advertises the assigned LAN address plus its public mapping. Existing TURN private-peer denials
  remain in force. No model, prompt, worker or public-port changes.

## Scope Run

| Required outcome | Evidence | Result |
| --- | --- | --- |
| Config, TLS and startup correctness |151 focused remote-call/Caddy checks | PASS for tested contracts |
| One microphone/startup owner |66 client tests,27 confirmed-consumer tests and TypeScript check | PASS |
| Native artifact/config/lifecycle |48 initial and33 follow-up hardening/provenance checks; overlapping coverage | PASS for tested contracts |
| Source review | Independent Opus5.5 review of changed microphone and native security code | No remaining material finding in those seams |
| Real LAN phone connection | Actual private-to-private nominated media pair and user-reported working call | PASS for that connection; not all phone journeys |
| Synthetic speech round trip | Real RTC injected speech, expected reply, received PCM and accepted End | PASS; does not prove physical speaker quality |
| Phone-speaker audio | Audible crackling reported | OPEN |
| Server audio continuity |12-second non-silent streaming, irregular byte boundaries, socket reuse, resampler and received-waveform checks;73 tests plus3 subtests | No reproduced PCM corruption; phone rendering and receive jitter remain separate |
| Cellular/public audio, muted phone reload and physical barge-in | Current-candidate complete acceptance not retained | NOT RUN / not accepted by this report |

## Crackle investigation

The call used echo cancellation. Its Safari version matches an
[open WebKit issue](https://bugs.webkit.org/show_bug.cgi?id=326286) about speaker crackling during
microphone processing. This is a leading hypothesis, not an established root cause. Native INFO
logs do not contain phone-side loss/jitter/concealment counters. Do not clear that boundary from
clean server PCM or the browser's playing state.

Use [the local audio fixture](../fixtures/browser-audio-processing.html) with the same microphone
constraints as the installed call client. Run no-mic, echo-off, echo-on, then no-mic from a fresh
browser session. Keep volume and grip constant; record speaker/earpiece and loudness. A reload may
not clear a browser's audio-processing state. The quiet tone does not rule out speech-level
distortion. Effective settings matter more than requested settings.

The fixture records or uploads no microphone audio. Its temporary copy on the running playground
is a diagnostic only and must be removed after the experiment; never include it in a release.
Independent review found no capture leak, and required matching the call constraints, correcting
test order, and retaining output-level/route limits. These corrections are in the canonical fixture.

Do not disable echo control, auto-mute during replies, change provider/codec/rate, or claim clean
phone audio to close this issue without causal evidence and the affected real-path check.
Raw device data, signed links, screenshots, logs and review transcripts remain private.

## Traceability

The [Voice capability](../../../docs/requirements_and_learnings/capabilities/voice.md) and [modern voice cases](../cases.md) own trusted LAN entry, microphone ownership and physical audio acceptance.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: A real LAN phone call, RTC speech injection and the browser audio-processing diagnostic.
- Real user path: A private-to-private media pair and user-reported working call established the selected connection; the phone speaker still crackled.
- Visible outcome: Call entry and RTC output worked in the recorded checks; clean phone-speaker output was not established.
- Expanded/detail state: Microphone startup, release, mute and failure cases passed; phone-side loss and jitter counters were unavailable.
- Persistence/reload result: Complete muted-phone reload and cellular/public audio acceptance were not run.
- Backend/log/DB confirmation: Connection, received PCM and server-stream continuity support the media path without proving phone rendering quality.
- Final model/runtime wording check: The cited WebKit issue is a hypothesis; clean server PCM is not clean physical speaker acceptance.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Automated Evidence

The selected checks and their original limits are recorded above. This format update adds report validation, not a new runtime or full-bank result.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.
