"""Native streaming text uses safe words without an extra phrase-length gate."""

import asyncio
import ast
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pathlib import Path

import aiohttp
import pytest
from livekit.agents import tts
from livekit.agents import APIError
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import xai

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from librechat_llm import LibreChatAuth, LibreChatLLM, _VoiceTtsDeltaBuffer
from sse import safe_voice_tts_prefix_end, sanitize_voice_tts_text, strip_voice_control_tags
from worker import _build_xai_tts_word_tokenizer, _tts_uses_native_streaming
import worker
from test_librechat_llm import _FakeStreamingSseSession
from fallback_tts import FallbackTTS, ProviderAttempt
from test_fallback_tts import FakeTTS, FakeStreamingTTS


def _buffer(*, native=True, controls=False):
    return _VoiceTtsDeltaBuffer(
        native_streaming=lambda: native,
        sanitize_chunk=lambda text: sanitize_voice_tts_text(
            text,
            preserve_leading_space=text[:1].isspace(),
            preserve_trailing_space=text[-1:].isspace(),
            allow_voice_controls=controls,
        ),
    )


@pytest.mark.parametrize("chunks,first", [
    (["I", " hear"], "I "),
    (["Hell", "o there"], "Hello "),
    (["Good", " morning"], "Good "),
])
def test_native_word_prefix_emits_before_phrase_completion(chunks, first):
    buffer = _buffer()
    assert buffer.feed(chunks[0]) == []
    assert buffer.feed(chunks[1]) == [first]
    assert first + "".join(buffer.finalize()) == "".join(chunks)


def test_native_keeps_the_last_word_for_delayed_punctuation():
    buffer = _buffer()
    assert buffer.feed("Hello ") == []
    assert buffer.feed("there ") == ["Hello "]
    assert buffer.feed("?") == ["there?"]
    assert buffer.finalize() == []


def test_legacy_and_unknown_capability_keep_phrase_policy():
    for buffer in (_buffer(native=False), _VoiceTtsDeltaBuffer()):
        assert buffer.feed("I") == []
        assert buffer.feed(" hear") == []
        assert buffer.feed(" you.") == ["I hear you."]


def test_actual_selected_capability_can_change_without_new_buffer():
    selected = {"native": True}
    buffer = _VoiceTtsDeltaBuffer(native_streaming=lambda: selected["native"])
    assert buffer.feed("I hear") == ["I "]
    selected["native"] = False
    assert buffer.feed(" you") == []
    assert buffer.feed(".") == ["hear you."]


@pytest.mark.parametrize("value,expected", [(True, True), (False, False), (None, False), ("true", False), (1, False)])
def test_native_capability_reads_typed_actual_renderer(value, expected):
    assert _tts_uses_native_streaming(SimpleNamespace(
        capabilities=SimpleNamespace(streaming=value))) is expected
    assert _tts_uses_native_streaming(SimpleNamespace()) is False


def test_provider_setter_preserves_legacy_signature_and_updates_native_capability():
    llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
        call_session_id="synthetic-call", call_secret="synthetic-secret"))
    assert llm._voice_native_streaming is False
    llm.set_voice_provider("synthetic", native_streaming=True)
    assert llm._voice_native_streaming is True
    llm.set_voice_provider("synthetic")
    assert llm._voice_native_streaming is True
    llm.set_voice_provider("synthetic", native_streaming=False)
    assert llm._voice_native_streaming is False


