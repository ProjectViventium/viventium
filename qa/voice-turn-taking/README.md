# Voice Turn-Taking QA

## Goal

Prove that Viventium's current LiveKit voice stack no longer defaults AssemblyAI to pure VAD-only
turn ending, that the new turn-handling controls are config/compiler owned, and that fresh boots do
not fail when the optional semantic turn-detector plugin is installed.

## Acceptance Criteria

- AssemblyAI defaults to `turn_detection=stt` when the provider supports endpointing.
- Silero VAD stays attached for interruption responsiveness.
- The default `stt` path does not stack the old large endpointing delay on top of provider
  endpointing.
- LiveKit interruption knobs compile from canonical config into generated runtime env.
- AssemblyAI endpointing knobs compile from canonical config into generated runtime env.
- Worker logs expose normalized turn-end reasons.
- A hostile restart with no turn-detector model cache still boots cleanly when the plugin is
  installed.
- Existing voice-gateway and compiler test suites remain green.
- Local `whisper_local` + `local_chatterbox_turbo_mlx_8bit` route plumbing remains functional after
  the turn-taking changes.
- Per-call requested STT overrides recompute the effective turn-taking defaults from the final STT
  provider instead of inheriting stale defaults from the machine route.
- Voice worker memory/prewarm controls compile from canonical config into generated runtime env.

## Automated Verification

Run from the canonical repo checkout.

### Voice gateway targeted turn-handling tests

```bash
cd viventium_v0_4/voice-gateway
.venv/bin/python -m unittest discover -s tests -p 'test_worker_turn_handling.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_worker_followup_scheduler.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_worker_ref_audio_validation.py' -v
```

Result:
- passed
- includes a signature guard proving the pinned `livekit-agents` build actually accepts:
  - `min_interruption_words`
  - `false_interruption_timeout`
  - `resume_false_interruption`
  - `min_consecutive_speech_delay`
  - mixed-provider override regression coverage for `whisper_local -> assemblyai` and
    `assemblyai -> pywhispercpp`
  - exact turn-detector asset cache verification for `onnx/model_q8.onnx` plus `languages.json`

### Voice gateway full suite

```bash
cd viventium_v0_4/voice-gateway
.venv/bin/python -m unittest discover -s tests -v
```

Result:
- `158` tests passed

### Compiler / release contract

```bash
uv run --with pytest --with pyyaml pytest tests/release/test_config_compiler.py -q
uv run --with pytest --with pyyaml pytest tests/release/test_voice_playground_dispatch_contract.py -q
```

Result:
- `55` compiler tests passed
- `9` voice playground dispatch tests passed

## Hostile Restart QA

Purpose:
- verify a clean boot when `livekit-plugins-turn-detector` is installed
- verify launcher-owned model predownload
- verify the previous missing-`model_q8.onnx` boot failure is gone

Steps:

```bash
rm -rf "$HOME/.cache/huggingface/hub/models--livekit--turn-detector"
rm -f "$HOME/Library/Application Support/Viventium/state/runtime/isolated/logs/voice_gateway.log"
rm -f "$HOME/Library/Application Support/Viventium/state/runtime/isolated/logs/voice_gateway_deps.log"
./bin/viventium stop
./bin/viventium start
```

Evidence:
- `voice_gateway_deps.log` was created automatically during startup
- it downloaded the turn-detector assets before worker boot
- the boot no longer registered the turn-detector plugin on the default local `vad` route
- `voice_gateway.log` no longer contained the old `model_q8.onnx` / inference-runner
  initialization failure
- the worker registered successfully
- explicit `turn_detector` mode now also has a runtime safeguard: if weights are missing despite the
  plugin being installed, `load_turn_detection()` falls back to `stt` instead of instantiating a
  broken detector path

Key log evidence:

```text
[viventium] Pre-downloading voice turn detector model...
INFO livekit.agents - Downloading files for <livekit.plugins.turn_detector.EOUPlugin ...>
INFO livekit.agents - Finished downloading files for <livekit.plugins.turn_detector.EOUPlugin ...>
{"message": "registered worker", ...}
```

