# === VIVENTIUM START ===
"""Prepare a chronological vision image from a Telegram MP4."""

from dataclasses import dataclass
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont


MAX_SAMPLE_FPS = 2
MAX_GRID_FRAMES = 12
TILE_SIZE = 320
LABEL_HEIGHT = 30
GRID_COLUMNS = 4


class VideoNoteFrameError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VideoNoteGrid:
    jpeg: bytes
    frame_count: int
    has_audio: bool | None = None


def extract_video_note_grid(video: bytes, duration: int, timeout_s: float = 10) -> VideoNoteGrid:
    """Sample an MP4, measuring its duration and audio tracks when duration is unknown."""
    deadline = time.monotonic() + timeout_s
    with tempfile.TemporaryDirectory(prefix="telegram-video-note-") as directory:
        workspace = Path(directory)
        source = workspace / "input.mp4"
        source.write_bytes(video)
        has_audio = None
        try:
            if duration <= 0:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-f", "mov",
                     "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(source)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=max(0, deadline - time.monotonic()), check=True,
                )
                metadata = json.loads(probe.stdout)
                duration = float(metadata["format"]["duration"])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError("Invalid video duration")
                has_audio = any(stream["codec_type"] == "audio" for stream in metadata["streams"])
            fps = min(MAX_SAMPLE_FPS, MAX_GRID_FRAMES / max(1, duration))
            filters = (
                f"fps={fps:.12g}:start_time=0:eof_action=pass,"
                f"scale={TILE_SIZE}:{TILE_SIZE}:force_original_aspect_ratio=decrease,setsar=1"
            )
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
                 "-protocol_whitelist", "file", "-f", "mov", "-i", str(source),
                 "-map", "0:v:0", "-vf", filters, "-frames:v", str(MAX_GRID_FRAMES),
                 "-q:v", "3", str(workspace / "frame-%02d.jpg")],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=max(0, deadline - time.monotonic()), check=True,
            )
        except subprocess.TimeoutExpired as error:
            raise VideoNoteFrameError("video_frames_timeout") from error
        except OSError as error:
            raise VideoNoteFrameError("media_decoder_unavailable") from error
        except (subprocess.CalledProcessError, KeyError, ValueError) as error:
            raise VideoNoteFrameError("video_frames_decode_failed") from error

        frames = sorted(workspace.glob("frame-*.jpg"))
        if not frames:
            raise VideoNoteFrameError("video_frames_empty")
        columns = min(GRID_COLUMNS, len(frames))
        rows = (len(frames) + columns - 1) // columns
        row_height = TILE_SIZE + LABEL_HEIGHT
        grid = Image.new("RGB", (columns * TILE_SIZE, rows * row_height), "#171717")
        draw = ImageDraw.Draw(grid)
        font = ImageFont.load_default(size=20)
        for index, path in enumerate(frames):
            y, x = divmod(index, columns)
            left, top = x * TILE_SIZE, y * row_height
            with Image.open(path) as frame:
                grid.paste(frame, (left + (TILE_SIZE - frame.width) // 2,
                                   top + (TILE_SIZE - frame.height) // 2))
            draw.text((left + 8, top + TILE_SIZE + 3), f"{index / fps:.2f}s",
                      font=font, fill="white")
        output = BytesIO()
        grid.save(output, format="JPEG", quality=88)
        return VideoNoteGrid(output.getvalue(), len(frames), has_audio)
# === VIVENTIUM END ===
