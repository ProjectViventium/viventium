# Scheduled Main and simple schedule editor — 2026-10-23

## Summary

**Result: PARTIAL.** Bounded scheduled-Main and schedule-editor acceptance passed; hardware input, perceptual audio and endurance remain outside the evidence.

## Scope Run

Blast-radius local development checks dated 2026-10-23, with explicitly dated follow-ups below.
This publication retains their existing evidence; it performs no new live-account or provider QA.

## Traceability

The scheduled-Main requirements and cases linked below own timing, selected channels, cognitive context and recovery. Expected behavior, observed results and remaining gaps stay separate below.

## Full-View Evidence Checklist

- Requirements, owning code, nested component contracts and affected causal checks are linked or named below.
- Browser/channel observations, logs, DB/state/persistence and generated/loaded identity support only their recorded paths.
- Omitted required coverage keeps the overall result PARTIAL; hardware, endurance and universal readiness are not inferred.

## User-Grade Evidence

- Surface exercised: Chrome schedule forms, Web chat, Telegram and an existing LiveKit call.
- Real user path: Create a real clock through the configured worker, let it become due, then inspect the delivered reply or file.
- Visible outcome: A due reply appeared automatically; actual Telegram image/document outputs arrived; the editor remained usable on narrow screens.
- Expanded/detail state: Create/edit controls, history, delivery status and uncertain-receipt warning were inspected.
- Persistence/reload result: Editor reload retained saved changes; supported runtime reload retained canonical results and delivery identities without replay.
- Backend/log/DB confirmation: Saved clocks, due admissions, canonical Main proofs, channel receipts and loaded-source identity were checked as detailed below.
- Final model/runtime wording check: Save acceptance stayed distinct from completed work and delivered artifacts; omitted speech-content and hardware checks remain explicit.
- Substitution check: deterministic checks, logs, DB rows and model review support the recorded user path; they do not replace omitted visible, detail, persistence or wording evidence.

## Automated Evidence

Affected checks and their counts are retained below. Banks may overlap. Historical failures, simulated
effects and omitted live paths remain identified; publication review does not turn them into passes.

## Public-Safety Review

The public report contains sanitized behavior and bounded conclusions. Raw prompts, account/client
identities, credentials, private paths, screenshots, recordings and detailed receipts remain private.
The publication candidate passed the staged public-safety scan.

## Findings

QA mode: **blast-radius**. Local development candidate. This report does not authorize a public
release or claim whole-product acceptance.

The final candidate is built and loaded. A fresh natural web request saved a real native clock
and its due reply appeared automatically. The resulting full-native provenance defect was fixed
at the shared provider entry. The actual saved due record then passed that production projection
and compiled source resolver without new provider calls or clocks. Earlier unchanged-path evidence
below is retained.

Requirement owner: [Main scheduling and continuity](../../../docs/requirements_and_learnings/capabilities/main-scheduling-continuity.md).
Cases: [xPerfect scheduled Main, due recovery and task isolation](../cases.yaml).