def test_real_worker_initial_and_selected_callback_use_the_unwrapped_renderer():
    tree = ast.parse(Path(worker.__file__).read_text())
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == "_handle_provider_selected")
    initial = next(node for node in ast.walk(tree) if isinstance(node, ast.Expr)
                   and isinstance(node.value, ast.Call)
                   and isinstance(node.value.func, ast.Attribute)
                   and node.value.func.attr == "set_voice_provider"
                   and isinstance(node.value.args[0], ast.Name)
                   and node.value.args[0].id == "primary_voice_provider")
    # Execute the actual small wiring seam; no job, room, provider or network is started.
    factory = ast.parse("def make(llm_impl, capabilities):\n"
                        "    current_tts_provider = current_tts_impl = None\n").body[0]
    factory.body.extend([callback, ast.Return(value=ast.Name(
        id="_handle_provider_selected", ctx=ast.Load()))])
    namespace = dict(worker.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                 "<worker-selected-tts-seam>", "exec"), namespace)
    llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
        call_session_id="synthetic-call", call_secret="synthetic-secret"))
    capabilities = []
    direct = SimpleNamespace(capabilities=SimpleNamespace(streaming=True))
    namespace.update(llm_impl=llm, capabilities=capabilities,
                     primary_voice_provider="synthetic", primary_tts_impl=direct)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[initial], type_ignores=[])),
                 "<worker-initial-tts-seam>", "exec"), namespace)
    assert llm._voice_native_streaming is True
    selected = namespace["make"](llm, capabilities)
    selected("synthetic-fallback", SimpleNamespace(
        capabilities=SimpleNamespace(streaming=False)))
    assert llm._voice_native_streaming is False
    selected("synthetic-native", direct)
    assert llm._voice_native_streaming is True


def test_worker_attempt_capability_changes_only_input_policy():
    tree = ast.parse(Path(worker.__file__).read_text())
    callback = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == "_handle_provider_attempt")
    wrapper_call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "FallbackTTS")
    assert any(keyword.arg == "on_provider_attempt"
               and isinstance(keyword.value, ast.Name)
               and keyword.value.id == callback.name for keyword in wrapper_call.keywords)
    llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
        call_session_id="synthetic-call", call_secret="synthetic-secret"))
    llm.set_voice_provider("audible-renderer", accepts_inline_voice_controls=True)
    namespace = dict(worker.__dict__, llm_impl=llm)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
                 "<worker-attempt-tts-seam>", "exec"), namespace)
    attempt = namespace[callback.name]
    attempt(SimpleNamespace(capabilities=SimpleNamespace(streaming=True)))
    assert llm._voice_native_streaming is True
    attempt(SimpleNamespace(capabilities=SimpleNamespace(streaming=False)))
    assert llm._voice_native_streaming is False
    assert llm._voice_provider == "audible-renderer"
    assert llm._voice_accepts_inline_controls is True


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_native", [True, False])
async def test_current_attempt_capability_resets_before_repeated_stream_input(primary_native):
    primary_type = FakeStreamingTTS if primary_native else FakeTTS
    fallback_type = FakeTTS if primary_native else FakeStreamingTTS
    primary = primary_type(sample_rate=44100, should_fail=True)
    fallback = fallback_type(sample_rate=44100)
    llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
        call_session_id="synthetic-call", call_secret="synthetic-secret"))
    selected = []
    wrapper = FallbackTTS(
        attempts=[ProviderAttempt(label="primary", tts=primary),
                  ProviderAttempt(label="fallback", tts=fallback)],
        on_provider_attempt=lambda raw: llm.set_voice_native_streaming(
            _tts_uses_native_streaming(raw)),
        on_provider_selected=lambda label, raw: selected.append(label),
    )
    stream = wrapper.stream()
    stream.push_text("Synthetic sentence.")
    stream.end_input()
    async with stream:
        async for _ in stream:
            pass
    assert llm._voice_native_streaming is not primary_native
    assert selected == ["fallback"]
    # The live buffer reads the flag at each feed, even if constructed before stream creation.
    buffer = _VoiceTtsDeltaBuffer(native_streaming=lambda: llm._voice_native_streaming)
    next_stream = wrapper.stream()
    assert llm._voice_native_streaming is primary_native
    assert buffer.feed("I hear") == (["I "] if primary_native else [])
    assert selected == ["fallback"]  # No new audible provider is claimed by the reset.
    await next_stream.aclose()


class _ImmediateFailureStream(tts.SynthesizeStream):
    async def _run(self, output_emitter):
        raise APIError("synthetic pre-audio failure", retryable=False)