## AssemblyAI Default-Path Smoke

This machine did not have a live AssemblyAI key loaded in runtime env during QA, so the smoke used
a synthetic key only to prove the code path and defaults. No external STT session was started.

Command:

```bash
cd viventium_v0_4/voice-gateway
source "$HOME/Library/Application Support/Viventium/runtime/runtime.env"
test -f "$HOME/Library/Application Support/Viventium/runtime/runtime.local.env" && \
  source "$HOME/Library/Application Support/Viventium/runtime/runtime.local.env"
export ASSEMBLYAI_API_KEY=dummy-assemblyai-key
export OPENAI_API_KEY=dummy-openai-key
export VIVENTIUM_STT_PROVIDER=assemblyai
unset VIVENTIUM_TURN_DETECTION
export VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD=0.01
export VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS=100
export VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS=1000
.venv/bin/python - <<'PY'
import worker
env = worker.load_env()
selection = worker.build_stt_selection(env, None)
turn_detection, reason = worker.load_turn_detection(env, has_vad=True)
print("voice_turn_detection=", env.voice_turn_detection)
print("turn_detection=", type(turn_detection).__name__, reason)
print("selection=", type(selection[0]).__name__, selection[1])
print("assemblyai_kwargs=", worker._build_assemblyai_stt_kwargs(env))
print("min_endpoint=", env.voice_min_endpointing_delay_s)
print("max_endpoint=", env.voice_max_endpointing_delay_s)
print("min_interrupt_words=", env.voice_min_interruption_words)
print("false_interrupt_timeout=", env.voice_false_interruption_timeout_s)
print("resume_false_interrupt=", env.voice_resume_false_interruption)
print("min_consecutive_speech_delay=", env.voice_min_consecutive_speech_delay_s)
PY
```

Observed result:

```text
voice_turn_detection= stt
turn_detection= str stt_end_of_turn
selection= STT assemblyai
assemblyai_kwargs= {'end_of_turn_confidence_threshold': 0.01, 'min_turn_silence': 100, 'max_turn_silence': 1000}
min_endpoint= 0.0
max_endpoint= 1.8
min_interrupt_words= 1
false_interrupt_timeout= 2.0
resume_false_interrupt= True
min_consecutive_speech_delay= 0.2
```

Interpretation:
- AssemblyAI now defaults to `stt`, not `vad`
- the shipped compiler/runtime path now makes the documented AssemblyAI baseline explicit:
  - `end_of_turn_confidence_threshold=0.01`
  - `min_turn_silence=100`
  - `max_turn_silence=1000`
- the legacy Viventium env/config key for `min_end_of_turn_silence_when_confident` is mapped onto
  the provider's current `min_turn_silence` knob to avoid the deprecated alias at runtime
- interruption handling is stricter without waiting for a large extra endpointing delay

## Local Route + Worker Controls Smoke

Purpose:
- prove the local `whisper_local` + `local_chatterbox_turbo_mlx_8bit` route still hydrates from
  saved/session config and remains available after the turn-taking changes
- prove the new worker memory/prewarm controls compile from canonical config

Commands:

```bash
cd viventium_v0_4/LibreChat/api
npm run test:ci -- --runInBand server/services/viventium/__tests__/CallSessionService.spec.js

cd ../../voice-gateway
.venv/bin/python -m unittest tests.test_worker_ref_audio_validation tests.test_worker_turn_handling -v
```

Observed result:
- LibreChat call-session service slice passed (`11` tests)
- voice-gateway local-route + turn-handling slices passed
- worker options now carry `job_memory_warn_mb` / `job_memory_limit_mb`
- opting out of local TTS prewarm skips the in-process Chatterbox warm load without breaking route
  availability

## Notes

- Explicit `turn_detector` / semantic-turn-detector behavior is covered by unit tests. Direct
  ad-hoc instantiation outside a LiveKit job context raises the expected job-context error, so
  runtime validation for that mode should be done through the worker/test harness rather than a raw
  REPL import.
