"""Real local adapter readiness through process, claimed-call and streaming fallback seams."""

import asyncio
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from livekit.agents import APIConnectOptions
from livekit.agents.tts import SynthesizeStream, TTS, TTSCapabilities

import mlx_chatterbox_tts as mlx
import worker
from fallback_tts import FallbackTTS, ProviderAttempt
from librechat_llm import LibreChatAuth


LOCAL = "local_chatterbox_turbo_mlx_8bit"


def _env(primary=LOCAL, fallback="", *, prewarm=True):
    return SimpleNamespace(
        stt_provider="openai", tts_provider=primary, tts_provider_fallback=fallback,
        voice_prewarm_local_tts=prewarm, mlx_audio_model_id="synthetic-model",
        librechat_origin="http://synthetic-backend",
    )


def _auth():
    return LibreChatAuth(call_session_id="synthetic-call", call_secret="synthetic-secret",
                         job_id="synthetic-job", worker_id="synthetic-worker")


@pytest.mark.parametrize("primary,fallback,required", [
    (LOCAL, "", True), (LOCAL, LOCAL, True),
    (LOCAL, "openai", False), ("openai", LOCAL, False),
])
def test_actual_process_prewarm_failure_never_caches_a_failed_adapter(primary, fallback, required):
    proc = SimpleNamespace(userdata={})
    with (
        patch("worker.load_env", return_value=_env(primary, fallback)),
        patch("worker.load_vad", return_value=None),
        patch("worker._build_local_chatterbox_config",
              return_value=(mlx.MlxChatterboxConfig(model_id="synthetic-model"), None)),
        patch("mlx_chatterbox_tts._load_mlx_model", side_effect=RuntimeError("synthetic model unavailable")) as loader,
    ):
        if required:
            with pytest.raises(RuntimeError, match="worker will not register"):
                worker.prewarm_process(proc)
        else:
            worker.prewarm_process(proc)
    assert loader.call_count == 1
    assert "prewarmed_local_chatterbox_tts" not in proc.userdata


def test_actual_process_prewarm_success_caches_only_the_successful_adapter():
    proc = SimpleNamespace(userdata={})
    with (
        patch("worker.load_env", return_value=_env()),
        patch("worker.load_vad", return_value=None),
        patch("worker._build_local_chatterbox_config",
              return_value=(mlx.MlxChatterboxConfig(model_id="synthetic-model"), None)),
        patch("mlx_chatterbox_tts._load_mlx_model", return_value=object()) as loader,
    ):
        worker.prewarm_process(proc)
    assert loader.call_count == 1
    assert isinstance(proc.userdata["prewarmed_local_chatterbox_tts"], mlx.MlxChatterboxTTS)


class _HealthyStream(SynthesizeStream):
    async def _run(self, emitter):
        emitter.initialize(request_id="synthetic-fallback", sample_rate=24000, num_channels=1,
                           mime_type="audio/pcm", frame_size_ms=200, stream=True)
        emitter.start_segment(segment_id="synthetic-segment")
        async for text in self._input_ch:
            if isinstance(text, str):
                self._tts.input_chunks.append(text)
        self._tts.pcm_produced = True
        emitter.push(b"\x01\x00" * 4800)


class _HealthyNativeTTS(TTS):
    def __init__(self):
        super().__init__(capabilities=TTSCapabilities(streaming=True), sample_rate=24000, num_channels=1)
        self.input_chunks = []
        self.pcm_produced = False

    @property
    def provider(self):
        return "local_synthetic_alternative"

    @property
    def model(self):
        return "synthetic-model"

    def stream(self, *, conn_options):
        return _HealthyStream(tts=self, conn_options=conn_options)

    def synthesize(self, text, *, conn_options):
        raise NotImplementedError("This fixture exercises the native streaming route.")


def test_failed_actual_local_prewarm_preserves_streaming_configured_fallback_and_audible_selection():
    asyncio.run(_failed_actual_local_prewarm_preserves_streaming_configured_fallback_and_audible_selection())


