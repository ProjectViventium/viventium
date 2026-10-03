# Voice

## User promise

Voice Call is a real-time surface for the same authorized Main. Speech stays responsive, interruption
does not lose durable work, and an accepted effect happens at most once. Listen-Only records ambient
transcript evidence without acting as an assistant.

## Authority and interruption

### Interruption

- **CC-019:** Interruption stops or revises presentation only. It never cancels an accepted schedule,
  mission, or external effect.
- **PW-051:** Spoken interruption revises unfinished speech once. Hangup or network loss does not
  cancel accepted durable work.
- A state-changing voice command reserves its durable owner-and-turn identity before provider
  execution, persists the terminal outcome, and reconciles retries against that same record.

### Barge-in

- **CC-049:** Stable barge-in suppresses stale speech. A false interruption may resume; a stable one
  never does.

## Worker interaction

LiveKit sends speech through the existing voice gateway and LibreChat agent route to the selected
Voice Call LLM, or the Main LLM when no override is set. The Main source default uses
xPerfect → Grok 4.7 at high effort for Voice, with xPerfect → Opus 5.5/high as its configured fallback.
xPerfect serves as the text brain in this cascaded pipeline, with the same authorized harness
actions and model/effort selection as other
surfaces. Native realtime audio remains a separate capability; speech recognition and speech output
remain separate from the LLM. Provider defaults are GPT-6.1 Sol, Opus 5.5, and Grok 4.7 at high effort.
Other supported models and efforts remain selectable. Grok 4.7 Fast uses the Grok Build harness,
not the public xAI API. Owner-authorized call task controls use the same tool implementation through
the signed native capability broker. They recheck the accepted turn authority before each call and
are not inherited by delegated missions. Native Grok permission requests use the existing Call
activity input controls and the exact authenticated provider request mailbox. The Call UI shows
the complete bounded action description and the native offered choices. Submission rechecks the
call authority, owner, run, attempt, request fingerprint and expiry. Authenticated full-access Grok
conversation runs request native always-approve mode; other conversation access requests native ask mode.
Native deny rules, hooks and managed-policy restrictions remain enforced. Requests that still need
a native response use these same Call controls. Simultaneous native requests are shown one at a time. Denial, cancellation and expiry
keep their typed native outcome through chat and speech, and cannot start a provider fallback.
Call activity renders the authoritative task error message. Terminal tasks with an error remain
visible until the user dismisses them; terminal tasks without an error keep the brief existing
display. Dismissal changes only the displayed card, not the task outcome or action authority.
Recovered native error results settle the Call task as failed rather than completed.
Typed completion errors also settle non-native Call tasks as failed, including context failures.
An empty interactive assistant answer is a typed `provider_response_failed` outcome, so the existing
configured fallback can recover before speech starts. If recovery returns no answer, the task fails
and speech reports that result. Empty graph transfers, declared silence and background turns keep
their existing contracts; raw native output remains available for private audit.
An unanswered failed tool receipt remains in the audit history and raw ancestry; it is not carried
as an accepted Main answer. Visible answers and file-bearing rows retain their existing guards.
If Fast is absent from the native catalog and Grok 4.7 is present, the request uses and reports Grok 4.7.
Server-local MCP names do not contain the qualified-name separator. The same approved tools remain
callable in Grok, Codex and Claude. Prior broker names remain accepted lookup aliases with the same
grants and approval gates.
OpenCode integration is deferred in the backlog.

The [2026-10-03 local QA report](../../../qa/modern-playground-voice/reports/2026-10-03-voice-and-telegram-acceptance.md)
records current model defaults, Telegram photo/document delivery, voice selector save/reload,
spoken recall, early streamed speech and once-only worker completion through captured audio and
durable sent settlement. The linked prior report retains unchanged verified-owner tools,
approvals, recovery, Feelings, cortices, memory and interruption evidence. Full-flow latency joins
actual input PCM end to browser audio and distinguishes provider activity from model tokens.
Physical response under two seconds is not met. Default Unknown microphone action authority,
the rejected hosted Listening route, original linked-owner Web sign-in and genuinely off-network
public-file acceptance remain open. Short non-lexical sounds can produce false local-ASR text;
unqualified filenames retain the native bare-link behavior. These bounded results do not establish
universal recognition accuracy, glitch-free audio, full microphone parity or release readiness.

### Worker controls

- **PW-050:** In a normal Voice Call, Main remains available and may perform explicit authorized
  launch, list, queue, message, Steer, Pause, Resume, Stop, Retry, or Dismiss actions on exact work.

### Result presentation

- **PW-052:** Main speaks concise verified status or completion once. Files remain available in the
  linked chat or Active Work. Viventium never starts an unsolicited result call.

