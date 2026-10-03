# === VIVENTIUM START ===
"""Join native text, excluding only intervals proven to contain digital silence."""
from numbers import Integral

import numpy as np


def join_native_segments(segments, pcm):
    """Native t0/t1 are centiseconds. Unknown source or timing retains its text.

    The caller supplies the same complete mono 16 kHz PCM consumed by the model.
    No input is changed and no transcript words influence this check.
    """
    known = (isinstance(pcm, np.ndarray) and pcm.ndim == 1
             and pcm.size > 0 and pcm.dtype.kind == 'f')
    text = []
    for segment in segments or ():
        if known:
            start, end = getattr(segment, 't0', None), getattr(segment, 't1', None)
            if (isinstance(start, Integral) and not isinstance(start, bool)
                    and isinstance(end, Integral) and not isinstance(end, bool)
                    and 0 <= start < end and int(end) * 160 <= pcm.size):
                # NaN/Inf and even the smallest nonzero float keep the segment.
                if np.count_nonzero(pcm[int(start) * 160:int(end) * 160]) == 0:
                    continue
        text.append(segment.text)
    return ' '.join(text)
# === VIVENTIUM END ===