class _ImmediateFailureTTS(FakeStreamingTTS):
    def stream(self, *, conn_options):
        return _ImmediateFailureStream(tts=self, conn_options=conn_options)


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_native", [True, False])
async def test_current_attempt_capability_changes_before_fallback_audio(fallback_native):
    primary = _ImmediateFailureTTS(sample_rate=44100)
    fallback_type = FakeStreamingTTS if fallback_native else FakeTTS
    fallback = fallback_type(sample_rate=44100)
    llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
        call_session_id="synthetic-call", call_secret="synthetic-secret"))
    reached_fallback = asyncio.Event()
    selected = []

    def attempt(raw):
        llm.set_voice_native_streaming(_tts_uses_native_streaming(raw))
        if raw is fallback:
            reached_fallback.set()

    wrapper = FallbackTTS(
        attempts=[ProviderAttempt(label="primary", tts=primary),
                  ProviderAttempt(label="fallback", tts=fallback)],
        on_provider_attempt=attempt,
        on_provider_selected=lambda label, raw: selected.append(label),
    )
    buffer = _VoiceTtsDeltaBuffer(native_streaming=lambda: llm._voice_native_streaming)
    stream = wrapper.stream()
    try:
        await asyncio.wait_for(reached_fallback.wait(), timeout=1)
        assert selected == []
        assert llm._voice_native_streaming is fallback_native
        assert buffer.feed("I hear") == (["I "] if fallback_native else [])
        stream.push_text("Synthetic sentence.")
        stream.end_input()
        async with stream:
            async for _ in stream:
                pass
        assert selected == ["fallback"]
    finally:
        await stream.aclose()


@pytest.mark.parametrize("chunks,expected", [
    (["Emotion", "al", " pain."], "Emotional pain."),
    (["3", ".", "14 is", " pi."], "3.14 is pi."),
    (["Version 2", ".", "10 is", " ready."], "Version 2.10 is ready."),
    (["Active count is ", "7. ", "Urgent attention", ": two need input."],
     "Active count is 7. Urgent attention: two need input."),
    (["She asked, “Sleep okay ", "?”"], "She asked, “Sleep okay?”"),
    (["Good morning. Sleep okay ", "?"], "Good morning. Sleep okay?"),
    (["Right. That landed ", "!"], "Right. That landed!"),
    (["Visit https://example.", "com now."], "Visit link available now."),
    (["Email qa@", "example.com now."], "Email address available now."),
    (["See [the ", "brief](https://example.com)", " now."], "See the brief now."),
    (["**Hello ", "there**", " friend."], "Hello there friend."),
    (["*Hello ", "there*", " friend."], "Hello there friend."),
    (["Read `private", "_code`", " instead."], "Read private_code instead."),
    (["Before ```private", " code```", " after."], "Before after."),
    (["2 * 3 is ", "6."], "2 * 3 is 6."),
    (["你好", "世界"], "你好世界"),
])
def test_native_structural_and_numeric_tail_is_complete(chunks, expected):
    buffer = _buffer()
    emitted = []
    for chunk in chunks:
        emitted.extend(buffer.feed(chunk))
    emitted.extend(buffer.finalize())
    assert "".join(emitted) == expected
    assert not any(_VoiceTtsDeltaBuffer._is_orphan_punctuation(chunk) for chunk in emitted)


@pytest.mark.parametrize("text,prefix", [
    ("Hello <whis", "Hello "),
    ("Hello [long-", "Hello "),
    ("Hello **bold ", "Hello "),
    ("**complete** then _pending", "**complete** then "),
    ("2 * 3 is 6", "2 * 3 is 6"),
    ("value_name is complete", "value_name is complete"),
])
def test_shared_structural_prefix_holds_only_unfinished_tokens(text, prefix):
    assert text[:safe_voice_tts_prefix_end(text)] == prefix


@pytest.mark.parametrize("controls", [False, True])
def test_native_emotional_tokens_preserve_order_and_plain_route_strips_them(controls):
    text = "[sigh]<whisper>Hello there.</whisper> Next thought."
    buffer = _buffer(controls=controls)
    emitted = []
    for chunk in ("[si", "gh]<whis", "per>Hello ", "there.</whisper>", " Next thought."):
        emitted.extend(buffer.feed(chunk))
    emitted.extend(buffer.finalize())
    assert "".join(emitted) == (text if controls else "Hello there. Next thought.")
    assert all(not chunk.rstrip().endswith(("<whis", "[si")) for chunk in emitted)


