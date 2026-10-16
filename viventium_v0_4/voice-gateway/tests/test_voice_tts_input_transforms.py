"""Installed SDK text pipeline regressions; no synthesis or provider calls."""

import ast
import asyncio
from pathlib import Path

import pytest
from livekit.agents import ModelSettings
from livekit.agents.voice import generation
from livekit.agents.voice.agent_session import DEFAULT_TTS_TEXT_TRANSFORMS

from librechat_llm import _VoiceTtsDeltaBuffer
from sse import VoiceControlDisplayFilter, sanitize_voice_tts_text, sanitize_voice_followup_text


def _session_transforms():
    # Exercise the transforms supplied by the actual owning session constructor.
    tree = ast.parse((Path(__file__).parents[1] / "worker.py").read_text())
    call = next(node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "AgentSession")
    value = next((item.value for item in call.keywords
                  if item.arg == "tts_text_transforms"), None)
    return ast.literal_eval(value) if value is not None else DEFAULT_TTS_TEXT_TRANSFORMS


async def _render(chunks, *, native=True, hold_open=False):
    release, input_consumed = asyncio.Event(), asyncio.Event()
    output = []
    closed = False

    async def source():
        nonlocal closed
        for chunk in chunks:
            yield chunk
        input_consumed.set()
        await release.wait()
        closed = True

    async def owning_node(text, settings):
        buffer = _VoiceTtsDeltaBuffer(
            native_streaming=lambda: native,
            sanitize_chunk=lambda value: sanitize_voice_tts_text(
                value, preserve_leading_space=value[:1].isspace(),
                preserve_trailing_space=value[-1:].isspace(),
                allow_voice_controls=native),
        )
        async for delta in text:
            for value in buffer.feed(str(delta)):
                output.append((value, closed))
        for value in buffer.finalize():
            output.append((value, closed))
        if False:
            yield None

    task, _ = generation.perform_tts_inference(
        node=owning_node, input=source(), model_settings=ModelSettings(),
        text_transforms=_session_transforms(),
    )
    try:
        await asyncio.wait_for(input_consumed.wait(), 1)
        if hold_open:
            await asyncio.sleep(0.02)
        before = [text for text, after_close in output if not after_close]
    finally:
        release.set()
        await asyncio.wait_for(task, 1)
    return "".join(text for text, _ in output).strip(), before


def test_complete_voice_control_does_not_wait_for_llm_stream_end():
    text = "Keep one small step ready, [pause] then choose the useful part."
    speech, before = asyncio.run(_render([text], hold_open=True))
    assert before and before[0].startswith("Keep one small step")
    assert speech == text


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("text, expected", [
    ("Keep useful words.", "Keep useful words."),
    ("Read **carefully** and _keep_ ~~every~~ word.", "Read carefully and keep every word."),
    ("Open [the report](https://example.invalid/report) and continue.", "Open the report and continue."),
    ("See ![the diagram](https://example.invalid/image) then continue.", "See the diagram then continue."),
    ("Before. ```python\nprint('hidden')\n``` After.", "Before. After."),
    ("Before. ```python\nprint('hidden')", "Before."),
    ("Use ``literal `tick` **words**`` and continue.", "Use literal tick words and continue."),
    ("> Quote: **steady** words.\n- First point.\n- Second point.", "Quote: steady words. First point. Second point."),
    ("Hello 🙂 👨‍👩‍👧‍👦 world.", "Hello world."),
    ("The amount is 2.5. Keep it.", "The amount is 2.5. Keep it."),
])
def test_native_and_legacy_speech_keep_complete_markup(text, expected, native, character_chunks):
    chunks = list(text) if character_chunks else [text]
    speech, _ = asyncio.run(_render(chunks, native=native))
    assert speech == expected


@pytest.mark.parametrize("native", [True, False])
def test_inline_controls_follow_actual_renderer_capability(native):
    text = "[pause] Hello [soft] world."
    speech, _ = asyncio.run(_render(list(text), native=native))
    assert speech == (text if native else "Hello world.")


