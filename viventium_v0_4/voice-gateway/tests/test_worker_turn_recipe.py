"""The one end-of-speech recipe on LiveKit Agents 1.8.11 (fixed gateway recipe).

Turn detection is the SDK's local turn model, or the listener's own end of turn for AssemblyAI.
Barge-in is voice activity. Nothing here is tunable by environment any more.
"""
import asyncio
import dataclasses
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from livekit.agents import AgentSession, inference
from livekit.agents.types import NOT_GIVEN
from livekit.plugins import xai as xai_plugin

import worker
from worker import (
    _build_xai_tts_word_tokenizer,
    build_agent_session,
    build_turn_handling,
    build_xai_tts,
    load_env,
    load_vad,
)

REMOVED_ENVIRONMENT = {
    "VIVENTIUM_TURN_DETECTION": "vad",
    "VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S": "4.0",
    "VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S": "9.0",
    "VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S": "3.0",
    "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS": "5",
    "VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S": "off",
    "VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION": "false",
    "VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S": "2.0",
    "VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S": "0.1",
    "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD": "0.9",
    "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS": "900",
    "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS": "9000",
    "VIVENTIUM_STT_VAD_MIN_SPEECH": "0.9",
    "VIVENTIUM_STT_VAD_MIN_SILENCE": "0.9",
    "VIVENTIUM_STT_VAD_ACTIVATION": "0.9",
    "VIVENTIUM_STT_VAD_MAX_BUFFERED_SPEECH": "5",
    "VIVENTIUM_STT_VAD_FORCE_CPU": "true",
}


@pytest.mark.parametrize("provider", ["pywhispercpp", "whisper_local", "openai"])
def test_local_whisper_and_openai_listening_use_the_local_turn_model_pinned_to_v1_mini(provider):
    # Pinned: neither dev mode nor a LiveKit Cloud marker may move the decision to a hosted model.
    with patch.dict(os.environ, {"LIVEKIT_DEV_MODE": "1", "LIVEKIT_REMOTE_EOT_URL": "https://eot.example.test",
                                 "LIVEKIT_API_KEY": "synthetic", "LIVEKIT_API_SECRET": "synthetic"}, clear=True):
        turn_handling = build_turn_handling(provider)
        unpinned = inference.TurnDetector()

    detector = turn_handling["turn_detection"]
    assert isinstance(detector, inference.TurnDetector)
    assert detector.model == "turn-detector-v1-mini"
    assert detector._cloud_opts is None
    # What the pin protects against: left to itself the SDK would have picked its hosted model.
    assert unpinned.model == "turn-detector-v1"
    # Whisper and OpenAI deliver text only after the utterance: the turn waits for it.
    assert turn_handling["endpointing"]["min_delay"] == 1.0


def test_assemblyai_listening_uses_its_own_end_of_turn_with_no_minimum_wait():
    turn_handling = build_turn_handling("assemblyai")

    assert turn_handling["turn_detection"] == "stt"
    assert turn_handling["endpointing"]["min_delay"] == 0.0


def test_assemblyai_alone_decides_the_end_of_turn_so_it_keeps_one_second_for_unfinished_sentences():
    # With "stt" nothing arbitrates after the provider. The 1.8.11 plugin, given no value, sends its
    # Universal-3 engines max_turn_silence = min_turn_silence = 100 ms (meant for use with
    # LiveKit's turn model): every short pause would end the turn.
    from livekit.plugins.assemblyai import stt as assemblyai_stt

    with patch.dict(os.environ, {**REMOVED_ENVIRONMENT, "VIVENTIUM_STT_PROVIDER": "assemblyai"}, clear=True):
        kwargs = worker._build_assemblyai_stt_kwargs(load_env())
    assert kwargs == {"speaker_labels": True, "model": "u3-rt-pro", "max_turn_silence": 1000}

    listener = assemblyai_stt.STT(api_key="synthetic", **kwargs)
    assert listener._opts.max_turn_silence == 1000
    assert listener._opts.min_turn_silence == 100
    plugin_alone = assemblyai_stt.STT(api_key="synthetic", model="u3-rt-pro", speaker_labels=True)
    assert plugin_alone._opts.max_turn_silence is NOT_GIVEN  # sent as 100 ms for this engine


@pytest.mark.parametrize("provider", ["pywhispercpp", "openai", "assemblyai"])
def test_barge_in_is_voice_activity_and_replies_are_never_started_early(provider):
    turn_handling = build_turn_handling(provider)

    assert turn_handling["interruption"] == {"mode": "vad"}
    assert turn_handling["preemptive_generation"] == {"enabled": False}
    assert turn_handling["endpointing"]["max_delay"] == 1.5
    assert set(turn_handling) == {"turn_detection", "endpointing", "interruption", "preemptive_generation"}


@pytest.mark.parametrize("provider", ["pywhispercpp", "assemblyai"])
def test_session_takes_the_recipe_and_does_not_forward_chat_context_to_the_listener(provider):
    async def run():
        turn_handling = build_turn_handling(provider)
        session = build_agent_session(vad=None, stt_impl=None, llm_impl=None, tts_impl=None,
                                      turn_handling=turn_handling)
        return turn_handling, session

    turn_handling, session = asyncio.run(run())
    assert isinstance(session, AgentSession)
    options = session.options
    # Her replies are not sent to the listening provider; key terms are unaffected.
    assert options.stt_context_options["forward_chat_context"] is False
    assert options.turn_handling["turn_detection"] is turn_handling["turn_detection"]
    assert options.interruption["mode"] == "vad"
    assert options.preemptive_generation["enabled"] is False
    assert options.endpointing["max_delay"] == 1.5
    assert options.endpointing["min_delay"] == (0.0 if provider == "assemblyai" else 1.0)
    # The numbers the gateway used to set are now whatever the SDK ships.
    assert options.interruption["resume_false_interruption"] is True
    assert options.min_consecutive_speech_delay == 0.0
    assert list(options.tts_text_transforms) == ["filter_emoji"]


