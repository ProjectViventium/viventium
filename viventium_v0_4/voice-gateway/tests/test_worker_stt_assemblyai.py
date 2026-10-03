# === VIVENTIUM START ===
# Feature: Selectable AssemblyAI streaming STT model (Universal-3 Pro / u3-rt-pro) in the modern
#   playground "Listening" picker.
# Added: 2026-05-29
# Why: Regression coverage for the bug where the AssemblyAI engine variant was cosmetic — the model
#   was never passed to the plugin, the catalog advertised an invalid "universal-streaming" id, and
#   the selected variant was dropped in _apply_requested_voice_route. These tests pin: the proven
#   u3-rt-pro default, the real plugin-valid variant set surfaced in the capability catalog, that a
#   picked variant is applied and normalized, and that build_stt_selection actually hands the model
#   to livekit-plugins-assemblyai.
import os
import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker import (  # noqa: E402
    ASSEMBLYAI_DEFAULT_STT_MODEL,
    ASSEMBLYAI_STT_MODELS,
    HAS_ASSEMBLYAI,
    VoiceRouteError,
    _apply_requested_voice_route,
    _assemblyai_stt_model_variants,
    _build_assemblyai_stt_kwargs,
    _build_voice_capability_catalog,
    _normalize_assemblyai_stt_model,
    build_stt_selection,
    load_env,
    _ingest_raw_stt_speaker_event,
)
from speaker_segments import SpeakerSegmentTracker
from multi_track_ingress import MultiTrackIngressCoordinator
from livekit.agents.stt import SpeechEventType
from livekit.plugins.assemblyai.stt import SpeechStream as AssemblyAISpeechStream


def _actual_assemblyai_events(labels):
    """Exercise the pinned plugin's actual typed Turn decoder without a network call."""
    stream = object.__new__(AssemblyAISpeechStream)
    events = []
    stream._event_ch = SimpleNamespace(send_nowait=events.append)
    stream._opts = SimpleNamespace(format_turns=False)
    stream._speech_duration = 0.0
    stream._last_preflight_start_time = 0.0
    stream._session_id = 'synthetic-pending'
    stream.start_time_offset = 0.0
    stream.start_time = 1_790_000_000.0
    for index, label in enumerate(labels):
        start_ms = index * 4000
        stream._process_stream_event({
            'type': 'Turn', 'speaker_label': label, 'end_of_turn': True,
            'transcript': 'This is a stable synthetic attribution sentence.',
            'words': [{'text': 'Stable', 'start': start_ms, 'end': start_ms + 1000},
                      {'text': 'sentence', 'start': start_ms + 1000, 'end': start_ms + 3000}],
        })
    return stream, [event for event in events if event.type == SpeechEventType.FINAL_TRANSCRIPT]


