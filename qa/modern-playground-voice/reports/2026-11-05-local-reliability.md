# Local reliability repair — partial acceptance

## Summary

QA: blast-radius. Local development only; no release or component-pin claim.

Requirement links: `PW-014`, `PW-018`, `PW-023` and the approved Voice Should flow.
The ordinary replay below exercises the functional clauses of
[`PAR-QA-RESPONSIVE-001` and `PAR-QA-E2E-001`](../../parallel-work/cases.yaml).
The physical Mac check supplies evidence for the affected
[`MPV-014` / `MPV-015`](../cases.md) path. These are scoped results, not blanket passes for
every restart, cleanup, provider, phone, degraded-state or endurance clause in those journeys.

## Findings

The ordinary Telegram replay initially FAILED and superseded a general readiness claim from the
earlier explicit-worker checks. Main ran image generation directly; a follow-up correction and
quick question then waited about 884 seconds and received a context-preservation error. Neither
independent objective had a durable worker owner. The new candidate honors Main's saved
coordination capability policy and reads an owner-scoped native session budget instead of treating
the minimum discovery floor as its actual ceiling. No prompt, model or effort changed. The repair
has 609 passing focused checks and a clean package build. The same-chat post-change replay passed
durable handoff, exact steering, concurrent independent browser work, Main's answer before work
finished, once-only files and results, Web reload and an opened, visually checked downloaded PDF.
The first ordinary request grouped the postcard and checklist in one worker. A later separate-input
photo/guide/correction replay is recorded below; grouping must not be mistaken for two workers.

The final ordinary replay sent separate photo and eight-page guide requests, then changed only
the guide to four days and added a spare charger. Both durable workers overlapped for about
64 seconds. The correction continued the same guide worker; the photo retained its original
uninterrupted run. Main answered “3 nights” before either result finished. The three interactive
replies became visible in 16.1, 17.1 and 16.5 seconds. The photo and corrected PDF each had one
sent delivery record, one attachment and one Main-authored result. Web reload retained both
results and showed their delivered state. The downloaded PDF opened in Preview, contained eight
pages and four daily plans, and included the spare charger on its checklist. All eight rendered
pages were visually checked. This closes the ordinary A/B/C functional gate on the active local
candidate; it does not erase the earlier 60.8-second control reply or certify natural-fast speed.

Claude's implementation review approved the candidate after revalidating the existing restricted
native session contract. Restricted sessions intentionally bootstrap complete source; they still
retain per-conversation usage calibration. The existing stateless restriction remains unchanged.
The original schedule-access gating is unchanged. Native tool discovery required several model
round trips on the first correction: 60.8 seconds to Telegram visibility, with less than a second
in the tools themselves. A simple context follow-up took 8.5 seconds and made no tool calls or
new worker. Latency remains partial; no natural-fast acceptance is inferred.

Five ordinary worker callback rows initially hid the previous usable native admission behind a
three-row lookup cutoff. A regression failed before that cutoff was removed. One 500 ms deadline
still bounds the complete read-only scan; identity and authority checks remain intact. Another
test verifies that the deadline covers the entire scan, rather than restarting per row.

The budget observation traces to an earlier complete-source native request: 181,168 admitted
bytes and 88,202 prompt tokens produced the retained 2.054 calibration. The replay admitted every
protected visible source with zero omissions, but its separate native tool-evidence coverage field
remained unproven. These turns do not establish fresh calibration or close that broader gate.
The current configuration has not demonstrated calibration refresh. The receipt reports the same
current policy used by Native admission; the underlying sample has no new freshness bound.
Neither a new downstream capacity guarantee nor automatic self-healing from calibration drift
is claimed. Final Native/model capacity rejection remains a possible failed turn with retained
source, not a successful recovery.

The existing trusted LAN path and saved login work again. Optional legacy integrations remain
configured but disabled. The history sizing correction restores an affected long conversation,
and real Web and live-call chat tests demonstrate independent workers and exact steering. This is not full voice
acceptance: hands-free iPhone speaker quality, iPhone interruption and natural response latency
remain open. An old test consumer is the highly probable source of the idle stall: its import path,
reproduced state transition and execution timing match. The original process's database open was
not captured. The consuming project's replacement import and explicit startup passed isolated
tests, including an unchanged sentinel database. Off-network calling was not enabled for this QA.