async def _failed_actual_local_prewarm_preserves_streaming_configured_fallback_and_audible_selection():
    primary = mlx.MlxChatterboxTTS(config=mlx.MlxChatterboxConfig(model_id="synthetic-model"))
    fallback = _HealthyNativeTTS()
    # The call passes only constructed, already-authorized attempts into this seam.
    # A synthetic local alternative exercises fallback without changing the product's
    # local/cloud egress gate or pretending a new local provider is shipped.
    attempts = [ProviderAttempt(label=LOCAL, tts=primary),
                ProviderAttempt(label="local_synthetic_alternative", tts=fallback)]
    selected = []
    attempted = []
    fatal = AsyncMock()
    report = AsyncMock(return_value={"status": "degraded"})
    def on_selected(provider, tts):
        assert tts is fallback and fallback.pcm_produced
        selected.append(provider)
    with (
        patch("mlx_chatterbox_tts._load_mlx_model", side_effect=RuntimeError("synthetic model unavailable")),
        patch("worker._report_voice_gateway_failure", report),
    ):
        ready = await worker._prewarm_call_local_tts(
            env=_env(fallback="local_synthetic_alternative"), auth=_auth(), primary_tts_impl=primary,
            primary_voice_provider=LOCAL, prewarmed_local_tts=None, attempts=attempts,
            fail_initialization=fatal,
        )
        assert ready is False
        with patch.dict(worker.os.environ, {}, clear=True):
            env = replace(worker.load_env(), tts_provider=LOCAL, tts_provider_fallback="openai")
        facts = worker._build_current_call_runtime_context(
            env, "synthetic-call", turn_detection="stt", primary_tts_ready=ready,
        )
        assert facts["readyRoute"]["tts"] == {"provider": None, "variant": None}
        assert facts["configuredTtsFallback"] == "openai"
        assert env.tts_provider == LOCAL
        assert selected == []
        fatal.assert_not_awaited()
        assert report.await_args.kwargs == dict(classification="provider_failure", modality="tts",
                                                provider=LOCAL, phase="initialization", fatal=False)
        wrapper = FallbackTTS(attempts=attempts, on_provider_selected=on_selected,
                              on_provider_attempt=attempted.append)
        stream = wrapper.stream(conn_options=APIConnectOptions(max_retry=0))
        stream.push_text("A useful fallback reply.")
        stream.end_input()
        frames = [event.frame async for event in stream]
        await stream.aclose()
    assert frames and sum(len(frame.data) for frame in frames) > 0
    assert selected == ["local_synthetic_alternative"]
    assert attempted[0] is primary and attempted[-1] is fallback
    assert all(item is primary for item in attempted[:-1])
    assert "".join(fallback.input_chunks) == "A useful fallback reply."
    assert attempts[0].tts is primary  # Configured primary is not silently remapped.


def test_actual_local_prewarm_without_constructed_fallback_reports_then_releases_claim():
    asyncio.run(_actual_local_prewarm_without_constructed_fallback_reports_then_releases_claim())


async def _actual_local_prewarm_without_constructed_fallback_reports_then_releases_claim():
    primary = mlx.MlxChatterboxTTS(config=mlx.MlxChatterboxConfig(model_id="synthetic-model"))
    operations = []
    async def report(*args, **kwargs):
        operations.append(("failure", kwargs))
        return {"status": "failed"}
    async def abandon(*args, **kwargs):
        operations.append(("abandon", kwargs))
        return True
    async def fatal(error):
        await worker._report_voice_initialization_failure_and_abandon("http://synthetic-backend", _auth(), error)
    with (
        patch("mlx_chatterbox_tts._load_mlx_model", side_effect=RuntimeError("synthetic model unavailable")),
        patch("worker._report_voice_gateway_failure", side_effect=report),
        patch("worker._abandon_voice_session_claim", side_effect=abandon),
    ):
        # A configured string filtered by egress policy or whose constructor failed
        # must not count as an actual attempt.
        with pytest.raises(worker.VoiceRouteError, match="prewarm failed"):
            await worker._prewarm_call_local_tts(
                env=_env(fallback="openai"), auth=_auth(), primary_tts_impl=primary,
                primary_voice_provider=LOCAL, prewarmed_local_tts=None,
                attempts=[ProviderAttempt(label=LOCAL, tts=primary)], fail_initialization=fatal,
            )
    assert [item[0] for item in operations] == ["failure", "abandon"]
    assert operations[0][1]["fatal"] is True
    assert operations[0][1]["provider"] == LOCAL
    assert operations[1][1]["reason"] == "gateway_initialization_failed"


@pytest.mark.parametrize("cached,opt_out", [(True, False), (False, True)])
def test_existing_cache_reuse_and_explicit_prewarm_opt_out_avoid_a_second_load(cached, opt_out):
    asyncio.run(_existing_cache_reuse_and_explicit_prewarm_opt_out_avoid_a_second_load(cached, opt_out))


async def _existing_cache_reuse_and_explicit_prewarm_opt_out_avoid_a_second_load(cached, opt_out):
    primary = mlx.MlxChatterboxTTS(config=mlx.MlxChatterboxConfig(model_id="synthetic-model"))
    with patch("mlx_chatterbox_tts._load_mlx_model") as loader:
        ready = await worker._prewarm_call_local_tts(
            env=_env(prewarm=not opt_out), auth=_auth(), primary_tts_impl=primary,
            primary_voice_provider=LOCAL, prewarmed_local_tts=primary if cached else None,
            attempts=[ProviderAttempt(label=LOCAL, tts=primary)], fail_initialization=AsyncMock(),
        )
    loader.assert_not_called()
    assert ready is True
