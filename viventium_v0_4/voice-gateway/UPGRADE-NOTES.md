# Voice gateway: LiveKit Agents 1.5.10 to 1.8.11

Written 10 Nov 2026. Covers the gateway source and its tests only. The call page, Core and the
launcher are not changed here.

## 1. What changed, in short

- The gateway SDK and every LiveKit plugin are pinned to 1.8.11 in `requirements.txt`.
  The optional MLX bundle installs only MLX dependencies. Each consumer first installs its own
  pinned LiveKit set: gateway 1.8.11 or Telegram's retained set. The bundle does not upgrade or
  downgrade either environment. The separate turn-detector plugin is no longer a gateway dependency.
- End of speech and barge-in are LiveKit's own, one recipe for every call
  (`worker.py: build_turn_handling`, `build_agent_session`, `load_vad`):
  - end of turn: the SDK's local turn model on the audio, `inference.TurnDetector(version="v1-mini")`;
    with AssemblyAI the listener's own end of turn (`"stt"`), no minimum wait;
  - barge-in: voice activity (`{"mode": "vad"}`); longest wait when unsure 1.5 s; preemptive
    generation off; Silero's stock sensitivity and CPU behavior with the existing 600 s speech buffer.
- xAI voice is the plugin class built directly (`worker.py: build_xai_tts`). `xai_pooled_tts.py`
  and the `_connect_ws` monkeypatch are gone.
- Local Whisper streams through the SDK's `stt.StreamAdapter`. The copied adapter is gone.
- `voice_p0_timing.py` is gone with its wiring.
- Code with no caller is gone (list in section 6).
- Not changed: the wire protocol with the call page, the backend calls, Call / Wing / Listen-Only,
  speaker attribution, multi-track ingress, provider list and selection, `FallbackTTS`,
  `mlx_chatterbox_tts.py`. Cartesia's transient HTTP retry classification is described below.

## 2. Environment variables the gateway no longer reads

22 variables. If they are still set they are ignored (there is a test for the end-of-speech ones:
`tests/test_worker_turn_recipe.py::test_removed_end_of_speech_variables_change_nothing`).

End of speech and barge-in (18):

| Variable | Old default | What applies now |
|---|---|---|
| `VIVENTIUM_TURN_DETECTION` | per provider | Fixed: local turn model `v1-mini`; `"stt"` for AssemblyAI |
| `VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S` | 0.0 / 0.35 / 0.5 / 0.9 by mode | Fixed 1.0 s for Whisper and OpenAI listening (their text arrives about 0.8 s after speech stops; found in a real call, where a sentence with a pause went out as its first half); fixed 0.0 for AssemblyAI |
| `VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S` | 1.8 / 3.0 by mode | Fixed 1.5 s |
| `VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S` | 0.5 | SDK default 0.5 s |
| `VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS` | 0 or 1 by mode | SDK default 0 |
| `VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S` | 2.0 | SDK default 2.0 s |
| `VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION` | true | SDK default true |
| `VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S` | 0.2 or 0.0 by mode | SDK default 0.0 |
| `VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S` | 1.0 local Whisper, 3.0 otherwise | SDK default 3.0 s |
| `VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD` | unset in code; the config compiler sends `0.01` | Not sent: the provider's default |
| `VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS` | unset in code; the compiler sends `100` | Not sent by us: the plugin's own default, also 100 ms |
| `VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS` | unset in code; the compiler sends `1000` | Fixed 1000 ms in code (`_ASSEMBLYAI_MAX_TURN_SILENCE_MS`); see section 4 |
| `VIVENTIUM_STT_VAD_MIN_SPEECH` | 0.1 | Stock Silero 0.05 s |
| `VIVENTIUM_STT_VAD_MIN_SILENCE` | 0.5 | Stock Silero 0.55 s |
| `VIVENTIUM_STT_VAD_ACTIVATION` | 0.4 | Stock Silero 0.5 |
| `VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH` | 600 | Fixed 600 s in code (`_MAX_UNBROKEN_SPEECH_S`): stock is 60 s, which would cut long unbroken speech on Whisper and OpenAI listening |
| `VIVENTIUM_STT_VAD_FORCE_CPU` | false | Stock Silero true |
| `LIVEKIT_REMOTE_EOT_URL` | unset | The gateway no longer reads it. The SDK still does (it means "hosted on LiveKit Cloud"); the turn model version and the barge-in mode are pinned so it cannot move either to a hosted model |