## Scope Run

| Requirement / journey | Expected result | Actual evidence | Remaining gate |
| --- | --- | --- | --- |
| Remote access § LAN / modern voice | Current private address, trusted HTTPS and actual audio | User confirmed two-way same-Wi-Fi audio. Existing network worker reconciles address, DNS, proxy and native media before readiness. | Physical travel/handover and restricted-Wi-Fi isolation are not certified. |
| Stable local entry point | Restart preserves bookmarked address | Config/compiler/launcher now use two validated saved ports. Original trusted settings URL opened in Chrome after managed restart. Remote helper bank: 162 passed; selected compiler checks: 41 passed. | Two real restarts retained the same configured ports and trusted browser entry point. Physical address handover remains a separate gate. |
| Device sound controls | Small visual controls; retained selection; safe microphone cleanup | Speaker and Earpiece/headphones icon controls; provider detail hidden without a call. Chrome reload retained choice. Failed capture verification releases the microphone before ending. Type check passed. | Physical phone UI and published capture after latest restart remain open. |
| iPhone audio | Clear usable speech | Same-device diagnostic isolates crackle to echo cancellation enabled. User confirmed clear earpiece speech with it disabled. Explicit audio-session routing also produced clear, quiet earpiece sound. Test 5 stopped every microphone track, selected playback and waited before the tone; the user reported crackle at the start and finish, with medium volume. | Test 5 FAILED clean loudspeaker acceptance. No push-to-talk mode was added. Hands-free speaker and physical interruption remain unproved. |
| Main continuity / Telegram | Preserve required context and answer | Actual pinned Core/peer/legacy size replaces an insufficient fixed reserve. Two causal regression cases failed before the fix. 222 selected tests pass. Original Telegram conversation returned the correct answer after reviewed history repair. | Initial repair took about nine minutes. Exact-model compaction experiments did not prove a better producer; unproven prompt changes were reverted. |
| Main/worker Should flow | Main answers while independent work runs; exact steering | Real Web and live browser-call A/B/C: two workers overlapped; Main answered before completion; a correction continued the same A worker and did not modify B. Verified artifacts and one final message per result on both surfaces. Call inputs used the real typed-chat control with the microphone muted. | Web Main processing took 21.45 and 14.64 seconds. Call first text took 10.76–18.52 seconds across the sampled turns; speech synthesis added 0.28–0.73 seconds to its first audio. Hardware interruption and natural conversational speed remain open. |
| One presenter | Main authors useful replies; no duplicate speaker | The earlier failed call correlates with primary TTS timeout and configured backup TTS, followed by another primary-rendered failure notice. The user clarified that the later two-voice report occurred during diagnostic button 5. That served page contains only a tone and microphone handling; no speech synthesis or call connection. | Five subsequent live-call speech outputs used the primary renderer without fallback. After an idle pause, upstream admission stalled for six minutes; the primary renderer then spoke the failure notice with 208 ms first audio and no fallback. This does not prove the original TTS failure is fixed. No active room or new gateway speech was found for the later diagnostic report; its speech source remains unproved and must not inherit the earlier call's explanation. |
| Idle recovery | An existing conversation answers after a pause | An older copied runtime API constructed its service during test import and loaded the live environment before test isolation. An isolated synthetic replay reproduced the state transition. The current runtime uses an explicit app factory and environment paths. After supported recovery, Main and current workers remained ready through an idle pause; a real browser call returned the correct result with 11.45 seconds to first text and 0.62 seconds from synthesis request to first audio. | The consumer candidate passed 42 assembled checks and 44 checks after credential-fixture isolation. Synthetic sentinel state remained unchanged on import; no environment reads or added threads occurred, and explicit startup passed. Later inventory found additional eligible work, recovered through the supported owner without creating replacement runs. The initial recovery was incomplete. Historical waiting and explicitly paused work stayed unchanged; timed-out occurrences were not recovered. No Pause bypass or direct database rewrite was added. This typed-input call does not prove physical speech. |
| Main scheduling continuity | Durable outcome reconciliation before cancellation; exact delivery | Scheduler/API repair tests and real one-time reminders delivered through Web and Telegram. Retained Python bank: 278 passed, one skipped, 111 subtests; API bank: 99 passed. | Durable callbacks now resolve saved scheduler ownership; unavailable lookup retains intent and prevents dispatch. Eligibility ordering and bounded continuation prevent one bad row starving later work. Causal regressions cover ownership, queue progress, fast/slow lookup failure and claim replacement. Affected banks pass: 13 dispatch integrations, 44 terminal transactions, 99 scheduler gateway cases, and 86 callback/receiver/host unit cases. Normal startup superseded the misrouted callbacks and retained their completed results; no active callbacks remained. A fresh natural request delivered once in Web and Telegram after restart. The final lookup-error settlement and indexed identity refinement are active after an API watchdog reload. Existing admission identities are unchanged. |
| Account access | Existing saved password works and stays unchanged | Existing Chrome credential restored; real sign-out, autofill, sign-in and reload passed after earlier activation. All saved credential digests stayed unchanged across the latest restart. | Cause of the original password mismatch remains unknown. No new password was generated. |
| Optional legacy services | Retained but default off | Schema/config/generated runtime and running containers inspected; legacy search/productivity/crawl integrations disabled. An unused older voice-QA Redis container was stopped after checking that no client used it; its container and volume remain. | Re-enabling every optional integration is outside this repair. |
| Off-network calling | Optional free, open-source, self-hostable networking | Broad primary-source research plus GPT Pro and Claude review. Candidate assessment belongs in remote-access requirements. | Off-network setup and calling were NOT RUN in this batch. No enrollment or new network access was created. |