@pytest.mark.parametrize("text", [
    "Read ``literal `tick` **words** <custom>`` then finish.",
    "Open [the report](https://example.invalid/report) and continue.",
    "See ![the diagram](https://example.invalid/image) then continue.",
])
def test_shared_delimiter_guard_keeps_literal_display(text):
    display = VoiceControlDisplayFilter()
    actual = "".join(display.feed(char) for char in text) + display.feed("", final=True)
    assert actual == text


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("suffix", [
    "array[0 and more useful words", "x < y and more useful words", "`unfinished literal words",
])
def test_safe_words_before_ambiguous_markup_do_not_wait_for_input_end(native, suffix):
    prefix = "Useful ordinary words arrive before the unfinished expression. "
    speech, before = asyncio.run(_render([prefix + suffix], native=native, hold_open=True))
    assert before and "Useful ordinary words" in "".join(before)
    assert speech.startswith(prefix.strip())


@pytest.mark.parametrize("native", [True, False])
def test_lexically_impossible_angle_tag_is_not_held(native):
    text = "Useful ordinary words arrive before the expression x < y and more useful words."
    speech, before = asyncio.run(_render([text], native=native, hold_open=True))
    assert "x < y" in "".join(before)
    assert speech == text


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("text, expected", [
    ("Open [the report](https://example.invalid/a(b)/c) and continue.", "Open the report and continue."),
    ("See ![the diagram](https://example.invalid/a(b)/c) then continue.", "See the diagram then continue."),
    ("Open [one](https://example.invalid/a(b(c))/d)[two](https://example.invalid/second) now.", "Open onetwo now."),
    (r"Open [the report](https://example.invalid/a\(b\)/c) and continue.", "Open the report and continue."),
    ("Open [the\nreport](https://example.invalid/a(b)/c) and continue.", "Open the report and continue."),
])
def test_balanced_and_escaped_link_targets_remain_non_speech(text, expected, native, character_chunks):
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == expected


@pytest.mark.parametrize("native", [True, False])
def test_closed_link_label_waits_for_next_character(native):
    prefix = "Useful ordinary words arrive before the possible link. "
    _speech, before = asyncio.run(_render([prefix + "[the report]"], native=native, hold_open=True))
    assert before and "the report" not in "".join(before)


