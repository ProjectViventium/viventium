# === VIVENTIUM START ===
"""Native interval evidence must never become a transcript phrase rule."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))
from whisper_cpp_segments import join_native_segments


def test_exact_zero_interval_only_and_input_unchanged():
    pcm = np.zeros(48000, dtype=np.float32)
    pcm[1600] = pcm[33600] = 0.001
    before = pcm.tobytes()
    segments = [SimpleNamespace(t0=0, t1=100, text=' Start '),
                SimpleNamespace(t0=100, t1=200, text='any native text'),
                SimpleNamespace(t0=200, t1=300, text=' Late ')]
    assert join_native_segments(segments, pcm) == ' Start   Late '
    assert join_native_segments(segments, None) == ' Start  any native text  Late '
    assert pcm.tobytes() == before


@pytest.mark.parametrize('sample', [1e-8, np.nextafter(np.float32(0), np.float32(1)),
                                  np.nan, np.inf, -np.inf])
def test_nonzero_or_nonfinite_sample_keeps_genuine_native_text(sample):
    pcm = np.zeros(16000, dtype=np.float32)
    pcm[8000] = sample
    assert join_native_segments([SimpleNamespace(t0=0, t1=100, text='Thank you.')], pcm) == 'Thank you.'


@pytest.mark.parametrize('start,end', [(None, 100), (0, None), (False, 100), (0, True),
    (0.0, 100), (0, float('nan')), (-1, 100), (100, 0), (0, 0), (0, 101),
    (0, np.int64(np.iinfo(np.int64).max))])
def test_unknown_or_invalid_native_interval_keeps_text(start, end):
    assert join_native_segments([SimpleNamespace(t0=start, t1=end, text='Kept')],
        np.zeros(16000, dtype=np.float32)) == 'Kept'


@pytest.mark.parametrize('pcm', [None, np.zeros((1, 16000), dtype=np.float32),
                                np.zeros(16000, dtype=np.int16), np.array([], dtype=np.float32)])
def test_unknown_pcm_shape_keeps_text(pcm):
    assert join_native_segments([SimpleNamespace(t0=0, t1=100, text='Kept')], pcm) == 'Kept'


def test_missing_timestamp_legacy_and_empty_segments_keep_contract():
    pcm = np.zeros(16000, dtype=np.float32)
    assert join_native_segments([SimpleNamespace(text=' Legacy ')], pcm) == ' Legacy '
    assert join_native_segments([], pcm) == ''
    assert join_native_segments([SimpleNamespace(t0=0, t1=100, text='')], pcm) == ''
# === VIVENTIUM END ===
