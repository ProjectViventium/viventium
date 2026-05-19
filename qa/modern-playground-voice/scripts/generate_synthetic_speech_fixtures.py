#!/usr/bin/env python3
"""Generate public-safe fake-microphone WAV fixtures for LiveKit voice QA."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

try:
    import audioop
except ModuleNotFoundError:
    audioop = None


ROOT = Path(__file__).resolve().parents[3]
VOICE_GATEWAY_DIR = ROOT / "viventium_v0_4" / "voice-gateway"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "qa" / "modern-playground-voice" / "synthetic-audio"


@dataclass(frozen=True)
class Segment:
    text: str
    silence_after_s: float = 0.0


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    purpose: str
    segments: tuple[Segment, ...]
    expected_transcript_rows: int = 1

    @property
    def expected_text(self) -> str:
        return " ".join(segment.text for segment in self.segments)


FIXTURES: tuple[FixtureCase, ...] = (
    FixtureCase(
        case_id="short",
        purpose="Short, single-turn transcript sanity check.",
        segments=(Segment("Short synthetic voice QA. Alpha bravo."),),
    ),
    FixtureCase(
        case_id="pause-700ms",
        purpose="Continuation after a pause longer than the local 0.5 second endpointing target.",
        segments=(
            Segment("I need help with the invoice.", 0.7),
            Segment("And also the receipt."),
        ),
    ),
    FixtureCase(
        case_id="pause-1500ms",
        purpose="Human-style resumed thought after a clearly noticeable pause.",
        segments=(
            Segment("Here is the first part of my thought.", 1.5),
            Segment("Actually continue that same thought with the second part."),
        ),
    ),
    FixtureCase(
        case_id="long",
        purpose="Longer utterance to expose Whisper inference and buffering tails.",
        segments=(
            Segment(
                "This is a longer synthetic voice QA passage. "
                "It checks whether the local LiveKit path can carry a complete spoken request, "
                "including several clauses, without dropping the ending or delaying the final words."
            ),
        ),
    ),
)


def read_wav_mono_s16(path: Path, *, target_rate: int) -> bytes:
    if audioop is None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("Python audioop or ffmpeg is required to normalize WAV fixtures")
        return subprocess.run(
            [
                ffmpeg,
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-ar",
                str(target_rate),
                "-ac",
                "1",
                "-sample_fmt",
                "s16",
                "-f",
                "s16le",
                "pipe:1",
            ],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout

    with wave.open(str(path), "rb") as reader:
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        frame_rate = reader.getframerate()
        pcm = reader.readframes(reader.getnframes())

    if sample_width != 2:
        pcm = audioop.lin2lin(pcm, sample_width, 2)
        sample_width = 2
    if channels > 1:
        pcm = audioop.tomono(pcm, sample_width, 0.5, 0.5)
        channels = 1
    if frame_rate != target_rate:
        pcm, _ = audioop.ratecv(pcm, sample_width, channels, frame_rate, target_rate, None)
    return pcm


def write_wav(path: Path, *, pcm: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm)


def silence(*, sample_rate: int, seconds: float) -> bytes:
    if seconds <= 0:
        return b""
    return b"\0\0" * int(round(sample_rate * seconds))


def synthesize_with_mlx(text: str, *, temp_dir: Path, index: int) -> Path:
    sys.path.insert(0, str(VOICE_GATEWAY_DIR))
    from mlx_chatterbox_tts import MlxChatterboxConfig, synthesize_wav_bytes

    wav = synthesize_wav_bytes(
        text,
        config=MlxChatterboxConfig(stream=True, streaming_interval_s=1.0),
    )
    if not wav:
        raise RuntimeError("local Chatterbox generated no audio")
    path = temp_dir / f"segment-{index:02d}-mlx.wav"
    path.write_bytes(wav)
    return path


def synthesize_with_macos_say(text: str, *, temp_dir: Path, index: int, sample_rate: int) -> Path:
    say = shutil.which("say")
    ffmpeg = shutil.which("ffmpeg")
    afconvert = shutil.which("afconvert")
    if not say:
        raise RuntimeError("macOS say is not available")

    aiff_path = temp_dir / f"segment-{index:02d}.aiff"
    wav_path = temp_dir / f"segment-{index:02d}-say.wav"
    subprocess.run([say, "-o", str(aiff_path), text], check=True)
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(aiff_path),
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-sample_fmt",
                "s16",
                str(wav_path),
            ],
            check=True,
        )
    elif afconvert:
        subprocess.run(
            [
                afconvert,
                "-f",
                "WAVE",
                "-d",
                f"LEI16@{sample_rate}",
                "-c",
                "1",
                str(aiff_path),
                str(wav_path),
            ],
            check=True,
        )
    else:
        raise RuntimeError("ffmpeg or afconvert is required to convert macOS say output to WAV")
    return wav_path


def synthesize_segment(
    text: str,
    *,
    provider: str,
    temp_dir: Path,
    index: int,
    sample_rate: int,
) -> tuple[Path, str]:
    if provider in {"auto", "mlx_chatterbox"}:
        try:
            return synthesize_with_mlx(text, temp_dir=temp_dir, index=index), "mlx_chatterbox"
        except Exception:
            if provider == "mlx_chatterbox":
                raise
    return (
        synthesize_with_macos_say(text, temp_dir=temp_dir, index=index, sample_rate=sample_rate),
        "macos_say",
    )


def generate_case(
    case: FixtureCase,
    *,
    output_dir: Path,
    provider: str,
    sample_rate: int,
    tail_silence_s: float,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"viventium-{case.case_id}-") as temp:
        temp_dir = Path(temp)
        pcm_parts = [silence(sample_rate=sample_rate, seconds=0.35)]
        providers: list[str] = []
        for index, segment in enumerate(case.segments):
            segment_path, used_provider = synthesize_segment(
                segment.text,
                provider=provider,
                temp_dir=temp_dir,
                index=index,
                sample_rate=sample_rate,
            )
            providers.append(used_provider)
            pcm_parts.append(read_wav_mono_s16(segment_path, target_rate=sample_rate))
            pcm_parts.append(silence(sample_rate=sample_rate, seconds=segment.silence_after_s))
        pcm_parts.append(silence(sample_rate=sample_rate, seconds=tail_silence_s))

    wav_path = output_dir / f"{case.case_id}.wav"
    write_wav(wav_path, pcm=b"".join(pcm_parts), sample_rate=sample_rate)
    duration_s = sum(len(part) for part in pcm_parts) / float(sample_rate * 2)
    return {
        "caseId": case.case_id,
        "purpose": case.purpose,
        "file": str(wav_path),
        "sampleRate": sample_rate,
        "durationSeconds": round(duration_s, 3),
        "tailSilenceSeconds": tail_silence_s,
        "providers": sorted(set(providers)),
        "expectedText": case.expected_text,
        "expectedTranscriptRows": case.expected_transcript_rows,
        "segments": [
            {"text": segment.text, "silenceAfterSeconds": segment.silence_after_s}
            for segment in case.segments
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider", choices=["auto", "mlx_chatterbox", "macos_say"], default="auto")
    parser.add_argument("--case", dest="case_id", default="all")
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument(
        "--tail-silence-s",
        type=float,
        default=100.0,
        help="Trailing silence before Chromium fake-mic loops the WAV.",
    )
    args = parser.parse_args()

    selected = [case for case in FIXTURES if args.case_id in {"all", case.case_id}]
    if not selected:
        raise SystemExit(f"unknown fixture case: {args.case_id}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "providerRequested": args.provider,
        "fixtures": [
            generate_case(
                case,
                output_dir=args.output_dir,
                provider=args.provider,
                sample_rate=args.sample_rate,
                tail_silence_s=args.tail_silence_s,
            )
            for case in selected
        ],
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "fixtureCount": len(selected)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