@pytest.mark.parametrize("text, expected", [
    ("One **clear** sentence with [the report](https://example.invalid/a(b)/c).\n- A useful point.",
     "One clear sentence with the report. A useful point."),
    ("A **useful** description with ![the diagram](https://example.invalid/a(b)/c).\n> A quoted point.",
     "A useful description with the diagram. A quoted point."),
])
def test_followup_uses_the_same_complete_markup_sanitizer(text, expected):
    assert sanitize_voice_followup_text(text) == expected


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("target", ["relative/report.txt", "/uploads/report.txt", "sandbox:/report.txt", "file:/report.txt"])
@pytest.mark.parametrize("image", [True, False])
def test_non_http_markdown_targets_are_not_spoken(native, character_chunks, target, image):
    text = f"Useful words. {'!' if image else ''}[the report]({target}) Then continue."
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == "Useful words. the report Then continue."


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
def test_voice_control_followed_by_parenthetical_words_is_not_a_markdown_link(native, character_chunks):
    text = "Useful words. [pause] (aside) Then continue."
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == (text if native else "Useful words. (aside) Then continue.")


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("target", ["relative/report.txt", "/uploads/report.txt", "sandbox:/report.txt", "file:/report.txt"])
@pytest.mark.parametrize("image", [True, False])
def test_unterminated_markdown_target_stays_non_speech_at_input_end(native, character_chunks, target, image):
    text = f"Useful words. {'!' if image else ''}[the report]({target}"
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == "Useful words. the report"


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("opening, closing, expected", [
    ("```python\n", "```", "Useful words. Then continue."),
    (" ```python\n", "```", {True: "Useful words. Then continue.", False: "Useful words.  Then continue."}),
    ("[pause] ```python\n", "```", None),
    ("`", "`", "Useful words. hidden body Then continue."),
    ("``", "``", "Useful words. hidden body Then continue."),
    ("[the report](relative/", ")", "Useful words. the report Then continue."),
    ("![the report](relative/", ")", "Useful words. the report Then continue."),
])
def test_pending_markup_span_reuses_classification_and_recovers_exactly(monkeypatch, native, opening, closing, expected):
    import librechat_llm
    original = librechat_llm.safe_voice_tts_prefix_end
    calls = []
    def classify(value):
        calls.append(len(value))
        return original(value)
    monkeypatch.setattr(librechat_llm, "safe_voice_tts_prefix_end", classify)
    buffer = _VoiceTtsDeltaBuffer(
        native_streaming=lambda: native,
        sanitize_chunk=lambda value: sanitize_voice_tts_text(
            value, preserve_leading_space=value[:1].isspace(),
            preserve_trailing_space=value[-1:].isspace(), allow_voice_controls=native),
    )
    output = buffer.feed("Useful words. ")
    output.extend(buffer.feed(opening))
    output.extend(buffer.feed("hidden body"))
    # The pending span remains opaque while ordinary target/code words arrive.
    before = len(calls)
    for _ in range(100):
        output.extend(buffer.feed(" "))
    assert len(calls) == before
    for character in closing:
        output.extend(buffer.feed(character))
    output.extend(buffer.feed(" Then continue."))
    output.extend(buffer.finalize())
    if expected is None:
        expected = "Useful words. [pause] Then continue." if native else "Useful words. Then continue."
    elif isinstance(expected, dict):
        # Retain the exact existing legacy chunk-boundary whitespace.
        expected = expected[native]
    assert "".join(output).strip() == expected
    # Finalization clears the local span; a subsequent ordinary feed still works.
    assert "Fresh words." in "".join(buffer.feed(" Fresh words.") + buffer.finalize())


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("chunks", ["whole", "characters", "newline_split"])
@pytest.mark.parametrize("target", ["relative/report.txt", "/uploads/report.txt", "sandbox:/out/report.txt", "file:/out/report.txt"])
def test_unclosed_target_newline_keeps_human_followup(native, chunks, target):
    text = f"Useful ordinary words. [the report]({target}\nWant me to send it?"
    parts = list(text) if chunks == "characters" else (text.split("\n", 1) if chunks == "newline_split" else [text])
    if chunks == "newline_split": parts = [parts[0] + "\n", parts[1]]
    speech, before = asyncio.run(_render(parts, native=native, hold_open=True))
    assert speech == "Useful ordinary words. the report Want me to send it?"
    assert "Want me to" in "".join(before)


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("target", [
    'relative/report.txt "my\nreport"',
    '\nrelative/report.txt',
    '\n<relative/report.txt>',
    'relative/report.txt "my )\nreport"',
    'relative/report.txt\n"title"',
    "relative/report.txt 'my\nreport'",
    'relative/report.txt\n(parenthetical title)',
    'relative/report.txt (my\nreport)',
    'relative/a(b(c))/report.txt "title with (parentheses)"',
    r'relative/a\(b\)/report.txt "title"',
    'relative/report.txt\n)',
])
def test_complete_multiline_target_titles_stay_non_speech(native, character_chunks, target):
    text = f"Useful ordinary words. [the\nreport]({target}) Then continue."
    if target.endswith(")\n)"): raise AssertionError("invalid fixture")
    if target == 'relative/report.txt\n)': text = "Useful ordinary words. [the\nreport](relative/report.txt\n) Then continue."
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == "Useful ordinary words. the report Then continue."


@pytest.mark.parametrize("text", [
    "[the report](sandbox:/out/report.txt\nWant me to send it?",
    "![the diagram](relative/diagram.png\nWant me to show it?",
])
def test_followup_recovers_only_after_malformed_target_line(text):
    expected = "the report Want me to send it?" if text.startswith("[the report]") else "the diagram Want me to show it?"
    assert sanitize_voice_followup_text(text) == expected


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("destination", ['<docs/with " quote>', "<docs/with ' quote>", '<docs/with ( note>'])
def test_angle_destination_contents_cannot_start_title(native, character_chunks, destination):
    text = f"Useful ordinary words. [the report]({destination}) Then continue."
    speech, _ = asyncio.run(_render(list(text) if character_chunks else [text], native=native))
    assert speech == "Useful ordinary words. the report Then continue."


