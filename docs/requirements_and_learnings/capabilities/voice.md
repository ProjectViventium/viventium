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

### Worker controls

- **PW-050:** In a normal Voice Call, Main remains available and may perform explicit authorized
  launch, list, queue, message, Steer, Pause, Resume, Stop, Retry, or Dismiss actions on exact work.

### Result presentation

- **PW-052:** Main speaks concise verified status or completion once. Files remain available in the
  linked chat or Active Work. Viventium never starts an unsolicited result call.

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

## Owners and QA

- Real-time media: `viventium_v0_4/voice-gateway/`
- Durable call/task authority: `viventium_v0_4/LibreChat/api/server/services/viventium/`
- Browser surface: `viventium_v0_4/agent-starter-react/`
- QA: `qa/modern-playground-voice/`, `qa/voice-call-hardening/`,
  `qa/voice-streaming-first/`, `qa/voice-turn-taking/`, and `qa/listen-only-mode/`

Acceptance requires the installed call path, an audible result, interruption and recovery,
persistence, durable-effect exactly-once proof, and source/build/installed identity. Logs or a
published audio track alone do not pass.

## Detailed contracts

- [Voice Calls](../06_Voice_Calls.md)
- [Voice Latency and Memory RCA](../14_Voice_Latency_and_Memory_RCA.md)
- [Voice Chat LLM Override](../34_Voice_Chat_LLM_Override.md)
- [Remote Access and Tunneling](../47_Remote_Access_and_Tunneling.md)
- [Voice Component Fork Modification Inventory](../52_Voice_Component_Fork_Modification_Inventory.md)

### Scheduler admission and audible proof

When the configured voice-worker load threshold is unlimited, report zero scheduler load so the
LiveKit server does not reject the only available worker during model startup. Finite thresholds
retain SDK load calculation. This is worker admission behavior and does not enable the unsupported
native LiveKit deployment mode.

Real browser audio QA observes the rendered remote audio element: unmuted, positive volume,
active playback, decoded data and a live enabled media track. The playground's bounded
`data-viventium-audio-*` marker and `[ViventiumVoiceAudio]` event support correlation with that
call. Neither server TTS completion nor this browser state replaces human audible evidence.