@pytest.mark.parametrize("text,expected", [
    ("[sigh]<whisper>Hello there.</whisper>", "Hello there."),
    ('[sigh]<emotion value="calm">Hello there.</emotion>', "Hello there."),
    ("<whisper>[sigh]</whisper>Hello there.", "Hello there."),
    ("[JSON]<whisper>Hello</whisper>", "[JSON]Hello"),
    ("[7]<whisper>Hello</whisper>", "[7]Hello"),
    ("[note]literal", "[note]literal"),
    ("2 * 3 is 6. [1, 2]", "2 * 3 is 6. [1, 2]"),
])
def test_adjacent_wrapper_stripping_preserves_literal_bracket_controls(text, expected):
    assert strip_voice_control_tags(text) == expected


def test_native_candidate_checks_are_bounded_on_a_large_single_delta():
    buffer = _buffer()
    text = "**" + "word " * 2000
    with patch("librechat_llm.safe_voice_tts_prefix_end", wraps=safe_voice_tts_prefix_end) as guard:
        assert buffer.feed(text) == []
    assert guard.call_count <= 50


@pytest.mark.parametrize("text,audio,supersede", [
    ("{NTA}", "eligible", False),
    ("Hello there.", "skip", False),
    ("Hello there.", "eligible", True),
])
def test_native_capability_does_not_bypass_silence_disposition_or_supersession(text, audio, supersede):
    async def run():
        metadata = {"viventium": {"deliveryDisposition": {
            "version": 1, "audio": audio, "source": "model", "valid": True,
            "required": True,
        }}}
        events = [{"event": "on_message_delta", "data": {"delta": {
            "content": [{"type": "text", "text": text}], "metadata": metadata,
        }}}, {"final": True, "responseMessage": {
            "content": [{"type": "text", "text": text}], "metadata": metadata,
        }}]
        fake = _FakeStreamingSseSession(events)
        llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
            call_session_id="synthetic-call", call_secret="synthetic-secret"),
            voice_native_streaming=True)
        content = []
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
            async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                role="user", content=["Synthetic request"])])) as stream:
                if supersede:
                    llm._presentation_coordinator.begin_stable(
                        source_event_id="synthetic-new-input", presentation_ref="next-speech")
                async for chunk in stream:
                    if chunk.delta and chunk.delta.content:
                        content.append(chunk.delta.content)
        assert content == []
    asyncio.run(run())


def test_native_stream_releases_chat_chunk_before_final_event():
    async def run():
        release = asyncio.Event()
        content = []
        final_seen = False

        class GatedContent:
            async def iter_any(self):
                nonlocal final_seen
                first = {"event": "on_message_delta", "data": {"delta": {
                    "content": [{"type": "text", "text": "Hello there"}]}}}
                yield f"data: {json.dumps(first)}\n\n".encode()
                await release.wait()
                for event in (
                    {"event": "on_message_delta", "data": {"delta": {
                        "content": [{"type": "text", "text": "."}]}}},
                    {"final": True, "responseMessage": {"content": [
                        {"type": "text", "text": "Hello there."}]}},
                ):
                    final_seen = final_seen or event.get("final") is True
                    yield f"data: {json.dumps(event)}\n\n".encode()

        fake = _FakeStreamingSseSession([])
        original_get = fake.get
        def get(*args, **kwargs):
            response = original_get(*args, **kwargs)
            response.content = GatedContent()
            return response
        fake.get = get
        llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
            call_session_id="synthetic-call", call_secret="synthetic-secret"),
            voice_native_streaming=True)
        with patch("librechat_llm.aiohttp.ClientSession", return_value=fake):
            async with llm.chat(chat_ctx=ChatContext(items=[ChatMessage(
                role="user", content=["Synthetic request"])])) as stream:
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=1)
                    assert not final_seen
                    content.append(chunk.delta.content)
                finally:
                    release.set()
                async for chunk in stream:
                    if chunk.delta and chunk.delta.content:
                        content.append(chunk.delta.content)
        assert final_seen
        assert content[0] == "Hello there"
        assert "".join(content) == "Hello there."
    asyncio.run(run())


