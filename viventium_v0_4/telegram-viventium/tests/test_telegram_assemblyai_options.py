# === VIVENTIUM START ===
"""Compiled call settings reach note recognition without loading a call worker."""
import ast
import types
from pathlib import Path
from typing import Any, Optional

import pytest

from TelegramVivBot.utils.stt_env import build_assemblyai_stt_options, normalize_voice_context_keyterms


def _call_builder():
    """The call's own builder with the one module value it reads, without loading a worker."""
    source = Path(__file__).resolve().parents[2] / 'voice-gateway' / 'worker.py'
    wanted = [
        node for node in ast.parse(source.read_text()).body
        if (isinstance(node, ast.FunctionDef) and node.name == '_build_assemblyai_stt_kwargs')
        or (isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == '_ASSEMBLYAI_MAX_TURN_SILENCE_MS'
            for target in node.targets))
    ]
    namespace = {'Env': object, 'Any': Any, 'Optional': Optional,
                 '_normalize_assemblyai_stt_model': lambda value: value}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_build_assemblyai_stt_kwargs'], namespace['_ASSEMBLYAI_MAX_TURN_SILENCE_MS']


@pytest.mark.parametrize('format_turns', ['true', 'false'])
def test_note_options_equal_call_builder_for_the_values_a_call_still_sends(format_turns):
    # A call no longer reads the compiled end-of-turn values: it sends one fixed unfinished-sentence
    # wait. When the compiled config carries that same wait, a note and a call send the same options.
    build_call, call_silence_ms = _call_builder()
    keyterms = ['Example Meeting']
    call = build_call(types.SimpleNamespace(
        assemblyai_stt_model='universal-streaming-multilingual',
        assemblyai_format_turns=format_turns == 'true',
    ), keyterms)
    assert call.pop('model') == 'universal-streaming-multilingual'
    assert build_assemblyai_stt_options({
        'VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS': str(call_silence_ms),
        'VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS': format_turns,
    }, keyterms) == call


def test_note_still_forwards_every_compiled_end_of_turn_value():
    assert build_assemblyai_stt_options({
        'VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD': '0.31',
        'VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS': '240',
        'VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS': '1500',
    }) == {
        'speaker_labels': True, 'end_of_turn_confidence_threshold': 0.31,
        'min_turn_silence': 240, 'max_turn_silence': 1500,
    }


@pytest.mark.parametrize('value', [None, []])
def test_empty_context_and_unset_options_keep_provider_defaults(value):
    assert build_assemblyai_stt_options({}, value) == {'speaker_labels': True}


@pytest.mark.parametrize('value', ['word', [''], [12], ['private/path'], ['private\\path'],
                                    ['line\nfeed'], ['x' * 97], ['term'] * 33])
def test_malformed_or_unbounded_context_is_not_sent_to_provider(value):
    with pytest.raises(ValueError):
        normalize_voice_context_keyterms(value)


@pytest.mark.parametrize('value', ['invalid', '-1', 'nan', 'inf'])
def test_invalid_optional_compiled_numbers_are_not_forwarded(value):
    assert build_assemblyai_stt_options({
        'VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD': value,
        'VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS': value,
        'VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS': value,
    }) == {'speaker_labels': True}


def test_options_are_read_for_each_note_without_mutating_context():
    source = ['Example Meeting']
    first = build_assemblyai_stt_options({'VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS': '1000'}, source)
    second = build_assemblyai_stt_options({'VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS': '1500'}, [])
    first['keyterms_prompt'].append('Only First')
    assert source == ['Example Meeting']
    assert second == {'speaker_labels': True, 'max_turn_silence': 1500}
# === VIVENTIUM END ===