class TestAssemblyAIPendingSpeaker(unittest.TestCase):
    def test_pending_is_unknown_without_relabeling_owner_but_real_second_voice_still_demotes(self):
        stream, events = _actual_assemblyai_events(['A', 'PENDING', 'A', 'B'])
        self.assertEqual(events[1].alternatives[0].speaker_id, 'PENDING')
        tracker = SpeakerSegmentTracker(call_session_id='synthetic-pending', owner_signed=True,
            participant_authenticated=True, participant_identity='synthetic-owner', participant_name='You')
        for index, event in enumerate(events):
            _ingest_raw_stt_speaker_event(tracker, event, timeline_offset_s=0, speech_stream=stream)
            segments, _ = tracker.finalize_turn(event.alternatives[0].text)
            if index == 1:
                self.assertFalse(tracker.shared_microphone_detected)
                self.assertEqual(tracker.pop_session_state_changes(), [])
                self.assertEqual(segments[0]['speaker']['actorTrust'], 'unknown')
                self.assertEqual(segments[0]['speaker']['key'], 'unknown')
            elif index < 3:
                self.assertEqual(segments[0]['speaker']['actorTrust'], 'owner_participant')
            else:
                self.assertTrue(tracker.shared_microphone_detected)
                self.assertEqual(segments[0]['speaker']['actorTrust'], 'shared_mic_unverified')
                self.assertEqual(tracker.pop_session_state_changes()[0]['attributionState'], 'shared_mic_unverified')

    def test_pending_literal_is_not_remapped_for_a_different_provider(self):
        _, events = _actual_assemblyai_events(['A', 'PENDING'])
        tracker = SpeakerSegmentTracker(call_session_id='synthetic-other')
        for event in events:
            _ingest_raw_stt_speaker_event(tracker, event, timeline_offset_s=0,
                                         speech_stream=SimpleNamespace())
            tracker.finalize_turn(event.alternatives[0].text)
        self.assertTrue(tracker.shared_microphone_detected)

    def test_ambient_pending_does_not_create_a_second_speaker_tombstone(self):
        stream, events = _actual_assemblyai_events(['A', 'PENDING', 'A'])
        states, turns = [], []
        async def append(target, value):
            target.append(value)
        async def empty_audio():
            if False:
                yield
        async def event_source():
            for event in events:
                yield event
        stream._event_aiter = event_source()
        stream._task = SimpleNamespace(cancelled=lambda: False, exception=lambda: None)
        stream.end_input = lambda: None
        coordinator = MultiTrackIngressCoordinator(call_session_id='synthetic-pending',
            owner_participant_identity='synthetic-owner', stt_impl=SimpleNamespace(stream=lambda: stream),
            audio_stream_factory=lambda _track: empty_audio(), clock=lambda: 0,
            wall_clock=lambda: 1_790_000_000.0,
            on_segment_changes=lambda _value: append([], _value),
            on_session_state_change=lambda value: append(states, value),
            on_ambient_turn=lambda value: append(turns, value))
        tracker = SpeakerSegmentTracker(call_session_id='synthetic-pending',
            participant_authenticated=True, participant_identity='synthetic-guest')
        asyncio.run(coordinator._run_track_once(participant=None, track=None,
                                                track_sid='synthetic-track', tracker=tracker))
        self.assertEqual(states, [])
        self.assertFalse(tracker.shared_microphone_detected)
        self.assertEqual(turns[0]['segments'][0]['speaker']['actorTrust'], 'authenticated_participant')
        self.assertEqual(turns[1]['segments'][0]['speaker']['actorTrust'], 'unknown')
        self.assertEqual(turns[2]['segments'][0]['speaker']['actorTrust'], 'authenticated_participant')

_VALID_MODEL_IDS = {model_id for model_id, _label in ASSEMBLYAI_STT_MODELS}


def _assemblyai_stt_capability(env):
    for capability in _build_voice_capability_catalog(env):
        if capability.get("modality") == "stt" and capability.get("id") == "assemblyai":
            return capability
    raise AssertionError("AssemblyAI STT capability missing from catalog")


def _assemblyai_env(**overrides):
    # AssemblyAI availability + selection are read from os.environ at call time (load_env,
    # capability catalog, and build_stt_selection all use os.getenv), so the patch must wrap the
    # whole exercise — not just load_env() — or the key disappears and the worker falls back.
    base = {
        "VIVENTIUM_VOICE_STT_PROVIDER": "assemblyai",
        "ASSEMBLYAI_API_KEY": "test-assemblyai-key",
        "OPENAI_API_KEY": "test-openai-key",
    }
    base.update(overrides)
    return base


class TestAssemblyAISttModelNormalization(unittest.TestCase):
    """Pure-function behavior — no runtime/env needed."""

    def test_default_constant(self):
        self.assertEqual(ASSEMBLYAI_DEFAULT_STT_MODEL, "u3-rt-pro")

    def test_normalizer_handles_alias_and_junk(self):
        self.assertEqual(_normalize_assemblyai_stt_model("u3-pro"), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model(""), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model("  garbage  "), "u3-rt-pro")
        self.assertEqual(_normalize_assemblyai_stt_model("u3-rt-pro"), "u3-rt-pro")
        self.assertEqual(
            _normalize_assemblyai_stt_model("universal-streaming-english"),
            "universal-streaming-english",
        )

    def test_variants_helper_puts_selected_first(self):
        variants = _assemblyai_stt_model_variants("universal-streaming-multilingual")
        ids = [variant_id for variant_id, _label in variants]
        self.assertEqual(ids[0], "universal-streaming-multilingual")
        self.assertEqual(set(ids), _VALID_MODEL_IDS)

    def test_variants_helper_defaults_unknown_first_entry(self):
        ids = [variant_id for variant_id, _label in _assemblyai_stt_model_variants("bogus")]
        self.assertEqual(ids[0], "u3-rt-pro")