- This QA pass proves the structural fix and clean boot path. Real-call tuning for specific speech
  styles should now be done by adjusting surfaced config knobs rather than patching complaint-shaped
  heuristics into runtime code.

## 2026-04-21 Background Follow-Up Window + Endpointing Evidence

### Scope

- unify the umbrella product phrase to `background follow-up window`
- raise the shared default to `30s` with compiler-owned parity across LibreChat, live voice, and
  Telegram
- add durable `user_turn_completed` evidence for real live calls
- verify the modern playground still completes a real answer on the current localhost stack

### Config / compiler proof

Live generated runtime env after `bin/viventium start --restart`:

```text
VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S=30
VIVENTIUM_VOICE_FOLLOWUP_GRACE_S=30
VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S=30
VIVENTIUM_STT_PROVIDER=whisper_local
```

Automated release coverage:

```bash
uv run --with pytest --with pyyaml pytest tests/release/test_config_compiler.py -q
```

Result:
- `57` tests passed

Interpretation:
- the shared `30s` default is now compiler-owned rather than drifting by surface
- this machine still runs `whisper_local` as the machine route, which is why AssemblyAI env knobs
  do not appear in the live runtime env on this laptop unless AssemblyAI is selected

### Focused runtime regression coverage

```bash
cd viventium_v0_4/LibreChat/api
npm run test:api -- --runInBand --runTestsByPath \
  server/routes/viventium/__tests__/voice.spec.js \
  server/services/viventium/__tests__/cortexFollowupGrace.spec.js

cd ../../telegram-viventium/TelegramVivBot
uv run --with pytest --with pytest-asyncio pytest ../tests/test_librechat_bridge.py -q
```

Result:
- LibreChat focused slice passed
- Telegram bridge slice passed (`62` tests)

### Real browser QA

Account used:
- `test@viventium.ai`

Observed localhost flow:
1. Opened the authenticated LibreChat surface on `http://localhost:3190`
2. Launched the modern playground from `Start voice call`
3. Connected the live call on `http://localhost:3300`
4. Sent the transcript prompt:
   - `What were we talking about earlier today about the dashboard launch and the maintenance window?`
5. Received a real assistant answer in the transcript:

```text
From what I've got stored: the dashboard launch does not need an on-site trip.
It's screen-based, data-driven, and can run remotely. The maintenance window
also moved later so it would stop colliding with the overnight batch work.
Does that still sound right?
```

Acceptance result:
- modern playground connected successfully
- transcript send worked
- recall continuity worked on the QA account
- the response completed without raw background-insight leakage
- browser console showed no errors during the successful run
- remaining console noise was warning-only:
  - missing `lk-user-choices` local-storage key
  - repeated `lk.agent.session` byte-stream handler warnings

### Live call timing evidence

For call session `<call-session-id>`, the live worker log recorded:

```text
[voice-gateway] AgentSession callSessionId=<call-session-id> \
  turn_detection=stt turn_end_reason=stt_end_of_turn min_interrupt=0.5s \
  min_interrupt_words=1 min_endpoint=0.0s max_endpoint=1.8s \
  false_interrupt_timeout=2.0 resume_false_interrupt=True \
  min_consecutive_speech_delay=0.2s

[voice-gateway] user_turn_completed source=livekit_metrics \
  callSessionId=<call-session-id> reason=stt_end_of_turn \
  detection=stt eou_delay=0.896s transcription_delay=0.894s
```

Interpretation:
- the current live call path is using STT-owned end-of-turn, not VAD-only turn ending
- the new durable `user_turn_completed` evidence is present on the live call surface with the exact
  `callSessionId`
- the endpointing decision for this live run happened in under one second after end-of-turn

### Conclusion

- The product now uses one umbrella phrase in docs and config: `background follow-up window`
- The shared default is `30s` across LibreChat, voice, and Telegram
- Real localhost browser QA on the isolated stack still works after the change
- The live runtime now emits durable turn-completion evidence that is specific enough to diagnose
  future endpointing complaints without guessing from browser screenshots alone