def test_removed_end_of_speech_variables_change_nothing():
    with patch.dict(os.environ, {}, clear=True):
        plain = load_env()
    with patch.dict(os.environ, REMOVED_ENVIRONMENT, clear=True):
        configured = load_env()
        with patch("worker.silero_vad.VAD.load", return_value="stock-vad") as vad_load:
            vad = load_vad(configured)
        turn_handling = build_turn_handling(configured.stt_provider)

    assert configured == plain
    fields = {field.name for field in dataclasses.fields(configured)}
    assert not {name for name in fields if name.startswith(("voice_turn", "voice_min_", "voice_max_endpoint",
                                                              "voice_false_", "voice_resume_", "voice_aec_",
                                                              "voice_configured_", "voice_requested_turn"))}
    assert not {name for name in fields if "end_of_turn" in name or "turn_silence" in name}
    # Stock Silero sensitivity with the retained whole-utterance buffer guard.
    assert vad == "stock-vad"
    vad_load.assert_called_once_with(max_buffered_speech=600.0)
    assert turn_handling["interruption"] == {"mode": "vad"}
    assert turn_handling["endpointing"] == {"min_delay": 1.0, "max_delay": 1.5}


def _xai_env(**overrides):
    with patch.dict(os.environ, {"VIVENTIUM_TTS_PROVIDER": "xai", **overrides}, clear=True):
        return load_env()


def test_xai_voice_is_the_plugin_class_with_latency_option_and_space_keeping_tokenizer():
    env = _xai_env()
    with patch.object(xai_plugin.tts, "XAI_WEBSOCKET_URL", xai_plugin.tts.XAI_WEBSOCKET_URL), \
         patch.object(xai_plugin.tts, "SAMPLE_RATE", xai_plugin.tts.SAMPLE_RATE):
        voice = build_xai_tts(env, "synthetic-key")

    # The plugin's own class: no subclass, no patched connection method.
    assert type(voice) is xai_plugin.TTS
    assert "_connect_ws" not in vars(voice)
    assert env.xai_tts_optimize_streaming_latency == 1
    assert voice._opts.optimize_streaming_latency == 1
    assert voice._opts.voice == env.xai_voice and voice._opts.language == env.xai_language
    tokenizer = voice._opts.tokenizer
    assert type(tokenizer) is type(_build_xai_tts_word_tokenizer())
    text = "Night, friend. Ha. Which one?"
    assert "".join(tokenizer.tokenize(text)) == text


def test_xai_latency_option_off_is_left_to_the_plugin_default():
    env = _xai_env(VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY="0")
    with patch.object(xai_plugin.tts, "XAI_WEBSOCKET_URL", xai_plugin.tts.XAI_WEBSOCKET_URL), \
         patch.object(xai_plugin.tts, "SAMPLE_RATE", xai_plugin.tts.SAMPLE_RATE):
        voice = build_xai_tts(env, "synthetic-key")

    assert voice._opts.optimize_streaming_latency is NOT_GIVEN


def test_xai_plugin_connects_to_the_configured_endpoint_with_the_latency_option():
    # What the removed _connect_ws monkeypatch used to guarantee, now done by the 1.8.11 plugin.
    connected = {}

    class Http:
        async def ws_connect(self, url, headers):
            connected.update(url=url, headers=headers)
            return "socket"

    async def run():
        env = _xai_env(VIVENTIUM_XAI_TTS_WS_URL="wss://xai-tts.example.test/v1/tts",
                       VIVENTIUM_XAI_SAMPLE_RATE="44100", VIVENTIUM_XAI_VOICE="Eve")
        with patch.object(xai_plugin.tts, "XAI_WEBSOCKET_URL", xai_plugin.tts.XAI_WEBSOCKET_URL), \
             patch.object(xai_plugin.tts, "SAMPLE_RATE", xai_plugin.tts.SAMPLE_RATE):
            voice = build_xai_tts(env, "synthetic-key")
            voice._session = Http()
            socket = await voice._connect_pooled_ws(1.0)
            return voice.sample_rate, socket

    sample_rate, socket = asyncio.run(run())
    assert socket == "socket"
    assert sample_rate == 44100
    assert connected["url"].startswith("wss://xai-tts.example.test/v1/tts?")
    for part in ("voice=Eve", "language=en", "codec=pcm", "sample_rate=44100", "optimize_streaming_latency=1"):
        assert part in connected["url"]
    assert connected["headers"] == {"Authorization": "Bearer synthetic-key"}


def test_stock_vad_is_loaded_without_arguments_and_absence_is_not_fatal():
    with patch("worker.silero_vad.VAD.load", return_value="stock-vad") as vad_load:
        assert load_vad(SimpleNamespace(stt_provider="pywhispercpp")) == "stock-vad"
    vad_load.assert_called_once_with(max_buffered_speech=600.0)
    with patch("worker.HAS_SILERO", False):
        assert load_vad() is None
    assert not hasattr(worker, "_silero_vad_kwargs_for_env")
    assert not hasattr(worker, "load_turn_detection")
