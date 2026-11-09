# === VIVENTIUM START ===
"""Video-note preparation keeps the original input and its visual evidence together."""

import base64
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / "TelegramVivBot"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
sys.modules.setdefault("config", SimpleNamespace(VIVENTIUM_TELEGRAM_BACKEND="librechat"))

from TelegramVivBot.utils import scripts, telegram_audio, telegram_stt, telegram_video


@pytest.fixture
def clip(tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("Requires the Telegram FFmpeg runtime")
    file = tmp_path / "colors.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=red:s=96x96:r=10:d=1",
         "-f", "lavfi", "-i", "color=blue:s=96x96:r=10:d=1",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
         "-c:v", "libx264", str(file)],
        check=True, timeout=10,
    )
    return file.read_bytes()


@pytest.mark.parametrize("duration", [2, 0])
def test_real_ffmpeg_grid_keeps_temporal_order_and_labels(clip, duration):
    if duration == 0 and shutil.which("ffprobe") is None:
        pytest.skip("Requires the Telegram ffprobe runtime")
    result = telegram_video.extract_video_note_grid(clip, duration=duration)
    assert result.has_audio is (None if duration else False)
    assert result.frame_count == 4
    with Image.open(BytesIO(result.jpeg)) as image:
        assert image.format == "JPEG"
        assert image.size == (1280, 350)
        for index in (0, 1):
            red, _, blue = image.getpixel((160 + index * 320, 160))
            assert red > blue + 100
        for index in (2, 3):
            red, _, blue = image.getpixel((160 + index * 320, 160))
            assert blue > red + 100
        assert max(image.crop((0, 320, 90, 350)).convert("L").getextrema()) > 220


def test_invalid_mp4_reports_visual_decode_failure():
    if shutil.which("ffmpeg") is None:
        pytest.skip("Requires the Telegram FFmpeg runtime")
    with pytest.raises(telegram_video.VideoNoteFrameError, match="video_frames_decode_failed"):
        telegram_video.extract_video_note_grid(b"invalid media", duration=4)


@pytest.mark.asyncio
@pytest.mark.parametrize("media_kind", ["video_note", "video", "document"])
@pytest.mark.parametrize(
    ("speech", "visuals", "files", "partial"),
    [
        ("spoken", "ready", 1, None),
        ("silent", "ready", 1, None),
        ("route_unavailable", "ready", 1, "voice_route_unavailable"),
        ("failed", "ready", 1, "transcription_failed"),
        ("spoken", "failed", 0, "video_frames_timeout"),
        ("failed", "failed", 0, None),
        ("silent", "failed", 0, None),
    ],
)
async def test_video_note_uses_one_download_and_preserves_each_available_part(
    monkeypatch, media_kind, speech, visuals, files, partial,
):
    downloads = []
    decoded = []
    video = b"video bytes"

    async def download(_bot, file_id, **_kwargs):
        downloads.append(file_id)
        return scripts.TelegramDownloadResult(file_bytes=video)

    async def route(**identity):
        assert identity == {
            "telegram_user_id": "owner", "telegram_chat_id": "chat",
            "telegram_message_thread_id": 9,
        }
        if speech == "route_unavailable":
            raise TimeoutError
        return {"stt": {"provider": "pywhispercpp", "variant": "tiny", "source": "saved"}}

    async def transcribe(data, _timeout, *, selection, timing, input_format):
        decoded.append("audio")
        assert data is video
        assert selection == {"provider": "pywhispercpp", "variant": "tiny"}
        assert input_format == (None if media_kind == "video_note" else "mov")
        if speech == "silent":
            raise telegram_audio.TelegramAudioDecodeError("no_speech")
        if speech == "failed":
            raise telegram_stt.TelegramSTTError("transcription_failed")
        return "Exact spoken text."

    def prepare_grid(data, duration):
        decoded.append("video")
        assert data is video
        assert duration == (4 if media_kind == "video_note" else 0)
        if visuals == "failed":
            raise telegram_video.VideoNoteFrameError("video_frames_timeout")
        return telegram_video.VideoNoteGrid(b"jpeg bytes", 8)

    monkeypatch.setattr(scripts.config, "ChatGPTbot", SimpleNamespace(get_voice_route=route), raising=False)
    monkeypatch.setattr(scripts.config, "VIVENTIUM_TELEGRAM_FILE_UPLOAD_ENABLED", True, raising=False)
    monkeypatch.setattr(scripts.config, "NICK", None, raising=False)
    monkeypatch.setattr(sys.modules["config"], "VIVENTIUM_TELEGRAM_BACKEND", "librechat", raising=False)
    monkeypatch.setattr(scripts, "download_telegram_file_result", download)
    monkeypatch.setattr(scripts, "_transcribe_audio_bytes", transcribe)
    monkeypatch.setattr(telegram_video, "extract_video_note_grid", prepare_grid)
    update = SimpleNamespace(
        chat_id="chat", from_user=SimpleNamespace(id="owner"), chat=SimpleNamespace(type="private"),
        is_topic_message=True, message_thread_id=9, message_id=17, text=None, caption=None,
        reply_to_message=None, photo=None, voice=None, audio=None, video=None, document=None,
        video_note=None,
    )
    filename = "sample.MP4" if media_kind != "video_note" else None
    if filename and speech == "spoken" and visuals == "ready":
        update.caption = "  Exact caption: café 17 + 23\nSecond line.  "
    setattr(update, media_kind, SimpleNamespace(
        file_id="clip", duration=4, file_name=filename, mime_type="application/octet-stream",
    ))
    result = await scripts.GetMesage(update, SimpleNamespace(bot=object()))
    assert downloads == ["clip"]
    assert result[:2] == (update.caption, update.caption)
    assert sorted(decoded) == (["video"] if speech == "route_unavailable" else ["audio", "video"])
    assert result[10] == ("Exact spoken text." if speech == "spoken" else None)
    notice = result[11]
    if partial:
        assert notice.continues and notice.error_code == partial
    elif visuals == "failed":
        expected = "video_frames_timeout" if speech == "silent" else "transcription_failed"
        assert notice.error_code == expected and not notice.continues
    else:
        assert notice is None
    assert len(result[12]) == files
    if files:
        assert result[12][0]["mime_type"] == "image/jpeg"
        assert base64.b64decode(result[12][0]["data"]) == b"jpeg bytes"
        assert result[12][0]["filename"] == (
            "video-note-frames.jpg" if media_kind == "video_note" else "sample-frames.jpg"
        )
    assert result[13] == []


@pytest.mark.asyncio
async def test_uploaded_mp4_with_no_audio_track_is_visual_only(clip, monkeypatch):
    if shutil.which("ffprobe") is None:
        pytest.skip("Requires the Telegram ffprobe runtime")

    async def download(*_args, **_kwargs):
        return scripts.TelegramDownloadResult(file_bytes=clip)

    monkeypatch.setattr(scripts, "download_telegram_file_result", download)
    result = await scripts.transcribe_video("clip", SimpleNamespace(bot=object()), frame_duration=0)
    assert result.frame_grid.startswith(b"\xff\xd8")
    assert result.text is None
    assert result.error_code is None
    assert result.frame_error is None
# === VIVENTIUM END ===
