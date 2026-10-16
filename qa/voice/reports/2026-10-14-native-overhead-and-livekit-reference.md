# Native overhead and LiveKit reference evidence

<!-- qa-evidence-exempt: Historical engineering measurements and standalone reference experiments; it is not a current full acceptance report. Current Voice cases retain loaded user-path gates. -->

QA scope: blast-radius. Local development candidate; not a public release or full voice acceptance.

## Requirement and result

| Requirement | Candidate and evidence | Limit |
| --- | --- | --- |
| VOICE-PERF-002: separate work from transport | Passive host spans separate durable admission and HTTP response headers. A full High voice turn recorded 38.5 ms admission and 301.6 ms response headers. Warm unauthorized HTTP rejection p 50 was 0.373 ms. | Rejection is not an authorized turn. Header time includes server work. A broader 1.258 s host span includes context and graph preparation. |
| Remove output polling overhead | Native file notifications and run wake hints retain durable reads, output eligibility and bounded reconciliation. Ten fixed-phase paired checks: ready output to SSE chunk median 190.94 → 0.879 ms. Focused race and confirmed-consumer checks passed. | Fixed injection phase is not a random-phase average or whole-call saving. One real process CPU observation is not an old/new CPU comparison. |
| VOICE-WARM-001: genuine initialized processes | Saved Queen count 2 and ordinary mission-worker count 1 probes used native Grok, same model/High and existing session tools. Initialization 545 → 0.65–0.76 ms; exact listener identity proof still 54–55 ms. Runner to prompt 649 → 125–130 ms. | Other native providers remain explicitly unsupported for this option. This is not provider inference/KV warming. Whole response times differ. Loaded API save/reload/process proof is recorded below; browser settings proof is blocked. |
| Preserve Stop and continuity | Real native terminal-tool interruption returned confirmed Stop in 367.5 ms, proved the tool PID absent, and retained coherent same-session recall on the next turn. Orphan recovery and bounded cleanup checks passed. | A websocket close alone is not Stop. Unknown cleanup retains ownership and consumes capacity. |
| Stream text to actual speech | Full Core call delivered speech before native completion. Real standalone reference room emitted four public chunks, audio 186 ms before SDK completion, complete interruption, answer and follow-up recall. | Not every-word delivery, hardware echo or no-glitch acceptance. Actual native in-flight API cancellation and reconnect remain untested. |
| VOICE-AWARE-002: incremental preparation | Source-owned v 2 prompt starts from existing Life and prior report. Six exact-Main old/proposed fixture replays passed. A compiled-prompt execution found actual authorized context and an earlier report with real tools, labelled stale evidence and completed in 75.5 s. | The fixture replay alone proves no retrieval benefit. The real execution is not a controlled preparation speed comparison or actual Call-trigger acceptance. |
| VOICE-XP-LK-001: portable reference | Small official-SDK adapter preserves typed public/skip-voice metadata, stable conversation identity, exact request cancellation and owned-client cleanup. Actual room interruption and continuity passed. | Bare xPerfect does not automatically gain Core memory, Feelings or speaker trust. Full production module parity and callback-to-speech remain open. |

## Actual full-call time

A High native reply with 42,877 input tokens took 27.255 s from physical input speech end to received non-silent audio. Local end detection/transcription/commit consumed 1.075 s. Native prompt to first raw reply consumed 22.316 s. That provider window contains context processing, reasoning, execution, network and any provider queue; it is not isolated pure inference. The remaining host/native setup and output stages are reported separately in private joined clocks. No sub-two-second claim is supported.

A standalone three-turn reference used a different prompt and context. Its final targeted first reply took 7.656 s. It must not be compared as the same workload as the full Core call.

## Reusable lessons

- A timestamp named admission may precede the actual permission operation. Inspect the code that writes it.
- Measure a suspected wait before removing it. A zero background budget can disable intelligence rather than remove delay.
- Existing activation, memory search and background work already overlap Main. Do not build another background pipeline.
- Pinned LiveKit 1.5.10 discards early input during its default 3 s echo warmup. The reference exposes the native warmup setting for echo-free injection; the hardware default is preserved.
- A separate native endpoint minimum can add 500 ms after authoritative STT. Expose the existing SDK control with provider semantics; do not change every listening provider's default.
- Native server readiness, session loading, current tool grants and model inference are separate stages. Report all four.
- Validate every settings facade. A UI field and runtime schema alone do not prove the intervening strict API accepts a save.
- Direct SDK experiments are not installed endpoint support. The retained Direct prototype does not appear in the native worker registry.

## Acceptance still required