## Should / Fix comparison

The source of truth is [voice capability: Should / fixes](../../../docs/requirements_and_learnings/capabilities/voice.md#should--fixes--direct-queen).
The retained [October acceptance](../../parallel-orchestrator/reports/2026-10-23-should-flow-acceptance.md)
provides historical evidence, not proof of the current phone path.

| Should | Current observation |
| --- | --- |
| Preserve original ordered inputs and full relevant context | Retained conversation and current worker objectives preserved. Compaction review rejected a draft-input omission before accepting a revision. |
| One Main; durable A/B work; answer C without awaiting completion | Passed in the real Web journey and through the live call’s typed-chat control. Main route and effort were not changed. |
| Steer exact A; leave B intact | Same A worker identity continued after interruption; B ran unchanged, in both Web and call checks. |
| Parallel subconscious does not gate first answer | Existing native path runs background cortices beside Main. Mandatory context reconciliation can still block admission when history does not fit. |
| One presenter per useful result | One Main-authored result per worker appeared in each tested surface. All five sampled call speech outputs used the primary renderer; this does not establish physical speaker quality. |
| Fast natural voice and interruption | Not passed. No timing target or hardware result is inferred from Web tests. |

## Independent review

The current coordination/capacity repair also received a retained review-only Claude review. It
approved the source and the real replay, challenged the session restriction and catalog hypothesis,
then corrected those claims against the current owners. Codex already receives MCP access through
its native mechanism; the existing schema-bearing catalog and Grok-only access prompt are not a
proven correction for Codex's extra metadata lookups. No hidden prompt or session-resume exception
was added. Reviewer approval does not close latency or iPhone acceptance.

The post-change Mac check used actual speakers and the built-in microphone, not typed call input.
Whisper captured the story request and the spoken interruption. Viventium stopped playback about
200 ms after detected speech start and answered only “ready.” This is not an acoustic-onset figure.
First text took 12.653 and 8.179 seconds; primary TTS added about 239 and 182 ms from its first text
write to first audio receipt. Both outputs used the primary renderer without fallback. The UI and
database recorded the ended call; the microphone closed and the original audio settings were restored. This verifies Mac physical interruption after the capability repair,
without establishing iPhone loudspeaker quality.

Claude Desktop reviewed source, failure evidence and proposed changes in the retained project
conversation. It confirmed the history estimate and random-port defects, challenged foreground
compaction latency, and rejected unsupported completion claims. It also found queue starvation and the slow-lookup claim-expiry case; causal regressions and repairs cover both. Other reviewer claims were corrected against the source and live ownership evidence. Review is supporting evidence;
it does not replace the open phone and remote-network tests.

Claude reviewed the later idle-state evidence and broader audio research; GPT-6 Pro completed the audio research independently. Both reject full speaker acceptance. The final material-update review completed and checked the recovery receipts and native software echo-cancellation proposal. Its categorical claim that browser routing cannot improve loudness is not adopted: the cited native software-processing condition is not a physical result on this browser. Temporary
writer diagnostics were removed from source and unloaded from the running service. The physical
microphone-release diagnostic failed clean loudspeaker acceptance. It does not enable a production
speaker mode or imply that tap-to-talk preserves hands-free interruption.

The physical diagnostic confirmed microphone release after the failed speaker check. Exact device,
browser and audio settings remain private. This inspection does not reconstruct earlier browser
state or establish the source of spoken audio. A later silent capability check did not establish
output availability after capture permission. The fixture can now explicitly request capture only when
needed to enumerate outputs, then release every acquired track. Focused checks covered no-capture
listing, successful cleanup, enumeration rejection and a late permission grant after Stop. The
served file matches its source. Desktop browser listing passed. The physical Safari check after
capture permission is pending; iPhone Mirroring does not provide microphone access.

Current primary-source checks distinguish separate mechanisms:

- [WebKit 326286](https://bugs.webkit.org/show_bug.cgi?id=326286): open echo-processing crackle report;
  changing context rate or routing is not established as a fix.
- [Safari 26 speaker selection](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/):
  supported browser API, but [WebKit 320087](https://bugs.webkit.org/show_bug.cgi?id=320087) records
  silent failure on single-track remote streams. Its source fix landed; this alone does not prove
  the affected phone's shipping build or eliminate echo-processing crackle.
- [LiveKit speaker-selection PR 1635](https://github.com/livekit/client-sdk-js/pull/1635): still open.
  Installed 2.18.2 and current 2.23.0 both exclude Safari in `supportsSetSinkId`; a routine version
  bump does not enable this route. The default-system device follows the current route, not an
  unconditional built-in loudspeaker.
- [LiveKit 2003](https://github.com/livekit/client-sdk-js/issues/2003): double playback with
  `webAudioMix`. This client's effective value is false, so that report does not establish the
  diagnostic's two-voice cause. [PR 2029](https://github.com/livekit/client-sdk-js/pull/2029) separately
  fixes context and dummy-element cleanup; neither is evidence that a tone page generated speech.

- [WebKit 317968](https://github.com/WebKit/WebKit/commit/c315a716758008c2e11d996fe2e663db6097d114):
  fixes stale samples on a WebAudio output underrun. It is a possible lead for unwanted sound,
  not proof of the diagnostic's speech source or of the affected phone's shipping code.
- [LiveKit Swift 2.16.0](https://github.com/livekit/client-sdk-swift/releases/tag/2.16.0) includes
  [software-processing loudspeaker correction 1072](https://github.com/livekit/client-sdk-swift/pull/1072).
  This native path can retain software echo cancellation while disabling platform voice processing.
  It remains an alternative to validate, not a delivered browser fix. The SDK maintainer explicitly
  requires echo evaluation at the louder output. Full client authentication, reliable free
  installation, physical speech and interruption are still prerequisites.

The bounded browser route experiment needs an actually exposed output device, a user gesture on
its active audio element, one audible rendering path and continuous echo-controlled capture.
A successful API return is not acoustic proof. No guessed device identifier or unmerged SDK
patch was added. The next acceptance evidence must cover speech, echo rejection and interruption;
more quiet-tone variants cannot satisfy that contract.

The recovered call's latency partition is retained privately: about 1.57 seconds from provider
request persistence to native invocation; the native task reported 5.13 seconds and 154,260 input
tokens, with no cached input. First gateway text arrived 11.45 seconds after the client request.
These timestamps do not attribute all delay to model inference. No model, effort or context-quality
reduction was made to improve timing.

## Privacy and reproducibility

Original prompts, thread references, account identity, credential recovery evidence, exact run IDs,
raw logs and device addresses remain in the private companion workspace. Public tests use
synthetic identities and addresses. No credentials or private DNS records belong in this report.

Selected repeatable owners: `tests/release/test_remote_call_tunnel.py`, LAN compiler cases in
`tests/release/test_config_compiler.py`, native history sizing cases in the LibreChat agent
controller, the Main context service suite, device-sound/call-entry tests in the modern Playground,
and the scheduler delivery/lease integration banks. Run these against the active checkout and
generated runtime; mocks alone cannot close the phone acceptance gates.


## Follow-up: reply delay and interruption

The same signed-in local browser opened a new test call. Two typed requests produced correct
visible replies and triggered TTS. First text took 14.142 and 11.615 seconds. The first turn spent
5.166 seconds before its Main provider request was recorded; the repeat spent 0.725 seconds there.
An exact invocation join identified 2.248 seconds of request-side retention and 2.417 seconds of
session preparation on the first turn. A concurrent provider request also entered retention and
spent 4.510 seconds there. A coincident activation event is not proof of an activation barrier.

xPerfect now coalesces due retention and runs it outside request admission. Startup retention,
active work protection and normal native model selection stay in place. Focused retention,
admission, disconnect, startup and store shutdown checks: 27 passed. The old inline implementation failed the
blocking regression. Claude reviewed the final idle-close fence and shutdown ownership. This is a verified removal
of an inline wait, not a claim that inference or natural calls now meet the speech latency target.

An earlier synthetic speaker-injection attempt did not provide usable acoustic input to the
microphone, so it cannot validate or disprove physical interruption. The owned call ended normally.
No fresh physical-phone result after capture permission was available. The phone gate remains open.


The managed worker service reloaded the candidate after its existing work settled. A new real
Chrome call accepted the same arithmetic prompt, displayed the correct answer and ended normally.
Its first text arrived in **7.330 seconds**; first TTS audio took another **0.642 seconds**. This
is one typed sample with the same selected model and a different native execution duration, not
proof that the entire improvement came from retention or that a new retention interval was due.
The trusted LAN page still responded with HTTP 200. The two-second physical speech goal remains
open; the post-reload call did not exercise the physical speaker or microphone.


## Follow-up: Telegram retained-history stall

The next real voice note was transcribed and saved, but its reply failed after two twelve-minute
read-idle windows. Main was never admitted: required history compaction repeatedly regenerated a
large unchanged semantic state and exhausted its bounded repairs. Source reduction also increased
the intact tail and reduced the available summary budget. This is separate from transcription,
TTS and the previously repaired retention wait.

The registered compaction unit now supports digest-bound complete field replacements against an
approved previous state or a rejected draft. Omitted fields remain unchanged; server provenance
is excluded. The complete merged object still passes the original structural, carrier, source
identity and independent fidelity checks. All correction and checkpoint consumers receive that
complete draft. Empty replacements, unknown fields and stale digests are rejected. Models, routes,
source coverage, attempts, deadlines and promotion authority are unchanged.

Focused evidence: 194 service tests; 20 field-repair, producer-liveness and transport tests; eight
selected Telegram stream checks. Existing Main continuity checks: 266 passed. The broad prompt
registry bank has three failures in unrelated dirty prompt units; it is not reported as passed.
Exact configured-model paired initial-update cases include a dense prior state, a new count
correction, pending approval and quoted instructions. Dense output took 187.158 seconds before
and 18.124 seconds after; small cases remained approximately eight seconds. All six materialized
outputs passed independent full-source fidelity review. A candidate that ignored the new correction
was rejected. Earlier size and fidelity repair comparisons also passed their source-bound reviews.
These synthetic timings do not establish real conversational latency.

Telegram SSE now emits transport comments only while the same local generation producer is live.
It stops on completion, disconnect, producer loss or write failure. A real TCP counterfactual
passes across a quiet producer with comments and reaches the original read-idle timeout without
them or after producer loss. Comments never claim model progress or keep a stale job alive.

The managed Core restarted with registered compaction version 12. Only this prompt unit changed
in the generated bundle. The actual retained-history repair returned two changed fields and
passed independent review in approximately two minutes. The same saved conversation then reached
native Main admission. Its reply and selected outputs were delivered visibly in Telegram after 305.200 seconds,
including history repair and generation. A natural read-only continuation completed with correct
retained context in 17.714 seconds. Both replies are completed without errors
in the database and remain visible after reloading the signed-in Web conversation. The Workbench
shows version 12 and a live compiled bundle; the evaluated unit matches the generated runtime unit.
The old failed attempts remain historical errors and were not rewritten. This restores the real
conversation but does not establish fast hands-free voice or a two-second first reply. The older Core migration remains incomplete; this result
does not claim that all historical sources have been reconciled.

Claude reviewed the field protocol and transport lifecycle. Its proposed final full rewrite was
withdrawn after source inspection showed identical evidence in full and replacement modes. The
remaining feedback question is covered by materializing the full draft before any downstream
consumer and by the final checkpoint/carrier regression. Claude re-read the current transport
predicate and withdrew a stale missing-predicate finding; it found no remaining code blocker in
the Telegram repair. The real delivery and persistence checks above are now complete. Voice
acceptance remains partial.

The official open-source Swift example and Meet iOS TestFlight invitations are currently closed
to new testers. Neither is a delivered speaker workaround. Physical speaker and spoken-interruption QA remained blocked on device availability for this
follow-up. No additional sound-test guesses or native app installation were performed.


## Follow-up: physical Mac interruption check

A fresh browser call used the Mac's built-in speaker and microphone with audible test output.
The original audio settings were restored after the call. System speech
played a lighthouse-story request through the speaker. The real published microphone captured it,
and local speech recognition produced the correct visible transcript. Main returned the story and
the selected primary renderer produced speech. While that delivered story was still playing,
system speech played a correction through the same physical route. Recognition captured the
correction; the agent changed from speaking to listening 149 ms after the detected speech-start
state, then answered the requested replacement. This measures server interruption after detection,
not latency from acoustic onset or a human assessment of audio quality. The browser displayed both
spoken inputs and the replacement reply. The call ended normally and microphone capture closed.

First Main text took 18.035 seconds and the next turn 6.462 seconds. First TTS took approximately
0.273 and 0.550 seconds respectively. Both outputs used the primary renderer; no backup voice was
used. The first native Main execution ran for approximately 16.46 seconds with 65,584 input tokens
and no cached input; the following execution ran for approximately 5.03 seconds with cached input.
Output lengths and context also differ, so this does not attribute the improvement solely to cache.
Main's native request began before parallel cortex activation collection completed; that collection
was not a prerequisite for this reply. No model, effort or required context was reduced for timing.
This proves the shared spoken path on the Mac, not iPhone speaker quality or iPhone barge-in.

A final regression also covers typed field replacement followed by fidelity rejection and an
enclosing-deadline checkpoint. It verifies the persisted complete draft, its resumed digest and
exact rendered carrier headroom. It passed; the prior 194 service cases remain valid evidence.

## Traceability

The linked [parallel-work cases](../../parallel-work/cases.yaml), [modern voice cases](../cases.md) and [Voice Should flow](../../../docs/requirements_and_learnings/capabilities/voice.md#should--fixes--direct-queen) own the scoped functional and physical paths.

## Full-View Evidence Checklist

The retained evidence above identifies the selected source, tests, artifact and state checks, visible user path and remaining gaps. This format update does not renew that historical acceptance for the publication candidate.

## User-Grade Evidence

- Surface exercised: Real Telegram, Web, browser calls, Preview and physical Mac speaker/microphone checks.
- Real user path: Separate work overlapped, exact steering preserved the sibling, later files arrived once, and the recorded Mac spoken interruption passed.
- Visible outcome: Replies, downloaded PDF pages and the replacement spoken answer were observed; the phone speaker diagnostic failed clean-speaker acceptance.
- Expanded/detail state: All eight downloaded PDF pages were checked; callback, continuity, scheduler and microphone-release details retain their stated limits.
- Persistence/reload result: Web reload retained results; selected restarts preserved configured entry and credentials. Broader travel and phone persistence remain open.
- Backend/log/DB confirmation: Recorded source/build checks, isolated sentinel state, admission, receipts and call state support the dated results.
- Final model/runtime wording check: Mac interruption after detected speech, typed-call latency and iPhone acoustic acceptance are separate measurements.
- Substitution check: Automated checks, source review and model review support only their stated scopes; they do not replace the required visible, persistence or physical-audio evidence.

## Automated Evidence

The selected checks and their original limits are recorded above. This format update adds report validation, not a new runtime or full-bank result.

## Public-Safety Review

Raw prompts, personal media, accounts, credentials, operational identifiers, source hashes, screenshots and logs remain private. Only sanitized behavior, bounded evidence and remaining gaps are published.