class TestAssemblyAISttModelSelection(unittest.TestCase):
    def test_default_model_is_u3_rt_pro(self):
        with patch.dict(os.environ, _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL=""), clear=False):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "u3-rt-pro")

    def test_env_var_selects_valid_model(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="universal-streaming-multilingual"),
            clear=False,
        ):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "universal-streaming-multilingual")

    def test_unknown_env_model_normalizes_to_default(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="totally-made-up"),
            clear=False,
        ):
            env = load_env()
        self.assertEqual(env.assemblyai_stt_model, "u3-rt-pro")

    def test_catalog_lists_u3_rt_pro_and_drops_legacy_id(self):
        with patch.dict(os.environ, _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL=""), clear=False):
            capability = _assemblyai_stt_capability(load_env())
        variant_ids = [variant["id"] for variant in capability["variants"]]
        labels = {variant["id"]: variant["label"] for variant in capability["variants"]}
        self.assertEqual(variant_ids[0], "u3-rt-pro")
        self.assertIn("universal-streaming-english", variant_ids)
        self.assertIn("universal-streaming-multilingual", variant_ids)
        # The old cosmetic/invalid id must not resurface in the picker.
        self.assertNotIn("universal-streaming", variant_ids)
        self.assertEqual(labels["u3-rt-pro"], "Universal-3 Pro streaming (u3-rt-pro)")

    def test_build_kwargs_includes_selected_model(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            kwargs = _build_assemblyai_stt_kwargs(load_env())
        self.assertEqual(kwargs["model"], "u3-rt-pro")

    def test_build_kwargs_passes_contextual_terms_to_assemblyai(self):
        keyterms = ["Alpha Ledger.pdf", "Beta Notes.xlsx"]
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            kwargs = _build_assemblyai_stt_kwargs(load_env(), keyterms)
        self.assertEqual(kwargs["keyterms_prompt"], keyterms)

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_apply_requested_route_applies_selected_variant(self):
        requested = {
            "stt": {"provider": "assemblyai", "variant": "universal-streaming-multilingual"},
            "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
        }
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            applied = _apply_requested_voice_route(env, requested, capabilities)
        self.assertEqual(applied.stt_provider, "assemblyai")
        self.assertEqual(applied.assemblyai_stt_model, "universal-streaming-multilingual")

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_apply_requested_route_rejects_unknown_saved_variant(self):
        requested = {
            "stt": {"provider": "assemblyai", "variant": "nonexistent-engine"},
            "tts": {"provider": "openai", "variant": "gpt-4o-mini-tts"},
        }
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            env = load_env()
            capabilities = _build_voice_capability_catalog(env)
            with self.assertRaises(VoiceRouteError) as raised:
                _apply_requested_voice_route(env, requested, capabilities)
        self.assertEqual(raised.exception.code, "no_route")

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_build_stt_selection_passes_model_to_plugin(self):
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ):
            stt_impl, provider = build_stt_selection(load_env(), vad=None)
        self.assertEqual(provider, "assemblyai")
        # The plugin exposes the resolved model via the .model property.
        self.assertEqual(getattr(stt_impl, "model", None), "u3-rt-pro")

    @unittest.skipUnless(HAS_ASSEMBLYAI, "livekit-plugins-assemblyai not installed")
    def test_build_stt_selection_passes_terms_only_to_assemblyai(self):
        keyterms = ["Alpha Ledger.pdf", "Beta Notes.xlsx"]
        with patch.dict(
            os.environ,
            _assemblyai_env(VIVENTIUM_ASSEMBLYAI_STT_MODEL="u3-rt-pro"),
            clear=False,
        ), patch("worker.assemblyai_stt.STT", return_value="assemblyai-stt") as stt_cls:
            stt_impl, provider = build_stt_selection(
                load_env(), vad=None, contextual_keyterms=keyterms
            )
        self.assertEqual(stt_impl, "assemblyai-stt")
        self.assertEqual(provider, "assemblyai")
        self.assertEqual(stt_cls.call_args.kwargs["keyterms_prompt"], keyterms)


if __name__ == "__main__":
    unittest.main()
# === VIVENTIUM END ===