Canonical Call transcript and linked-chat text retain complete public links, including file and
workspace actions. An incomplete inline link stays as literal transcript text until it is complete;
its partial target is not clickable. Speech uses its existing artifact cleanup and selected renderer's streaming
policy. Main uses the SDK's separate text and audio paths; its speech buffer applies only to TTS.
Background completion display retains the full authored text while speech keeps the existing
follow-up cleanup and length cap. Voice controls stay hidden from display. Owner, mode, presentation,
speech-permit and playback checks remain in force, and link visibility does not change file access
or Call participant grants.

### Speaker authority

- **PW-053:** Only an explicitly engaged trusted Wing may use its authorized speaker role. Passive,
  unverified, and Listen-Only participants cannot launch or control work.

## Listen-Only

- **VOICE-001:** Listen-Only records visible ambient transcripts through the configured speech-to-
  text route, including a supported local zero-model-token path.
- It produces no assistant or TTS response, title, tool call, background mission, live memory write,
  or normal conversation-recall entry.
- Mode changes are atomic. Uncertain speaker identity stays `Unknown`. Later memory processing may
  use the transcript only as soft, corroborated evidence.

## Failure, recovery, and privacy

- Distinguish missing authorization, unavailable media service, provider rejection, timeout,
  interruption, and completed playback.
- Completed playback—not audio generation or track publication—is the user delivery boundary.
- Raw audio retention stays zero unless a separate explicit product policy says otherwise.
- Transcript and task data remain owner- and call-scoped and follow normal retention and deletion.

## Orchestration observability

Voice retains the Main prompt, connected capabilities, Feelings snapshot, activation decisions,
independent cortex execution and Phase B presentation. Traces join these stages to the trusted call
and logical turn with domain-separated hashes. Activation detection uses a fresh invocation identity
and records each cortex once within that invocation. Model receipts distinguish the requested model
from the actual native catalog selection, and retain the configured effort.

Native Grok receives the existing typed conversation output schema through ACP
`session/prompt._meta.outputSchema`, including resumed turns. The private schema file is checked
against the request contract before launch. The shared native schema makes `assistant_response`
the final result for the turn: complete authorized work now or report its actual blocker. A real
accepted asynchronous work receipt can still be acknowledged before that work completes. Graph
transfers continue through the existing typed `tool_call` result. This is transport truth, not an
extra Main instruction or a terminal retry loop. Conversation instructions do not acquire a worker's
`FINAL REPORT` completion contract. Provider authority receipts check the materialized instructions
and reject duplicate Feeling capsules. Grok conversation sessions use the exact pinned authority
in native `systemPromptOverride` on creation and resume; creation-only `rules` remain for mission
workers. A model change during native setup reapplies that authority before prompting, and effort
updates recheck the exact native model. A configured model change rebinds the conversation to a new
native session and seeds its visible history through the existing provider mechanism.
Native Grok observations include receive time in UTC, monotonic elapsed milliseconds and runner,
process, session-open and prompt-start markers. These distinguish observed setup and prompt time;
they do not infer hidden reasoning, provider queue time, cache behavior or unavailable token usage.
STT segment times retain their relative call-audio clock. The worker maps their end offset to UTC
through the call's paired monotonic/UTC origin before joining dispatch and provider stages. The
trace identifies this as the STT call-audio timeline; final-transcript observation remains a separate
timestamp. A missing origin remains unavailable. Neither timestamp substitutes for measured
physical microphone end in delivered-audio latency QA.
With latency logging enabled, the pinned provider wrappers separately record receipt of
AssemblyAI's end-of-turn event, observation of its final transcript, and SDK turn-commit entry
and exit. Word-end offsets remain provider-relative. The configured xAI instance records first
accepted text, websocket connect, first text write and first audio receipt. Socket reuse is
observed by object identity; it is not assumed for a later turn. Unsupported SDK versions keep
their original behavior and report that the measurement is unavailable. These records contain
hashes and typed timing fields, not transcripts, credentials, provider URLs or audio contents.
For an actual native streaming Speaking renderer, the gateway releases complete safe word
prefixes when the next lexical token begins. It retains the last word for delayed punctuation,
numbers and unfinished markup. The renderer keeps one continuous text segment until input ends;
the gateway does not flush once per word. Unknown and non-native renderers keep the existing
phrase policy. This boundary does not guarantee audio from a single unfinished word, eliminate
provider synthesis time, or establish glitch-free playback. Acceptance requires the loaded
first emitted chunk, provider input and delivered audio boundaries on the same actual turn.
Each new fallback stream resets this input policy to its actual primary renderer, and each
attempt updates it before input replay. Audible provider, controls and route metadata still
change only after that attempt produces audio.
Optional native observations distinguish catalog hits, joins, TTL refresh and scope-or-cold
misses through hashed scope components. They also report session binding decisions, executor
submit/entry and existing start-lock wait and hold boundaries. These observations do not change
catalog validation, native execution authority, scheduling, locks or socket lifetime. A scope
miss requires comparison with retained observations; a cache counter alone is not proof of its
cause. End-to-end latency still requires the actual loaded path and browser audio measurements.
Native Claude turns disable system-prompt snapshots when
that installed CLI supports the flag, so a resumed turn can receive its current pinned state.