@pytest.mark.parametrize("quote", ['"', "'"])
def test_followup_keeps_suffix_after_angle_destination_quote(quote):
    text = f'[the report](<docs/with {quote} quote>) Then continue.'
    assert sanitize_voice_followup_text(text) == "the report Then continue."


@pytest.mark.parametrize("native", [True, False])
@pytest.mark.parametrize("character_chunks", [True, False])
@pytest.mark.parametrize("tail", ['"Ready" to share?', "'Ready' to share?", '(Ready) to share?'])
def test_invalid_suffix_after_multiline_title_recovers_authored_words(native, character_chunks, tail):
    text = "Useful words. [the report](sandbox:/out/report.txt\n" + tail
    speech, before = asyncio.run(_render(list(text) if character_chunks else [text], native=native, hold_open=True))
    expected = "Useful words. the report " + tail
    assert speech == expected
    assert "to share" in "".join(before)


@pytest.mark.parametrize("tail", ['"Ready" to share?', "'Ready' to share?", '(Ready) to share?'])
def test_followup_invalid_suffix_after_multiline_title_keeps_words(tail):
    text = "Useful words. [the report](sandbox:/out/report.txt\n" + tail
    assert sanitize_voice_followup_text(text) == "Useful words. the report " + tail


@pytest.mark.parametrize("raw, expected", [
    ("Email qa_first.last+test@example.test.", "Email qa_first.last+test@example.test."),
    ("Email _first_+qa@example.test.", "Email _first_+qa@example.test."),
    ("Email **qa_first+test@example.test**.", "Email qa_first+test@example.test."),
    ("Email _qa@example.test_.", "Email qa@example.test."),
    ("Use docs.example.test/path and qa@example.test.", "Use docs.example.test/path and qa@example.test."),
])
def test_requested_email_survives_the_actual_transcription_buffer(raw, expected):
    for cut in range(len(raw) + 1):
        buffer = _VoiceTtsDeltaBuffer(native_streaming=lambda: True, preserve_text=True)
        display = VoiceControlDisplayFilter()
        actual = ""
        for chunk in (raw[:cut], raw[cut:]):
            actual += "".join(display.feed(value) for value in buffer.feed(chunk))
        actual += "".join(display.feed(value) for value in buffer.finalize())
        actual += display.feed("", final=True)
        assert actual == expected, cut
    speech = sanitize_voice_tts_text(expected)
    assert "@" not in speech
    assert "address available" in speech
    if "docs.example.test/path" in expected:
        assert "docs.example.test/path" in speech


@pytest.mark.parametrize("text", [
    "Open https://docs.example.test/_Path_?part=A_B#Result now.",
    "Use docs.example.test/path now.",
    "The amount is 2.5. Keep it.",
    "Wait... Yes! Ready.Next.",
])
def test_display_buffer_preserves_reference_and_punctuation_bytes(text):
    for cut in range(len(text) + 1):
        buffer = _VoiceTtsDeltaBuffer(native_streaming=lambda: True, preserve_text=True)
        display = VoiceControlDisplayFilter()
        chunks = [value for chunk in (text[:cut], text[cut:]) for value in buffer.feed(chunk)]
        chunks.extend(buffer.finalize())
        actual = "".join(display.feed(value) for value in chunks) + display.feed("", final=True)
        assert actual == text, cut


def test_display_preservation_does_not_change_default_speech_boundary_repair():
    speech = _VoiceTtsDeltaBuffer(native_streaming=lambda: True)
    display = _VoiceTtsDeltaBuffer(native_streaming=lambda: True, preserve_text=True)
    def render(buffer):
        chunks = buffer.feed("Ready.") + buffer.feed("Next.") + buffer.finalize()
        return "".join(chunks)
    assert render(speech) == "Ready. Next."
    assert render(display) == "Ready.Next."
