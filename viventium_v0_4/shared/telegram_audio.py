"""Buffered audio for Telegram's MP3/M4A sendAudio contract."""

from dataclasses import dataclass
from io import BytesIO
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import wave


class TelegramAudioError(RuntimeError):
    """A classified media failure before any Telegram transport starts."""


@dataclass(frozen=True)
class TelegramAudio:
    data: bytes
    filename: str
    content_type: str
    duration_seconds: float

    @property
    def duration(self) -> int:
        # The API accepts whole seconds. Preserve the measured value separately.
        return math.ceil(self.duration_seconds)


def finalize_wav_chunks(chunks: list[bytes]) -> bytes:
    """Finalize buffered PCM, including one chunk with streaming length fields."""
    if not chunks:
        return b""
    frames = []
    params = None
    for chunk in chunks:
        try:
            with wave.open(BytesIO(chunk), "rb") as source:
                current = source.getparams()[:3]
                if params is not None and current != params:
                    raise TelegramAudioError("Cartesia WAV segment params differ")
                params = current
                pcm = source.readframes(source.getnframes())
                width = current[0] * current[1]
                if not pcm or len(pcm) % width:
                    raise TelegramAudioError("audio_empty_or_partial_frame")
                if len(pcm) // width != source.getnframes() and source.getnframes() != 0xffffffff // width:
                    raise TelegramAudioError("audio_truncated")
                frames.append(pcm)
        except (wave.Error, EOFError) as error:
            raise TelegramAudioError("audio_decode_failed") from error
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(params[0])
        target.setsampwidth(params[1])
        target.setframerate(params[2])
        target.writeframes(b"".join(frames))
    return output.getvalue()


def _run(command: list[str], timeout_s: float) -> bytes:
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as error:
        raise TelegramAudioError("media_timeout") from error
    except OSError as error:
        raise TelegramAudioError("media_encoder_unavailable") from error
    if result.returncode:
        raise TelegramAudioError("audio_decode_or_encode_failed")
    return result.stdout


def package_telegram_audio(audio_bytes: bytes | list[bytes], timeout_s: float = 30) -> TelegramAudio:
    """Keep supported media bytes; encode other containers with the existing FFmpeg tool."""
    if not audio_bytes:
        raise TelegramAudioError("audio_empty")
    deadline = time.monotonic() + max(0, timeout_s)
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TelegramAudioError("media_timeout")
        return value
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise TelegramAudioError("media_probe_unavailable")
    chunks = audio_bytes if isinstance(audio_bytes, list) else [audio_bytes]
    if any(not chunk for chunk in chunks):
        raise TelegramAudioError("audio_empty")
    if all(chunk[:4] == b"RIFF" and chunk[8:12] == b"WAVE" for chunk in chunks):
        audio_bytes = finalize_wav_chunks(chunks)
        chunks = [audio_bytes]
    else:
        audio_bytes = chunks[0]
    with tempfile.TemporaryDirectory(prefix="telegram-send-audio-") as directory:
        source = Path(directory) / "source.media"
        source.write_bytes(audio_bytes)
        if len(chunks) > 1:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise TelegramAudioError("media_encoder_unavailable")
            manifest = Path(directory) / "chunks.txt"
            for index, chunk in enumerate(chunks):
                (Path(directory) / f"chunk{index}.media").write_bytes(chunk)
            manifest.write_text("".join(f"file 'chunk{index}.media'\n" for index in range(len(chunks))))
            source = Path(directory) / "combined.mp3"
            _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "concat", "-safe", "1", "-i", str(manifest), "-map", "0:a:0",
                  "-vn", "-c:a", "libmp3lame", "-b:a", "128k", str(source)], remaining())
            audio_bytes = source.read_bytes()

        def probe(path):
            try:
                value = json.loads(_run([
                    ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path),
                ], remaining()))
                streams = value.get("streams") or []
                audio = next(stream for stream in streams if stream.get("codec_type") == "audio")
                duration = float(audio.get("duration") or value["format"]["duration"])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError("duration")
                return value["format"]["format_name"].split(","), duration, streams
            except (ValueError, KeyError, StopIteration, TypeError) as error:
                raise TelegramAudioError("audio_metadata_invalid") from error

        formats, duration, streams = probe(source)
        if "mp3" in formats:
            return TelegramAudio(audio_bytes, "Voice.mp3", "audio/mpeg", duration)
        if "m4a" in formats and all(stream.get("codec_type") == "audio" for stream in streams):
            return TelegramAudio(audio_bytes, "Voice.m4a", "audio/mp4", duration)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise TelegramAudioError("media_encoder_unavailable")
        target = Path(directory) / "Voice.mp3"
        _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
              "-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-b:a", "128k", str(target)], remaining())
        formats, duration, _ = probe(target)
        if "mp3" not in formats:
            raise TelegramAudioError("audio_metadata_invalid")
        return TelegramAudio(target.read_bytes(), "Voice.mp3", "audio/mpeg", duration)