Playback acknowledgement records the accepted delivery state, revision and hashed call/turn.
The generation store retains the server-bound Voice call, task and effect identity across Redis
serialization. Late TTS metrics join the same actual speech handle; completed playback may precede
the metric callback. Trace finalization waits while that handle is active. Native input lookup uses
the authenticated request family, including graph children, without relaxing owner or tenant checks.
Intentional silence or superseded speech is distinct from failed playback. Phase B keeps committed
native evidence strict, waits within the existing delivery grace period for an external adapter,
and reports unavailable parent evidence without blocking ordinary cortex insight presentation.

When a local source runtime lacks release-bound durable trace identity, a bounded redacted event is
written to the local log with that limitation stated. It must not manufacture release identity or
count these records as installed-release acceptance. Raw prompts, transcripts, model outputs,
credentials, owner IDs and call IDs are excluded from this trace transport.
Authenticated late audio events use the retained task binding after the generation job expires;
a conflicting live job is refused. A local diagnostic acknowledgement explicitly reports
`durable: false`. Completion failures log only their class, status, code and diagnostic hash.

## Owners and QA

- Real-time media: `viventium_v0_4/voice-gateway/`
- Durable call/task authority: `viventium_v0_4/LibreChat/api/server/services/viventium/`
- Browser surface: `viventium_v0_4/agent-starter-react/`
- QA: `qa/modern-playground-voice/`, `qa/voice-call-hardening/`,
  `qa/voice-streaming-first/`, `qa/voice-turn-taking/`, and `qa/listen-only-mode/`

Acceptance requires the installed call path, an audible result, interruption and recovery,
persistence, durable-effect exactly-once proof, and source/build/installed identity. Logs or a
published audio track alone do not pass.
For an explicitly authorized local engineering audio case, real browser microphone injection through
LiveKit and captured returned speech can supply delivered-audio evidence. Check waveform content,
interruption timing, accepted revisions and task state, rather than just media-element state or
nonzero energy. Keep aggregate failures visible. This does not claim human headset quality,
endurance or installed-release acceptance.

## Detailed contracts

- [Voice Calls](../06_Voice_Calls.md)
- [Voice Latency and Memory RCA](../14_Voice_Latency_and_Memory_RCA.md)
- [Voice Chat LLM Override](../34_Voice_Chat_LLM_Override.md)
- [Remote Access and Tunneling](../47_Remote_Access_and_Tunneling.md)
- [Voice Component Fork Modification Inventory](../52_Voice_Component_Fork_Modification_Inventory.md)

### Scheduler admission and audible proof

Managed LiveKit media preserves the configured public IPv4 route and retains native local and
loopback ICE candidates through the published media ports. Local callers do not require router
hairpin NAT. The pinned server uses native external-IP discovery at startup to keep both candidate
types; discovered public mappings must equal the configured node IP before startup is accepted.
Private or mesh node addresses, IPv6 and deliberately configured external LiveKit endpoints keep
their existing routing. Discovery is a startup operation and adds no per-turn delay. A managed
public-IP container with an older candidate configuration is not reused as a matching artifact.

When the configured voice-worker load threshold is unlimited, report zero scheduler load so the
LiveKit server does not reject the only available worker during model startup. Finite thresholds
retain SDK load calculation. This is worker admission behavior and does not enable the unsupported
native LiveKit deployment mode.

Real browser audio QA observes the rendered remote audio element: unmuted, positive volume,
active playback, decoded data and a live enabled media track. The playground's bounded
`data-viventium-audio-*` marker and `[ViventiumVoiceAudio]` event support correlation with that
call. Neither server TTS completion nor this browser state replaces human audible evidence.

### Live-call audio eligibility

Live-call responses remain audio eligible for ordinary answers, drafts, lists and code requests.
Only an explicit user request for text-only or silent delivery suppresses audio. The existing
no-response and listen-only contracts still apply. A long written artifact may have a short spoken
summary or pointer instead of being read in full. This policy belongs to the shared versioned
`surface.voice.call` prompt and is inherited by each selected voice provider. Native delivery
metadata remains model-owned and is validated before speech.