def test_agent_tts_node_releases_safe_words_before_input_completion():
    async def run():
        release = asyncio.Event()
        input_complete = False
        seen = []

        async def source():
            nonlocal input_complete
            yield "Hello there"
            await release.wait()
            yield "."
            input_complete = True

        async def default_node(agent, text, settings):
            async for value in text:
                seen.append(value)
                yield value

        llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
            call_session_id="synthetic-call", call_secret="synthetic-secret"),
            voice_native_streaming=True)
        agent = worker.ViventiumVoiceAgent(instructions="Synthetic", llm=llm)
        with patch.object(worker.Agent.default, "tts_node", default_node):
            audio = agent.tts_node(source(), None)
            try:
                assert await asyncio.wait_for(anext(audio), 1) == "Hello "
                assert not input_complete
                release.set()
                async for _ in audio:
                    pass
            finally:
                release.set()
                await audio.aclose()
        assert "".join(seen) == "Hello there."

    asyncio.run(run())

def test_public_links_survive_display_while_only_tts_projects_speech():
    async def run():
        chunks = ['[sigh]<emotion value="calm">Read [the ',
                  'report](https://example.invalid/report?revision=2&view=owner)',
                  ' and https://example.invalid/source.</emotion>']
        raw = "".join(chunks)
        spoken = []

        async def source():
            for value in chunks:
                yield value

        async def default_node(agent, text, settings):
            async for value in text:
                spoken.append(value)
                yield value

        llm = LibreChatLLM(origin="http://core.test", auth=LibreChatAuth(
            call_session_id="synthetic-call", call_secret="synthetic-secret"),
            voice_native_streaming=True)
        agent = worker.ViventiumVoiceAgent(instructions="Synthetic", llm=llm)
        displayed = "".join([value async for value in agent.transcription_node(source(), None)])
        assert '[the report](https://example.invalid/report?revision=2&view=owner)' in displayed
        assert 'https://example.invalid/source.' in displayed
        assert '[sigh]' not in displayed and '<emotion' not in displayed
        with patch.object(worker.Agent.default, "tts_node", default_node):
            async for _ in agent.tts_node(source(), None):
                pass
        assert "".join(spoken) == sanitize_voice_tts_text(raw)
        assert 'https://' not in "".join(spoken)

    asyncio.run(run())

def test_pinned_xai_pushes_share_one_segment_until_end_input():
    async def run():
        packets = []
        received = asyncio.Queue()
        first_write = asyncio.Event()
        emitter = SimpleNamespace(
            initialize=lambda **kwargs: None,
            start_segment=lambda **kwargs: segments.append(kwargs),
            end_segment=lambda: None,
            push=lambda data: None,
        )
        segments = []

        class Socket:
            async def send_str(self, text):
                packet = json.loads(text)
                packets.append(packet)
                if packet["type"] == "text.delta":
                    first_write.set()
                if packet["type"] == "text.done":
                    await received.put(SimpleNamespace(type=aiohttp.WSMsgType.TEXT,
                        data=json.dumps({"type": "audio.done"})))
            async def receive(self):
                return await received.get()

        async def main(stream):
            await stream._run(emitter)

        renderer = xai.TTS(api_key="synthetic", tokenizer=_build_xai_tts_word_tokenizer())
        with patch.object(renderer, "_connect_ws", AsyncMock(return_value=Socket())) as connect, \
             patch.object(renderer, "_close_ws", AsyncMock()) as close, \
             patch.object(tts.SynthesizeStream, "_main_task", main):
            async with renderer.stream() as stream:
                stream.push_text("Hel")
                await asyncio.sleep(0)
                assert not packets
                stream.push_text("lo ")
                await asyncio.wait_for(first_write.wait(), timeout=1)
                assert not any(packet["type"] == "text.done" for packet in packets)
                stream.push_text("there.")
                stream.end_input()
                await asyncio.wait_for(stream._task, timeout=1)
            assert connect.await_count == close.await_count == 1
        assert len(segments) == 1
        assert sum(packet["type"] == "text.done" for packet in packets) == 1
        assert "".join(packet["delta"] for packet in packets if packet["type"] == "text.delta") == "Hello there."
    asyncio.run(run())