Read only by code that had no caller (4):

| Variable | What it did |
|---|---|
| `VIVENTIUM_VOICE_ABORT_TIMEOUT_S` | timeout of the unused stream-abort post |
| `VIVENTIUM_VOICE_INSIGHT_PREAMBLE` | unused insight formatter |
| `VIVENTIUM_VOICE_INSIGHT_INCLUDE_CORTEX_NAME` | unused insight formatter |
| `VIVENTIUM_VOICE_FOLLOWUP_RULES` | unused insight prompt builder |

Still read, meaning changed:

- `VIVENTIUM_VOICE_LOG_LATENCY`: still turns on the latency log lines. It no longer attaches the
  `[VoiceP0]` probes, and local Whisper no longer logs `[VoiceLatencyDetail] stream_adapter_*`.
- `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS`: still read and passed to the plugin. The inventory counted
  it with the end-of-turn values; it remains part of the supported provider configuration.

Outside this tree, to clean up at switch-over: `scripts/viventium/config_compiler.py` still writes
the turn-handling, AssemblyAI end-of-turn and VAD variables, and `viventium-librechat-start.sh`
still exports the `VIVENTIUM_STT_VAD_*` values and reads `VIVENTIUM_TURN_DETECTION`. These
settings do not control the new gateway recipe. The launcher's old turn-detector prefetch path
must be distinguished from the 1.8 local inference dependency. The shared Silero configuration
has no gateway reader; other component consumers retain their own contracts.

One SDK variable worth knowing: on macOS each call process loads the turn model's weights on first
use. `LIVEKIT_AGENTS_PRELOAD_LOCAL_INFERENCE=1` makes every call process load them while it warms up.

## 3. Behaviour a caller would notice

End of turn:

- Local Whisper and OpenAI listening: the end of a turn is decided by a model listening to the
  audio, not by a text model on the transcript or by silence alone. Shortest wait 1.0 s, longest
  1.5 s (was up to 1.8 s or 3.0 s). The model's own language table has ar, de, en, es, fr, hi, id,
  it, ja, ko, nl, pt, tr, zh.
- AssemblyAI: as before the provider ends the turn. The confidence threshold (`0.01` from the
  compiler today) is no longer sent, so the provider's default applies.

Barge-in:

- A short noise can pause the assistant on AssemblyAI calls too (the one-word minimum is gone).
  The SDK resumes the speech after 2 s if no words follow.
- Local Whisper calls: no barge-in during the first 3 s of the assistant's speech (was 1 s).
- A follow-up can start right after a reply (the 0.2 s gap is gone).

Listening:

- Silero retains the existing 600 s maximum for unbroken speech. Using the SDK's 60 s default
  here would truncate long utterances on local Whisper and OpenAI listening, so this one explicit
  buffer guard remains. AssemblyAI is not limited by this utterance buffer.
- The stock VAD is a little less sensitive (activation 0.5, was 0.4) and runs on the CPU.
- Local Whisper uses the call's VAD instead of loading a second one.

Voices:

- xAI: sockets are pooled by the plugin (rotated before 30 minutes). The plugin bounds connection
  establishment but does not bound a connected socket that sends no PCM. The existing generic
  `FallbackTTS` boundary now uses the native request timeout as a first-audio budget for every
  selected voice, including a single-provider route. Streaming starts that budget only when
  nonblank text is forwarded to the provider, so initial model thinking and empty input do not
  count. First PCM disarms it; a later failure cannot replay partial audio on another voice.
  Each failed attempt closes before the next configured voice is tried. One-shot synthesis uses
  the same first-audio guard with its already available complete input.
- One-shot synthesis no longer retries an error marked "do not retry" (the SDK used to retry
  everything). Cartesia one-shot: 401, 402, 403 and other 4xx fail at once, so a configured
  fallback voice takes over sooner; 408, 429 and 5xx are retried.

What the call page and Core see:

- `voiceRoute.stt.variant` for AssemblyAI is the engine in use (for example `u3-rt-pro`), one of
  the ids in the picker list. It used to be the constant `universal-streaming`.
- `voiceRuntimeContext.turnHandling` sent to Core with each reply request is now
  `{turnDetection, maxEndpointingDelayS}`. `minEndpointingDelayS`, `minInterruptionDurationS` and
  `minInterruptionWords` are gone. `turnDetection` is `turn_detector` on Whisper and OpenAI
  listening, `stt` on AssemblyAI. See section 5.
