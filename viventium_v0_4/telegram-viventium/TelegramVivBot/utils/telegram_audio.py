# === VIVENTIUM START ===
"""One native decode, with exact source-sample silence before channel/rate conversion."""
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np


class TelegramAudioDecodeError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DecodedTelegramAudio:
    pcm: np.ndarray
    no_speech: bool = False


def decode_audio_bytes(file_bytes, timeout_s=120):
    """Preserve every source channel/rate for validation; Whisper gets float32 16 kHz mono.

    The preserved source is read in bounded chunks from a private temporary file. Only
    the recognizer's mono buffer enters RAM. No PCM16 quantization, energy threshold,
    duration gate, trimming, or model/provider inference is involved.
    """
    if not file_bytes:
        raise TelegramAudioDecodeError('audio_empty')
    if shutil.which('ffmpeg') is None:
        raise TelegramAudioDecodeError('media_decoder_unavailable')
    with tempfile.TemporaryDirectory(prefix='telegram-audio-') as directory:
        source = Path(directory) / 'input.media'
        preserved = Path(directory) / 'source.f32'
        recognizer = Path(directory) / 'recognizer.f32'
        source.write_bytes(file_bytes)
        command = [
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(source), '-filter_complex', '[0:a:0]asplit=2[source][recognizer]',
            '-map', '[source]', '-c:a', 'pcm_f32le', '-f', 'f32le', str(preserved),
            '-map', '[recognizer]', '-ac', '1', '-ar', '16000',
            '-c:a', 'pcm_f32le', '-f', 'f32le', str(recognizer),
        ]
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired as error:
            raise TelegramAudioDecodeError('timeout') from error
        except OSError as error:
            raise TelegramAudioDecodeError('media_decoder_unavailable') from error
        if result.returncode != 0:
            raise TelegramAudioDecodeError('audio_decode_failed')
        no_speech = True
        with preserved.open('rb') as stream:
            source_samples = 0
            while chunk := stream.read(32768 * 4):
                if len(chunk) % 4:
                    raise TelegramAudioDecodeError('audio_decode_failed')
                samples = np.frombuffer(chunk, dtype='<f4')
                if not np.isfinite(samples).all():
                    raise TelegramAudioDecodeError('audio_nonfinite')
                source_samples += samples.size
                no_speech = no_speech and not np.any(samples != 0)
        if not source_samples:
            raise TelegramAudioDecodeError('audio_empty')
        if no_speech:
            return DecodedTelegramAudio(np.empty(0, dtype=np.float32), no_speech=True)
        if recognizer.stat().st_size % 4:
            raise TelegramAudioDecodeError('audio_decode_failed')
        pcm = np.fromfile(recognizer, dtype='<f4')
        if not pcm.size:
            raise TelegramAudioDecodeError('audio_empty')
        if not np.isfinite(pcm).all():
            raise TelegramAudioDecodeError('audio_nonfinite')
        return DecodedTelegramAudio(pcm)
# === VIVENTIUM END ===