| Contract | Actual check | Result |
| --- | --- | --- |
| Simple schedule setup | Real Chrome create, edit, reload, pause/resume, Run now, history and optional app connection dialog. Ordinary fields ask what, where and when; no JSON or credentials are required in that flow. | PASS |
| Responsive form | Actual desktop, 320px and 390px views; visible controls, keyboard focus, readable preview and no horizontal overflow. | PASS |
| Honest app delivery | Slow receiver settled automatically without another action or refresh. Two attempts produced one receiver effect. A first rejection and committed work with a lost reply stayed distinct. Unknown receipt warns that sending again may repeat the action. | PASS |
| Complete status-read path | Authenticated UI server → signed runtime definition read returns current receipt and expiry; missing definition remains missing. This replaces an earlier mocked-only check that missed the UI route. | PASS |
| Native scheduling | Natural Web, Telegram and open-call requests created actual saved clocks through configured native workers. Their tool metadata is discoverable through the normal inventory; no model coaching, intent routing or new Queen tool was added. | PASS |
| Ordinary Main and channels | Actual clocks invoked normal Main; Web updated visibly, Telegram delivered, and an eligible existing call received its reminder. A second fresh call request passed after the publication repair. | PASS |
| Full call speech path | RTC capture began before the second request and retained separate tracks. The agent track contains non-silent audio in both acknowledged delivery windows; the muted physical microphone track is silent. Speech content was not independently transcribed. Input used the call composer. | PASS for RTC output; STT input NOT RUN in this batch; no perceptual quality claim |
| Context and isolation | Separate due instructions retained their own task. A new destination retained its authorized source context. Owner, tenant, reference, tamper and signature failures were refused. | PASS |
| Recovery without repeated inference | Three earlier canonical results recovered with unchanged result and stream identities. Duplicate/lost replies reused the admission; changed bytes, expiry and premature wakes kept distinct outcomes. | PASS; 22 actual protocol checks |
| Current Main presentation authority | Real database enqueue, publication and permit checks accept the existing typed Main proof, reject revoked authority, and retain the worker path. No worker result is fabricated. | PASS; focused affected checks |
| Source retention and deletion | New target choices store ordered original-message references and digest, not request-body copies. Initial user preparation yields one set of six choices. The corrected full-native producer reuses those same original choices from the actual due record, with no new grant or text reconstruction. Real Mongo checks preserve future schedules and receipts, remove source/destination bindings with the conversation, and refuse changed, deleted or foreign originals. | PASS; actual persisted-data producer check |
| Permanent source failure | A missing or changed original stops with a recorded failure. It cannot loop indefinitely; a transient service failure remains recoverable. | PASS; focused affected checks |
| Cleanup | Synthetic future schedules are inactive. Existing history, uncertain effects, prior user schedules and unrelated work are preserved. | PASS |
| Final loaded candidate and restart persistence | Recorded process identity, source and built-package hashes identify the final Core reload, including the final JavaScript-only provider correction. All five affected service health checks passed. The final natural clock produced one new due reply, visible without refresh; the earlier seven canonical results and three sent delivery identities were retained without replay. | PASS |

## What the checks do not claim

- An app's HTTP acknowledgement means it accepted the request; it does not prove its task finished.
- The natural Telegram case selected the authorized chat-and-Telegram target. It proves Telegram
  delivery, not a Telegram-only model selection.
- No new sub-two-second, hardware-microphone, glitch-free, long-duration, provider-comparison or
  whole-product claim follows from these scheduling checks.
- Existing Cortex schedules retain their original clock. No bulk migration, replay or deletion ran.

Exact prompts, screenshots, recordings, account identifiers, raw receipts and source hashes stay
in private evidence. Public documentation records only sanitized product behavior and coverage.


## Real-use follow-up: provider failure and scheduled worker artifacts

The first real image request exposed gaps that the earlier text-reminder and editor checks did
not cover. A review score was not acceptance evidence. This follow-up keeps the existing Direct
Queen, native workers, cognition, scheduler and presenter; it adds no duplicate orchestration.

| Confirmed cause | Source correction | Evidence and limit |
| --- | --- | --- |
| Provider returned HTTP 200, then failed before an answer | Preserve declared safe error codes and bounded request IDs; distinguish content rejection, account access, rate limit and outage. | Official SDK HTTP/SSE transport checks exercise these classes without real credentials or provider prose. Historical vendor detail had been discarded and cannot be reconstructed. |
| A replacement turn's fallback renewed its dispatch lease while its own failed primary was still bound | Release only the exact current prior invocation before existing lease renewal. Keep first admission, stale-generation and foreign-producer fences. | Actual final-candidate browser replacement plus induced primary failure produced one configured fallback reply. Real in-memory and isolated Redis lease contracts pass. Earlier double failure and subsequent recovery proof is retained. |
| Native worker confused one broker catalog with its complete MCP inventory | Publish standard native MCP initialize instructions and versioned scheduling descriptions; state the broker's scope accurately. | Fresh uncoached Main worker called native schedule tools, saved a real clock and ended before due. No tool-name coaching in that case. |
| Scheduled image/file callbacks lost the selected channel | Preserve the canonical accepted channel field and existing topic through handoff, binding and adjudication. | New real clocks produced an actual generated Telegram photo and actual text document after the creating worker ended. Topic propagation has deterministic checks; a forum-topic delivery was not run. |
| Generic account access error suppressed configured fallback | Keep undeclared HTTP 402/403 as the existing access-denied class; explicit content-policy rejection remains terminal at any status. | Official SDK and host fallback-policy checks pass. No accepted action replay or additional native retry was added. |
| Stopped blank reply retained completed retrieval receipts but the formatter omitted them | Allow validated retrieval-only historical DATA on an unfinished assistant; preserve all source, conversation, tool, file and media checks. | Exact old/new causal reproduction and 481 affected checks pass. Twelve stale assertions now require retaining valid empty user-file sources, matching both old and new product behavior. Live continuation is recorded below. |
| Client body could project Telegram routing outside its actual adapter | Forward chat/user/message/topic only from the existing trusted interactive Telegram context; scheduled routing retains its admitted binding. | Trusted, absent, Web and system-origin producer checks pass. No extra mapping lookup or routing service. |