Browser warm-control acceptance; active integrated warm voice acceptance; actual in-flight native cancellation and reconnect; callback-to-speech; unheard native-history handling; hardware echo/audio quality; complete portable cognitive-module parity. These are not passed by source inspection or the isolated probes above.

Primary references: [LiveKit turn controls](https://docs.livekit.io/agents/logic/turns/tuning/), [AssemblyAI turn semantics](https://www.assemblyai.com/docs/universal-streaming/turn-detection), [Grok native source](https://github.com/xai-org/grok-build). Installed SDK and native binary signatures govern the implemented candidate.

## Review corrections before load

Independent review reproduced four additional native warm defects: orphan recovery depended on usable positive settings; warm-finalizer errors could skip shared cleanup; optional attachment failure could fail the turn before any prompt; full native Stop waited under the runtime-wide process lock. The corrected candidate performs startup recovery before settings gates, always runs shared finalization, uses the existing same-model cold path only before session/prompt acceptance, and separates exact signal from long cleanup proof. Unknown native cleanup retains authority and capacity. Focused causal checks cover these transitions; the repeated real tool Stop and same-session recall passed, with no native records left. The single Stop observation was 512 ms, not a claimed latency improvement.

The initial checks missed these transitions despite a successful normal warm turn. Do not treat a large test count or a clean reviewer verdict as coverage of shutdown interleaving, disabled-config startup, failed attachment or cross-worker blocking.

A separate authenticated observational lookup of an existing completed reply used twenty pooled local HTTP reads: median 17.19 ms, p 95 22.21 ms. This includes scoped database reads, retained-result validation and response handling. It is not pure transport, a fresh admitted turn or inference.

## Owning acceptance cases

| Delivered area | Requirement | Owning case | Result boundary |
| --- | --- | --- | --- |
| Output wake and speech projection | VOICE-PERF-002 | native-stream-no-polling-delay | Focused deterministic checks and actual received speech; universal audio quality remains open |
| Native idle processes | VOICE-WARM-001 | native-process-warm-count | Actual saved Queen/worker probes, Stop/recall and causal correction checks; loaded API proof passed; browser UI acceptance blocked |
| Portable audio reference | VOICE-XP-LK-001 | xperfect-livekit-reference | Actual SDK room streaming/interruption/recall; native in-flight cancellation and full cognitive parity remain open |
| Incremental preparation | VOICE-AWARE-002, VOICE-PREP-001 | optional-call-context-preparation | Source/compiled lineage, exact-model cases and real tools; unchanged Call-trigger evidence retained with its original limits |

## Loaded host and real-process acceptance

The normal same-checkout restart loaded the reviewed host, output and warm candidate without Git
promotion. A synthetic worker under the service's existing default owner saved count 2, reloaded it,
reached two actual idle process identities and owned listeners, then saved 0 and proved both exact
processes and records absent. Other settings were unchanged. This is API proof, not browser proof or
a warm Core Voice timing claim. Its idle Pause exposed an existing blanket host rejection; the
shared compute-cleanup repair retains the Pause effect and protects live/foreign/unknown sessions.

The loaded full Core call passed on configured Grok 4.7 Fast/High with Main unchanged: 22.676 s
physical speech-end to received speech,45,646 input tokens. Main's fresh capability work was 96.5 ms,
admission 86.5 ms, HTTP-header wait 189.2 ms. Native setup 3.110 s and native response window 16.911 s were
separate. First actual word to TTS acceptance was 77.9 ms; the first raw response was a header 123.5 ms
earlier. Speech started before native completion. No sub-two-second or no-glitch claim follows.

The API process used 3.61 CPU seconds over 22.51 wall seconds (16.0% of one core), including concurrent
work. It is not a stream-only or old/new CPU comparison. Passive output observations recorded 170
passes,108 delivered hints,one coalesced hint,106hint wake waits and 63 bounded timeouts in 21.3 seconds.

Native follow-up authority maps to background-agent case ACT-50;120focused consumer checks passed.
An actual Phase B follow-up grant is not established by the immediate spoken count reply alone.

## Final loaded-state boundary

The final idle-Pause repair is active. The same synthetic worker persisted an operator Pause and its callback after startup had already reclaimed idle compute. That already-reclaimed branch correctly avoids repeated cleanup. The mission work-log wording check applies when runtime cleanup actually runs; the focused check covers that branch. The extra live assertion expecting another cleanup log was invalid, and was retained as failed fixture evidence rather than reported as a product defect.

The configured High routes and alternatives were preserved. The production Voice worker remains at native warm count 0. This report does not establish its warm-call improvement. Direct SDK timings remain experiments rather than a delivered native Direct endpoint. Browser/native settings and artifact visual acceptance are blocked; hardware echo and glitch-free audio acceptance are NOT RUN. Full standalone cognitive parity remains open.

## Final report review corrections

Opus challenged the presentation as well as source changes. The revised chart separates the provider's 123.5 ms delivery-header-to-first-word interval from 77.9 ms first-word-to-TTS release. Neither the old 201.4 ms combined interval nor response headers can be labelled pure host overhead.

The same-audio AssemblyAI repeat returned two final segments; its first final arrived about 2.2 s into a 7.6 s request. The combined words were correct, but the boundaries differed from the local recognizer's single final. The final-segment result of 583–597 ms is therefore not proof of an equivalent whole-request turn-end improvement. A configuration that commits each final immediately risks starting an answer before the full request. Do not recommend a listening-provider switch or lower endpoint delay from latency alone; preserve complete requests and natural interruptions. The separate standalone echo/endpoint settings are labelled settings, not measured product speed gains.

## Native startup cause found after report review

The 3.110 s native setup sample contains a 2.209 s MCP connection interval. Its loopback Core tools/list request took 2.123 s. A retained credential-lookup flow had completed earlier, yet the shared FlowStateManager only observed it on a fixed two-second polling timer. The native registry checks themselves took about 1–2 ms. Native model initialization was 505 ms and session creation 143 ms; the tool handshake overlaps part of session creation, so these values must not be blindly summed.

The existing log phrase “already exists with valid token” does not prove a completed state: it can describe a pending flow or a completed null token result. The exact same-key history must support the attribution. The retained sample had already completed; no credential, permission or tool-readiness check needs deletion to remove its polling delay. New-conversation worker identity also differs from an older conversation, so per-worker warm settings cannot be claimed to warm another conversation's first turn.

The final structural correction reuses the flow monitor's existing checks immediately, with elapsed time zero, before its existing pending-state polling. A post-read cleanup guard protects cancellation and overlapping observations; invalid terminal states now reject rather than hang. Completed null token lookups remain valid results. The 61-case owning flow bank passed and the normal API package build succeeded. Independent source review accepted the delta. Pending cross-process observations still use the existing polling cadence, and the cold new-handler path retains its existing creation guard; this is not a claim that every authentication path has zero wait.

## Final loaded repeat

The final source and rebuilt package were loaded through the supported same-checkout restart. All 41 frozen source/build hashes match; Core and xPerfect health returned 200. The normal owner Call API and injected RTC audio path completed and ended normally, with no active owner call left.

| Boundary | Earlier call | Final loaded repeat | Interpretation |
| --- | ---: | ---: | --- |
| Speech end to received speech | 22.676 s | 14.357 s | Separate observations; not a controlled whole-call gain |
| Cold native setup | 3,110 ms | 1,521 ms | Both native warm count 0 |
| Native MCP connection | 2,209 ms | 538 ms | Partly overlaps session setup |
| Core tool catalog request | 2,123 ms | 437 ms | All 23 scoped tools remained ready |
| Native prompt to first raw reply | 16.911 s | 9.592 s | Provider context/reasoning/execution window, not pure inference |
| Provider header to first actual word | 123.5 ms | 61.0 ms | Provider output, not host release overhead |
| First actual word to TTS acceptance | 77.9 ms | 38.6 ms | Eligible streaming text released before full completion |

Both calls used configured Grok 4.7 Build Fast at High effort and returned the correct count with an unnecessary closing joke. The final repeat had 42,940 input and 1,178 completion tokens; the earlier call had 45,646 and 2,209. These differences prevent assigning the whole response-time change to the repair.

The final repeat used a newly created credential flow: its local handler completed in 42 ms. It therefore confirms the cold-handler path and readiness, not a live exercise of the repaired existing-COMPLETED branch. That branch is covered by the source and focused 61-case bank. An ended grant was not replayed to manufacture a cached-path test. Existing pending flow polling remains explicit. No under-two-second, pure zero-overhead, native warm Core Voice improvement, full portable cognitive parity or glitch-free hardware claim is made.

The final repeat did not improve every stage: Core conversation preparation increased from 642 to
1,108 ms. Exact request/participant timing records recovered after review show the invocation-fresh
grant increased from 96.5 to 286.6 ms, durable admission was 30.0 ms and HTTP headers 237.9 ms.
These spans overlap the stage table; do not add them again. About 190 ms of the 466 ms preparation
increase is within the grant span; the remaining increase is not isolated. This is an open
measurement/optimization gap, not a fixed stage or pure transport. Subtracting the observed provider
response and header-to-word windows leaves about 4.704 seconds in all other stages of the cold call.
That is arithmetic, not a new instant-model benchmark or proof of the requested two-second outcome.