- While typed text from the call page is being handled, the SDK shows the user as "speaking" (the
  SDK's own typed-input contract). Nothing else about typed input changed.

Operations:

- No `[VoiceP0]` log lines. The per-turn SDK numbers (`end_of_turn_delay`, `transcription_delay`,
  `on_user_turn_completed_delay`, `llm_node_ttft`, `tts_node_ttfb`, `e2e_latency`) and each voice's
  first-byte time are still logged.
- Memory warning for hosted routes: 1000 MB (was 500), the SDK's own default. Local routes keep
  2200 MB (local Whisper) and 1400 MB (local Chatterbox). On Whisper and OpenAI listening each call
  process now also holds the turn model (the SDK's note says about 244 MB). Not measured here.
- The worker still starts through `cli.run_app`, which now prints a deprecation warning.

## 4. AssemblyAI keeps one fixed whole-utterance guard

The three configurable AssemblyAI end-of-turn variables are removed, but
`max_turn_silence=1000` is still passed as a constant to retain unfinished-sentence behavior.

Why. With turn detection `"stt"` the provider alone ends the turn. Given no value, the plugin
(1.5.10 and 1.8.11 alike) sends its Universal-3 engines, which include our default `u3-rt-pro`,
`max_turn_silence = min_turn_silence = 100 ms`. Its comment says this is meant for use with
LiveKit's turn model. Alone it would end the turn at every short pause. Main does not have this
problem today because the config compiler always sends `1000`.

To get the plugin defaults instead: delete `_ASSEMBLYAI_MAX_TURN_SILENCE_MS` and its one use in
`_build_assemblyai_stt_kwargs`, and the test
`test_assemblyai_alone_decides_the_end_of_turn_so_it_keeps_one_second_for_unfinished_sentences`.

## 5. To confirm before real calls

1. Paused and long utterances on local Whisper and AssemblyAI, including Listen-Only. The 1.0 s
   minimum and 600 s buffer guards are present; source tests do not prove the audible call path.
2. First-audio failure and recovery on a real configured voice, without replaying any heard words.
3. Memory per call process with the local turn model loaded and cold-start readiness.
4. Installed dependency parity for both the main gateway and optional MLX bundle.

Core's `voiceRuntimeContext.turnHandling` fields are optional in
`packages/api/src/voice/callContext.ts` in the LibreChat component. Omitting the three retired
fields is compatible with that parser. `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS` remains passed through;
no new configuration decision is needed to preserve its existing behavior.

## 6. Code removed

- `xai_pooled_tts.py`; `voice_p0_timing.py`; the gateway's `silero_vad_config.py` shim.
- `worker.py`: the turn-detection selection layer, the turn and AssemblyAI tuning fields and their
  parsing, `_apply_xai_tts_streaming_latency_options`, `optional_module_available`,
  `_await_participant_call_session_id`, `_parse_call_mode`, `_parse_requested_voice_route`,
  `build_stt`, `_resolve_requested_variant`, `_remote_participant_count`, three optional env parsers.
- `librechat_llm.py`: `cancel_task` (with its result cache and lock),
  `_abort_librechat_voice_stream`, `_shielded_abort_librechat_voice_stream`,
  `_voice_abort_timeout_s`, `get_call_mode`, `format_insights_for_direct_speech`,
  `wait_for_background_continuations`, `record_current_trace_hop`,
  `log_current_trace_terminal_if_ready`.
- `sse.py`: `extract_text_deltas`, `format_insight_speech_prompt`.
- `pywhispercpp_provider.py`: `ViventiumInstrumentedStreamAdapter`,
  `ViventiumInstrumentedStreamAdapterWrapper`, `_local_whisper_vad_env`.

Left in place although nothing can reach it any more: `LibreChatLLM.set_task_cancel_handler`, the
worker's `_on_task_cancel_accepted` and `_apply_task_cancel_suppression`, and
`_VoiceTaskEventGate.mark_cancel_accepted`. Only `cancel_task` ever called that handler, and
`cancel_task` had no caller. A cancel from the call page reaches the gateway as a task event, and
that path is unchanged and tested.

## 7. Fixes the new SDK made necessary

- `multi_track_ingress.py: AudioSampleTimeline`. The 1.8.11 `stt.RecognizeStream` replaces a
  declared `start_time_offset` once, when the connection reads its first frame. The timeline read
  that as a reconnect and marked the utterance-end clock "unproved" for the whole call, on every
  listener. `expect_first_frame_anchor()` tells it apart from a real reconnect. Proved with a real
  `RecognizeStream` in `tests/test_worker_stt_clock.py`.
- `worker.py: _handle_owner_text_input` runs inside `session._claim_user_turn()`, as the SDK's own
  text callback does.
- `cartesia_tts.py`, one-shot path: the retry flag for HTTP failures also covers 408 and 429.
  The SDK now honours the flag; before it retried everything.
- `worker.py: _current_stt_variant` reports the AssemblyAI engine in use.
- `worker.py: _default_job_memory_warn_mb`: hosted default 500 to 1000 MB.

Checked and left as they are:

- `_ReasonScopedAudioPauseCoordinator` (the audio-pause monkeypatch). The SDK has no pause with an
  owner, so it stays. 1.8.11 added a caller that resumes the output before each reply; a test on a
  real `AgentSession` shows that this does not release Viventium's hold.
- `LibreChatLLM` has no `aclose` override and no prewarm, and it reads only plain text parts of the
  last user message, so the `LLM.aclose` and `llm.Instructions` changes do not touch it.
- Every other `retryable=` in `cartesia_tts.py`, `fallback_tts.py` and `mlx_chatterbox_tts.py`.
  Those marked retryable behave as before (the SDK always retried). `FallbackTTS` still gives each
  wrapped voice one attempt and lets the SDK retry the whole chain only when some failure was
  retryable. Two old oddities remain: Cartesia's one-shot "timed out" error is raised after all the
  audio was produced, and a local Chatterbox timeout (120 s) is retried up to three more times.
- `FallbackTTS` re-emits audio as bytes, so for a wrapped voice the SDK's first-byte metric is
  measured from the first text, not from the provider's start. Metrics only.

## 8. Original migration test inventory

The original migration review collected 1,458 cases on the 1.5.10 baseline and 1,375 on the
initial 1.8.11 candidate. The following inventory records that migration pass; publication
follow-up results and its additional cases are recorded in section 10.
Deleted: 109 (32 of them in `test_xai_pooled_tts.py`, removed in the structural step). Added: 26.
Renamed or moved: 7.

### Deleted, with the dropped item each one pinned

**`tests/test_librechat_llm.py`: 9.** Code with no caller removed: `LibreChatLLM.cancel_task` (VG-L-037).

- `TestCompletedGenerationPlayoutStop::test_direct_completed_stop_bypasses_callwide_cancel_callback_and_task_barrier`
- `TestCompletedGenerationPlayoutStop::test_malformed_completed_stop_response_is_not_cached_or_converted_to_generation_cancel`
- `TestCompletedGenerationPlayoutStop::test_stream_then_direct_completed_stop_remains_idempotent_without_global_cancel`
- `TestExternalTaskCancelPlayout::test_direct_cancel_then_external_event_uses_existing_callback_once`
- `TestExternalTaskCancelPlayout::test_external_event_then_direct_cancel_keeps_native_interrupt_idempotent`
- `TestLibreChatStreamingRun::test_explicit_task_cancel_calls_task_endpoint_once`
- `TestLibreChatStreamingRun::test_explicit_task_cancel_stops_detached_continuation`
- `TestVoicePresentationCoordinator::test_explicit_task_cancel_calls_task_endpoint_once`
- `TestVoicePresentationCoordinator::test_explicit_task_cancel_stops_detached_continuation`

**`tests/test_librechat_llm.py`: 3.** Code with no caller removed: `format_insights_for_direct_speech` (VG-L-035).

- `TestFinalEventHelpers::test_formats_insights_for_direct_speech`
- `TestFinalEventHelpers::test_formats_insights_for_direct_speech_strips_links`
- `TestFinalEventHelpers::test_formats_insights_for_direct_speech_with_preamble`

**`tests/test_librechat_llm.py`: 1.** Code with no caller removed: the stream-abort helper `_abort_librechat_voice_stream` (VG-L-038).

- `TestLibreChatStreamingRun::test_abort_http_error_never_reads_or_logs_private_provider_body`

**`tests/test_silero_vad_config.py`: 8.** Silero VAD tuning (`VIVENTIUM_STT_VAD_*`, shared VAD config, the copied adapter class): dropped. Two of these were duplicates of tests kept in `test_pywhispercpp_provider.py`.

The rest of the file (one test moved, see below).

**`tests/test_voice_p0_timing.py`: 25.** `voice_p0_timing.py` removed: every probe hooked private SDK or plugin internals and was hard-gated to 1.5.10 (VG-W-119, VG-W-120).

The whole file.

**`tests/test_worker_ref_audio_validation.py`: 2.** xAI `_connect_ws` monkeypatch (dropped: the plugin takes the latency option itself).

- `TestRefAudioValidation::test_apply_xai_tts_streaming_latency_options_adds_query_param`
- `TestRefAudioValidation::test_apply_xai_tts_streaming_latency_options_warns_when_hook_missing`

**`tests/test_worker_ref_audio_validation.py`: 2.** Endpointing and interruption default numbers and overrides (dropped variables).

- `TestRefAudioValidation::test_load_env_respects_voice_endpointing_overrides`
- `TestRefAudioValidation::test_load_env_sets_voice_endpointing_defaults`

**`tests/test_worker_turn_handling.py`: 12.** Turn-detection selection, fallback ladder and per-provider default numbers (dropped: one SDK recipe).

- `TestWorkerTurnHandling::test_current_call_facts_use_resolved_detection_after_runtime_fallback`
- `TestWorkerTurnHandling::test_explicit_turn_detector_falls_back_to_aligned_profile_when_uncached`
- `TestWorkerTurnHandling::test_load_env_defaults_to_stt_for_assemblyai_when_turn_detector_missing`
- `TestWorkerTurnHandling::test_load_env_keeps_stt_default_for_assemblyai_when_turn_detector_is_available`
- `TestWorkerTurnHandling::test_load_env_respects_explicit_turn_detector_override`
- `TestWorkerTurnHandling::test_load_turn_detection_falls_back_to_stt_when_turn_detector_missing`
- `TestWorkerTurnHandling::test_load_turn_detection_falls_back_to_stt_when_turn_detector_weights_missing`
- `TestWorkerTurnHandling::test_load_turn_detection_falls_back_to_vad_for_local_stt_when_runner_missing`
- `TestWorkerTurnHandling::test_load_turn_detection_returns_turn_detector_when_available`
- `TestWorkerTurnHandling::test_local_whisper_falls_back_to_vad_when_runner_is_not_registered`
- `TestWorkerTurnHandling::test_local_whisper_semantic_turn_detector_respects_explicit_min_words_override`
- `TestWorkerTurnHandling::test_local_whisper_uses_semantic_turn_detector_when_cached`

**`tests/test_worker_turn_handling.py`: 1.** 1.5.10 `AgentSession` signature assert for arguments the gateway no longer passes.

- `TestWorkerTurnHandling::test_installed_agents_sdk_accepts_interruption_kwargs`

**`tests/test_worker_turn_handling.py`: 1.** Turn-tuning and AssemblyAI end-of-turn environment overrides (dropped variables).

- `TestWorkerTurnHandling::test_load_env_respects_turn_handling_overrides`

**`tests/test_worker_turn_handling.py`: 5.** Silero VAD tuning values and the VAD cache key (dropped: stock `silero.VAD.load()`).

- `TestWorkerTurnHandling::test_local_session_uses_shared_minimum_speech_default`
- `TestWorkerTurnHandling::test_local_whisper_respects_explicit_vad_min_silence_override`
- `TestWorkerTurnHandling::test_local_whisper_respects_explicit_vad_min_speech_override`
- `TestWorkerTurnHandling::test_local_whisper_uncached_fallback_uses_shared_vad`
- `TestWorkerTurnHandling::test_vad_kwargs_cache_key_reuses_shared_timing_when_provider_changes`

**`tests/test_worker_turn_handling.py`: 1.** Turn-detector plugin probing (dropped).

- `TestWorkerTurnHandling::test_optional_module_available_handles_missing_parent_package`

**`tests/test_worker_turn_handling.py`: 7.** Turn-detector readiness probing: plugin cache, runner registration, remote URL (dropped).

- `TestWorkerTurnHandling::test_semantic_turn_detector_status_allows_remote_inference`
- `TestWorkerTurnHandling::test_semantic_turn_detector_status_requires_registered_local_runner`
- `TestWorkerTurnHandling::test_turn_detector_model_cache_check_looks_for_exact_assets`
- `TestWorkerTurnHandling::test_turn_detector_model_cache_check_rejects_partial_snapshot`
- `TestWorkerTurnHandling::test_turn_detector_model_cache_check_returns_false_when_exact_assets_missing`
- `TestWorkerTurnHandling::test_turn_detector_runner_registration_does_not_import_when_assets_missing`
- `TestWorkerTurnHandling::test_turn_detector_runner_registration_imports_multilingual_plugin`

**`tests/test_xai_pooled_tts.py`: 32.** `xai_pooled_tts.py` removed (in the structural step, before this pass): it was a backport of the socket pool the 1.8.11 xAI plugin now has (VG-L-075, VG-L-076).

The whole file.

Also removed from the source of `tests/test_librechat_llm.py`, never collected by pytest: the copies
of `test_explicit_task_cancel_calls_task_endpoint_once` and
`test_explicit_task_cancel_stops_detached_continuation` in `_PublicVoicePresentationCoordinatorTests`.

### Renamed or moved (same behaviour asserted)

- `test_librechat_llm.py`: the two `test_get_call_mode_*` tests are now `test_get_call_state_*`
  and call the kept `get_call_state`.
- `test_sse.py`: `test_extract_text_deltas_preserves_space_only_chunks` is now
  `test_sanitized_text_deltas_preserve_space_only_chunks` on the two kept functions.
- `test_worker_turn_handling.py`: the two `test_requested_*_override_recomputes_turn_profile_*`
  tests are now `test_requested_assemblyai_route_uses_the_listeners_own_end_of_turn` and
  `test_requested_local_route_reports_ready_route_and_local_turn_model` (the route facts are kept,
  the per-provider numbers are gone). `test_build_stt_selection_passes_assemblyai_turn_kwargs` is
  now `..._passes_assemblyai_engine_speaker_labels_and_fixed_turn_cap`.
- `test_intel_default_threads_are_lowered` moved from `test_silero_vad_config.py` to
  `test_pywhispercpp_provider.py`.

### Re-validated against 1.8.11 (pin updated, behaviour assertion kept)

- `test_worker_turn_handling.py::TestNativePublicPartFlush::test_actual_sdk_serializes_fresh_tts_nodes_and_drains_word_tag_buffers`.
  1.8.11 splits a reply on the flush marker in the reply pipeline, no longer inside
  `perform_tts_inference`. The test now runs a real `AgentSession`: the first public part is
  spoken from its own TTS input while the backend is still paused, and the next part starts only
  after it.
- `test_worker_stt_clock.py`: the default `stt_node` digest and version are pinned to 1.8.11; the
  fake stream re-anchors its offset the way 1.8.11 does; the real-SDK reconnect test uses real
  audio frames (1.8.11 times only those) and still ends "unproved".
- `test_worker_stt_assemblyai.py` (three unresolved-speaker tests): the plugin stream now reads its
  offset from its input channel. `PENDING` is still passed through by the plugin and still treated
  as "no speaker" by the gateway.
- `test_owner_track_capability.py`: the temporary adapter is closed by the node, and the real
  adapter copies `keyterms` / `chat_context` from the listener it wraps.
- `test_voice_native_streaming.py::test_pinned_xai_pushes_share_one_segment_until_end_input`: the
  finished socket goes back to the plugin's pool and is closed with the voice.
- `test_fallback_tts.py`: a 429 status error is retryable on 1.8.11 (the log line reports it so).
- `test_typed_call_input.py`, `test_audible_interruption_delivery.py`: fake sessions offer the
  SDK's user-turn claim; one test uses a real `AgentSession`.
- `test_worker_turn_handling.py::test_load_env_keeps_hosted_voice_memory_warning_threshold`: 1000.
- `test_librechat_llm.py::TestHostAdmissionFailureKeepsCall::test_connection_refused_retains_input_until_budget_without_provider_claim`:
  failed now and then on the baseline too. Its 30 ms budget left 3 ms between "stop retrying" and
  "stop waiting"; it now uses 600 ms. Same assertion.

### Added

- `tests/test_worker_turn_recipe.py` (15): the recipe per listener, the version pin, barge-in mode,
  preemptive generation off, the session options including "do not forward chat context", removed
  variables are inert, the stock VAD, the xAI voice (plugin class, latency option, space-keeping
  tokenizer, configured endpoint), the fixed AssemblyAI cap.
- `tests/test_worker_stt_clock.py` (3): first-frame anchor is not a reconnect; a reconnect still is;
  an undeclared offset behaves as before.
- `tests/test_pywhispercpp_provider.py` (3): the SDK adapter on the call's VAD; the stock VAD when
  none is given; speech end time and listener progress.
- `tests/test_cartesia_tts.py` (2): which one-shot failures are retried.
- `tests/test_worker_turn_handling.py` (1): the audio hold on a real session.
- `tests/test_worker_stt_assemblyai.py` (1): the published engine.
- `tests/test_typed_call_input.py` (1): the user-turn claim on a real session.

### Initial scratch-workspace prerequisites

Two cases initially failed on both baseline and candidate because the scratch workspace lacked
files outside the gateway tree:

- `test_sse.py::TestSSEParser::test_sanitize_voice_tts_text_tracks_shared_artifact_contract` needs
  `qa/modern-playground-voice/scripts/voice_artifact_contract.cjs` and Core modules it requires.
- `test_worker_ref_audio_validation.py::TestRefAudioValidation::test_all_runtime_tts_provider_models_declare_exact_control_or_plain_text_contract`
  needs `viventium_v0_4/LibreChat/shared/voice/tts_provider_capabilities.json`.

Both pass in a scratch copy of this tree with those files taken from the public checkout.

This historical suite result did not exercise `mlx-audio`; its Chatterbox cases used a mocked
model. It did not prove real audio, a provider or a room. Publication follow-up results must be
recorded against the exact candidate separately.

## 9. What the inventories had wrong or incomplete

1. Worker inventory, section 2a row E8, section 2d and open question 2: "None if unset today".
   The config compiler always writes the three AssemblyAI end-of-turn values (`0.01`, `100`,
   `1000`), so they are set on every compiled runtime. And the plugin default for the Universal-3
   engines is not "provider defaults" but `max = min = 100 ms`. See section 4.
2. Worker inventory, section 4: 19 end-of-speech variables. 18 were removed;
   `VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS` is still read.
3. Worker inventory, VG-W-111: "sdk-has-it (likely)". The timeline is still needed: the SDK anchors
   each connection on its first frame but does not account for a gap in the audio inside one
   connection. The stated risk (first-frame re-anchor read as a retry) is real, for the owner's
   stream only; the streams of other participants never declare an offset and are not affected.
4. Worker inventory, VG-W-068: "`FlushSentinel` ... unchanged". The type is, but where the SDK acts
   on it moved (reply pipeline instead of `perform_tts_inference`).
5. Worker inventory, VG-W-105: the shared VAD config "also serves Telegram". In the public checkout
   only the gateway imports it.
6. Speech inventory, section 6: the three underscore-named base classes in `test_librechat_llm.py`
   do not make 85 tests run twice. Pytest does not collect them; each test runs once through its
   subclass, and 45 of the 80 base tests are replaced there by a copy with the same name, so the
   base copy never runs.
7. Speech inventory, section 4 row 23: correct, with one consequence not stated: a 429 status error
   from a plugin was non-retryable on 1.5.10 and is retryable on 1.8.11.
8. Speech inventory, VG-L-037 and worker inventory, VG-W-052 / VG-W-092: removing `cancel_task`
   leaves the worker's "cancel accepted" handler without any trigger (section 6).
9. Not in either inventory: the 1.8.11 stream clock is anchored only by real `rtc.AudioFrame`
   objects (a test that feeds stand-in frames sees no anchoring at all).


## 10. Publication follow-up, 20 November 2026

The complete affected gateway bank passes **1,382 cases** on the 1.8.11 dependency set, including
the two cross-tree cases above with their actual declared source artifacts available. This is
source and synthetic-runtime proof, not installed or audible call acceptance.

Seven new first-audio cases cover the real pinned xAI stream against a connected silent synthetic
socket, exactly one fallback and attempt closure, one-shot synthesis, model thinking before text,
empty input, a delayed tail after first PCM, a sole unavailable provider, and cancellation before
and after input. The same connected-silent case fails with the baseline generic TTS boundary and
passes with the new deadline; no provider API or real account is contacted. Existing partial-audio
failure and native retry tests also pass. The SDK retains ownership of its xAI socket pool.

The optional MLX dependency file no longer declares an Agents version. The main gateway and the
retained Telegram runtime install their own exact SDK/plugin sets before adding MLX dependencies.
No Telegram SDK upgrade, installed runtime change, model download or production restart is claimed.
Real call, cold-start memory and audible device-path acceptance remain open as listed in section 5.