### Measured timing

These are individual observed runs, not averages. Three saved clocks fired within 0.922–2.665 ms
of their saved times. Signed HTTP acceptance took 12.156–13.595 ms. The requested text attachment
arrived about 47 seconds after its clock; the generated image arrived about 129 seconds after its
clock. The approved clock starts ordinary Main and any necessary native work at due time. Image
generation, worker completion and Main's authored return take additional time. This is not proof
of an exact artifact-delivery deadline or sub-two-second conversation latency.

### Candidate and remaining acceptance

- Core and xPerfect were loaded through their existing current-runtime watchdogs. Exact source,
  compiled package and process identities are retained privately. No other Codex or Claude chat
  was interrupted; no Git or direct database repair was used.
- Old callback bindings retain their historical selected destinations. The repair does not
  retroactively rewrite old receipts or replay uncertain effects.
- Final stopped-reply continuation: PASS. The existing native Run now tool created one new
  occurrence, normal scheduled Main completed, and the sourced live result appeared in the same
  browser conversation. The earlier failed admission remains preserved.
- Final interactive Telegram producer: PASS. After the final Core load, a native worker produced
  another real text document and the actual attachment appeared in Telegram.
- Natural repeating schedule controls: PASS in a disposable conversation. Create, pause and
  retire invoked native scheduling; persisted enabled/active flags are false and retirement is
  recorded. No future test sends remain.
- Independent Opus review: no material finding in the final dispatch fence, channel/topic,
  account-access classification, stopped-retrieval and trusted Telegram producer corrections.
  The earlier account-access finding was fixed before this final claim.
- Hardware/STT input, perceptual audio, endurance, provider comparison and new latency goals:
  NOT RUN in this blast-radius batch. Earlier unchanged-path RTC-output evidence is retained.
- Raw prompts, real account identities, screenshots, local paths and logs remain private.


## Focused completion: single execution, continuation and finalization

- Native Run now describes one asynchronous saved execution. Its caller receives admission facts,
  not an execution payload or the clock's internal dispatch hint. The saved executor still receives
  its complete instruction and authorized context. The general scheduling API is unchanged.
- A manual receipt now distinguishes fresh admission from replay. Same-key retry recovers the
  original occurrence; distinct requests require distinct keys. Concurrent admission remains
  atomic. A missing admission returns a typed error, and delegated uncertainty is preserved.
- A real next turn after a completed graph handoff exposed a second history mismatch. Persistence
  joins visible prose with two newlines, while the guard projected a literal tool label. The
  assistant-only supplemental text check now reuses the exact persistence projection; all ordered
  tool, source, owner and content-integrity checks remain. Three affected suites pass 487 tests.
- Shared native directories no longer undergo per-run file discovery and content validation.
  Existing selected native files/media and isolated-input integrity remain enforced. Seven
  affected suites pass 299 tests. This fixes both unowned-file attribution and local overhead.
- In the real user retry, the native worker used only schedule_list and schedule_run_now. It did
  not perform a second lookup or poll. Native completion to recorded run completion fell from
  14.806 seconds to 0.568 seconds in these two observed runs; these are not averages or complete
  conversation latency benchmarks. A real Telegram document also arrived after the scan repair.
- Exact configured Codex and Claude worker checks cover ordinary start, read without starting,
  separate work, a repeated new request, unknown submission followed by same-key recovery, and
  rejected admission. Fixture tool effects are simulated and remain separate from the actual
  user-path evidence. Earlier failed fixtures remain private; they are not counted as passing.
- Opus identified the replay-truth and native-receipt issues; the reviewed source contracts and
  their final corrections are recorded privately. A review score does not prove readiness.

This remains a local scheduling repair. It does not claim instant artifact generation, a
sub-two-second call, new hardware/audio/endurance coverage, or a whole-product acceptance result.
The saved personal persona, configured models, cognition and native capabilities were preserved.
