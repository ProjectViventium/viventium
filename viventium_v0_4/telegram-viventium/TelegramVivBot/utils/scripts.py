def CutNICK(update_text, update_message):
    import config
    botNick = config.NICK.lower() if config.NICK else None
    botNicKLength = len(botNick) if botNick else 0

    update_chat = update_message.chat
    update_reply_to_message = update_message.reply_to_message
    if botNick is None:
        return update_text
    else:
        if update_text[:botNicKLength].lower() == botNick:
            return update_text[botNicKLength:].strip()
        else:
            if update_chat.type == 'private' or (botNick and update_reply_to_message and update_reply_to_message.text and update_reply_to_message.from_user.is_bot and update_reply_to_message.sender_chat == None):
                return update_text
            else:
                return None

time_out = 600
async def get_file_url(file, context):
    file_id = file.file_id
    new_file = await context.bot.get_file(file_id, read_timeout=time_out, write_timeout=time_out, connect_timeout=time_out, pool_timeout=time_out)
    file_url = new_file.file_path
    return file_url

from io import BytesIO
import asyncio
import logging
import time
import base64
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
try:
    import config
except Exception:
    config = None

# === VIVENTIUM START ===
# Feature: Telegram file upload to LibreChat agent
# Download files from Telegram servers with MIME detection for vision model support.

# MIME type mapping for common extensions
EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".json": "application/json",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
    ".csv": "text/csv",
    ".html": "text/html",
    ".xml": "application/xml",
}

# Supported image MIME types for vision models
SUPPORTED_IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/tiff", "image/heic", "image/heif"
}


@dataclass
class TelegramDownloadResult:
    file_bytes: Optional[bytes] = None
    mime_type: str = ""
    filename: str = ""
    error_code: Optional[str] = None


@dataclass
class TelegramTranscriptionResult:
    text: Optional[str] = None
    error_text: Optional[str] = None
    error_code: Optional[str] = None

def detect_mime_from_path(file_path: str) -> str:
    """Detect MIME type from file path extension."""
    if not file_path:
        return "application/octet-stream"
    ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


def _transcription_download_error(media_label: str, error_code: Optional[str]) -> TelegramTranscriptionResult:
    if error_code == "file_too_large":
        return TelegramTranscriptionResult(
            error_text=f"This {media_label} is too large to transcribe in Telegram right now.",
            error_code=error_code,
        )
    if error_code == "download_timeout":
        return TelegramTranscriptionResult(
            error_text=f"Timed out downloading this {media_label} from Telegram. Please retry.",
            error_code=error_code,
        )
    return TelegramTranscriptionResult(
        error_text=f"Temporarily unable to download this {media_label} from Telegram. Please retry.",
        error_code=error_code or "download_failed",
    )


def _transcription_runtime_error(
    media_label: str,
    error_code: str = "transcription_failed",
) -> TelegramTranscriptionResult:
    if error_code == "media_decoder_unavailable":
        return TelegramTranscriptionResult(
            error_text=(
                f"Temporarily unable to transcribe this {media_label} because Telegram media "
                "decoding is not ready. Run bin/viventium upgrade, then retry."
            ),
            error_code=error_code,
        )
    return TelegramTranscriptionResult(
        error_text=f"Temporarily unable to transcribe this {media_label}. Please retry.",
        error_code=error_code,
    )


def classify_telegram_download_error(exc: Exception) -> str:
    message = str(exc or "").strip().lower()
    oversize_markers = (
        "file is too big",
        "file too large",
        "request entity too large",
        "payload too large",
        "entity_content_too_large",
    )
    if any(marker in message for marker in oversize_markers):
        return "file_too_large"
    if "timed out" in message or "timeout" in message:
        return "download_timeout"
    return "download_failed"


def ffmpeg_runtime_ready(timeout_s: float = 5.0) -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    try:
        completed = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=16000",
                "-t",
                "0.05",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg runtime probe failed: %s", exc)
        return False
    if completed.returncode != 0:
        logger.warning(
            "ffmpeg runtime probe exited with code %s",
            completed.returncode,
        )
        return False
    return True


async def download_telegram_file_result(
    bot,
    file_id: str,
    max_bytes: Optional[int] = None,
    filename_hint: Optional[str] = None,
    mime_type_hint: Optional[str] = None,
) -> TelegramDownloadResult:
    """
    Download file from Telegram servers with structured failure metadata.
    """
    try:
        if max_bytes is None:
            max_bytes = getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760)
        file = await bot.get_file(
            file_id,
            read_timeout=time_out,
            write_timeout=time_out,
            connect_timeout=time_out,
            pool_timeout=time_out,
        )
        file_path = file.file_path
        if not file_path:
            logger.warning(f"No file_path returned for file_id={file_id}")
            return TelegramDownloadResult(error_code="missing_file_path")

        if hasattr(file, "file_size") and file.file_size and file.file_size > max_bytes:
            logger.warning(f"File too large: {file.file_size} > {max_bytes} bytes")
            return TelegramDownloadResult(error_code="file_too_large")

        file_bytes = await file.download_as_bytearray()
        if not file_bytes:
            logger.warning(f"Downloaded file is empty for file_id={file_id}")
            return TelegramDownloadResult(error_code="empty_file")

        if len(file_bytes) > max_bytes:
            logger.warning(f"Downloaded file too large: {len(file_bytes)} > {max_bytes} bytes")
            return TelegramDownloadResult(error_code="file_too_large")

        mime_type = (mime_type_hint or "").strip()
        if not mime_type:
            mime_type = detect_mime_from_path(file_path)
        if mime_type == "application/octet-stream" and filename_hint:
            mime_type = detect_mime_from_path(filename_hint)

        filename = (filename_hint or "").strip()
        if not filename:
            filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

        logger.debug(f"Downloaded file: {filename}, {len(file_bytes)} bytes, {mime_type}")
        return TelegramDownloadResult(
            file_bytes=bytes(file_bytes),
            mime_type=mime_type,
            filename=filename,
        )

    except asyncio.TimeoutError:
        logger.warning(f"Timed out downloading file {file_id}")
        return TelegramDownloadResult(error_code="download_timeout")
    except TimeoutError:
        logger.warning(f"Timed out downloading file {file_id}")
        return TelegramDownloadResult(error_code="download_timeout")
    except Exception as e:
        logger.warning(f"Failed to download file {file_id}: {e}")
        return TelegramDownloadResult(error_code=classify_telegram_download_error(e))


async def download_telegram_file(
    bot,
    file_id: str,
    max_bytes: Optional[int] = None,
    filename_hint: Optional[str] = None,
    mime_type_hint: Optional[str] = None,
) -> Tuple[Optional[bytes], str, str]:
    """
    Download file from Telegram servers.

    Returns:
        Tuple of (file_bytes, mime_type, filename)
        Returns (None, "", "") if download fails or file is too large.
    """
    download_result = await download_telegram_file_result(
        bot,
        file_id,
        max_bytes=max_bytes,
        filename_hint=filename_hint,
        mime_type_hint=mime_type_hint,
    )
    return download_result.file_bytes, download_result.mime_type, download_result.filename


def encode_file_for_agent(
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> Dict[str, str]:
    """
    Encode file for LibreChat agent content array.

    Returns:
        Dict with data (base64), mime_type, and filename.
    """
    return {
        "data": base64.b64encode(file_bytes).decode("utf-8"),
        "mime_type": mime_type,
        "filename": filename,
    }


def is_image_mime(mime_type: str) -> bool:
    """Check if MIME type is a supported image type."""
    return mime_type in SUPPORTED_IMAGE_MIMES or mime_type.startswith("image/")
# === VIVENTIUM END ===

logger = logging.getLogger(__name__)

async def get_voice(file_id: str, context) -> TelegramTranscriptionResult:
    """Transcribe a voice message using Whisper (local or API)"""
    logger.info(f"Starting voice transcription for file_id={file_id}")

    try:
        download_result = await download_telegram_file_result(
            context.bot,
            file_id,
            max_bytes=getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760),
            filename_hint="voice.ogg",
            mime_type_hint="audio/ogg",
        )
        if not download_result.file_bytes:
            return _transcription_download_error("voice note", download_result.error_code)

        file_bytes = download_result.file_bytes
        logger.debug(f"Downloaded {len(file_bytes)} bytes from Telegram")

        whisper_mode = str(getattr(config, "WHISPER_MODE", "") or "").strip().lower()
        if whisper_mode in ("local", "pywhispercpp") and not ffmpeg_runtime_ready():
            logger.error("ffmpeg is not runnable for local Telegram voice transcription")
            return _transcription_runtime_error("voice note", "media_decoder_unavailable")

        # Use the proper transcription function that handles both local and API modes
        # This matches the pattern from telegram-bot-standalone
        logger.debug("Calling get_audio_message for transcription")
        from aient.aient.utils.scripts import get_audio_message
        timeout_s = int(os.environ.get("LOCAL_WHISPER_TIMEOUT_S", "120"))
        start_ts = time.monotonic()
        try:
            transcript = await asyncio.wait_for(
                asyncio.to_thread(get_audio_message, file_bytes),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            logger.exception("Transcription timed out after %ss", timeout_s)
            return _transcription_runtime_error("voice note", "timeout")
        finally:
            elapsed = time.monotonic() - start_ts
            logger.info("Transcription elapsed=%.2fs bytes=%d", elapsed, len(file_bytes))

        transcript_text = str(transcript or "").strip()
        if not transcript_text or transcript_text.startswith("error:"):
            logger.warning(f"Transcription failed or returned error: {transcript_text}")
            return _transcription_runtime_error("voice note")

        logger.info(f"Transcription successful, length: {len(transcript_text)} characters")
        return TelegramTranscriptionResult(text=transcript_text)

    except Exception as e:
        logger.exception(f"Exception during voice transcription: {e}")
        return _transcription_runtime_error("voice note")

import os
import sys
import tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def transcribe_video(
    file_id: str,
    context,
    *,
    media_label: str = "video note",
) -> TelegramTranscriptionResult:
    from aient.aient.utils.scripts import extract_audio_from_video, transcribe_audio_file

    try:
        if not ffmpeg_runtime_ready():
            logger.error("ffmpeg is not runnable for Telegram %s transcription", media_label)
            return _transcription_runtime_error(media_label, "media_decoder_unavailable")

        download_result = await download_telegram_file_result(
            context.bot,
            file_id,
            max_bytes=getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760),
            filename_hint="video.mp4",
            mime_type_hint="video/mp4",
        )
        if not download_result.file_bytes:
            return _transcription_download_error(media_label, download_result.error_code)

        file_bytes = download_result.file_bytes

        file_ext = os.path.splitext(download_result.filename or "")[1]
        if not file_ext:
            file_ext = ".mp4"

        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_video:
            temp_video.write(file_bytes)
            temp_video_path = temp_video.name

        audio_path = None
        try:
            audio_path = extract_audio_from_video(temp_video_path)
            transcript = transcribe_audio_file(audio_path)
        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)

        transcript_text = str(transcript or "").strip()
        if not transcript_text or transcript_text.startswith("error:"):
            logger.warning(f"Video transcription failed or returned error: {transcript_text}")
            return _transcription_runtime_error(media_label)

        return TelegramTranscriptionResult(text=transcript_text)

    except Exception as e:
        logger.exception(f"Exception during {media_label} transcription: {e}")
        return _transcription_runtime_error(media_label)

async def GetMesage(update_message, context, voice=True, *, override_user_id: Optional[str] = None):
    from aient.aient.utils.scripts import Document_extract
    image_url = None
    file_url = None
    reply_to_message_text = None
    message = None
    rawtext = None
    voice_text = None
    voice_error_text = None
    reply_to_message_file_content = None
    # === VIVENTIUM START ===
    # Feature: File upload to LibreChat agent - track file data for vision models
    file_data_list: List[Dict[str, str]] = []  # List of encoded files for agent
    # === VIVENTIUM END ===

    chatid = str(update_message.chat_id)
    # === VIVENTIUM START ===
    # Feature: Ensure callback-query preferences apply to the requesting user.
    # Reason: callback_query.message.from_user is the bot, so override_user_id
    # keeps per-user convo_id consistent with normal message flow.
    if override_user_id is not None:
        user_id = str(override_user_id)
    else:
        user_id = str(update_message.from_user.id) if update_message.from_user else ""
    # === VIVENTIUM END ===
    if update_message.is_topic_message:
        message_thread_id = update_message.message_thread_id
    else:
        message_thread_id = None
    # === VIVENTIUM START ===
    # Use per-user convo keys for LibreChat to isolate group participants.
    try:
        from config import VIVENTIUM_TELEGRAM_BACKEND
    except Exception:
        VIVENTIUM_TELEGRAM_BACKEND = "librechat"

    if VIVENTIUM_TELEGRAM_BACKEND == "librechat":
        if message_thread_id:
            convo_id = f"{chatid}:{message_thread_id}:{user_id}"
        else:
            convo_id = f"{chatid}:{user_id}"
    else:
        if message_thread_id:
            convo_id = str(chatid) + "_" + str(message_thread_id)
        else:
            convo_id = str(chatid)
    # === VIVENTIUM END ===

    messageid = update_message.message_id

    if update_message.text:
        message = CutNICK(update_message.text, update_message)
        rawtext = update_message.text

    if update_message.reply_to_message:
        reply_to_message_text = update_message.reply_to_message.text
        reply_to_message_file = update_message.reply_to_message.document

        if update_message.reply_to_message.photo:
            photo = update_message.reply_to_message.photo[-1]
            image_url = await get_file_url(photo, context)

        if reply_to_message_file:
            reply_to_message_file_url = await get_file_url(reply_to_message_file, context)
            reply_to_message_file_content = await Document_extract(reply_to_message_file_url, reply_to_message_file_url, None)

    if update_message.photo:
        photo = update_message.photo[-1]

        image_url = await get_file_url(photo, context)

        # === VIVENTIUM START ===
        # Download photo bytes for vision model support
        if getattr(config, "VIVENTIUM_TELEGRAM_FILE_UPLOAD_ENABLED", True):
            logger.info(f"[VIVENTIUM] Attempting to download photo: file_id={photo.file_id}")
            try:
                file_bytes, mime_type, filename = await download_telegram_file(
                    context.bot,
                    photo.file_id,
                    max_bytes=getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760),
                )
                logger.info(f"[VIVENTIUM] Photo download result: bytes={len(file_bytes) if file_bytes else 0}, mime={mime_type}, name={filename}")
                if file_bytes and is_image_mime(mime_type):
                    file_data_list.append(encode_file_for_agent(file_bytes, mime_type, filename))
                    logger.info(f"[VIVENTIUM] Captured photo for agent: {filename}, {mime_type}, size={len(file_bytes)}")
                else:
                    logger.warning(f"[VIVENTIUM] Photo not captured: bytes={bool(file_bytes)}, is_image={is_image_mime(mime_type) if mime_type else False}")
            except Exception as e:
                logger.warning(f"[VIVENTIUM] Failed to capture photo bytes: {e}")
        # === VIVENTIUM END ===

        if update_message.caption:
            message = rawtext = CutNICK(update_message.caption, update_message)

    if voice:
        voice_result = None
        if update_message.voice:
            voice_file_id = update_message.voice.file_id
            voice_result = await get_voice(voice_file_id, context)
        elif update_message.video_note:
            video_note_file_id = update_message.video_note.file_id
            voice_result = await transcribe_video(
                video_note_file_id,
                context,
                media_label="video note",
            )
        elif update_message.video:
            video_file_id = update_message.video.file_id
            voice_result = await transcribe_video(
                video_file_id,
                context,
                media_label="video",
            )

        if voice_result is not None:
            voice_text = voice_result.text
            voice_error_text = voice_result.error_text

            if update_message.caption:
                message = rawtext = CutNICK(update_message.caption, update_message)

    if update_message.document:
        file = update_message.document

        file_url = await get_file_url(file, context)

        if image_url == None and file_url and (file_url[-3:] == "jpg" or file_url[-3:] == "png" or file_url[-4:] == "jpeg"):
            image_url = file_url

        # === VIVENTIUM START ===
        # Download document bytes for agent (images, PDFs, text files)
        if getattr(config, "VIVENTIUM_TELEGRAM_FILE_UPLOAD_ENABLED", True):
            try:
                file_bytes, mime_type, filename = await download_telegram_file(
                    context.bot,
                    file.file_id,
                    max_bytes=getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760),
                    filename_hint=file.file_name,
                    mime_type_hint=getattr(file, "mime_type", None),
                )
                if file_bytes:
                    # Use document's original filename if available
                    doc_filename = file.file_name or filename
                    file_data_list.append(encode_file_for_agent(file_bytes, mime_type, doc_filename))
                    logger.debug(f"Captured document for agent: {doc_filename}, {mime_type}")
            except Exception as e:
                logger.warning(f"Failed to capture document bytes: {e}")
        # === VIVENTIUM END ===

        if update_message.caption:
            message = rawtext = CutNICK(update_message.caption, update_message)

    if update_message.audio:
        file = update_message.audio

        file_url = await get_file_url(file, context)

        if image_url == None and file_url and (file_url[-3:] == "jpg" or file_url[-3:] == "png" or file_url[-4:] == "jpeg"):
            image_url = file_url

        if update_message.caption:
            message = rawtext = CutNICK(update_message.caption, update_message)

    # === VIVENTIUM START ===
    # Return file_data_list for LibreChat agent file upload support
    return message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list
    # === VIVENTIUM END ===

async def GetMesageInfo(update, context, voice=True):
    # === VIVENTIUM START ===
    # Updated to include file_data_list return value
    if update.edited_message:
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list = await GetMesage(update.edited_message, context, voice)
        update_message = update.edited_message
    elif update.callback_query:
        # === VIVENTIUM START ===
        # Feature: Use callback_query.from_user for per-user convo_id resolution.
        callback_user_id = (
            str(update.callback_query.from_user.id)
            if update.callback_query and update.callback_query.from_user
            else None
        )
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list = await GetMesage(
            update.callback_query.message,
            context,
            voice,
            override_user_id=callback_user_id,
        )
        # === VIVENTIUM END ===
        update_message = update.callback_query.message
    elif update.message:
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list = await GetMesage(update.message, context, voice)
        update_message = update.message
    else:
        return None, None, None, None, None, None, None, None, None, None, None, None, None, []
    return message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list
    # === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Lightweight chat/convo ID extraction for callback queries.
# GetMesageInfo is too heavy for button presses (downloads files, extracts
# documents, transcribes voice).  This helper extracts only what the
# Preferences UI needs: chatid, convo_id, message_thread_id.
def get_callback_ids(update):
    """Fast convo_id extraction for callback queries — no file I/O."""
    cq = update.callback_query
    msg = cq.message if cq else None
    if not msg:
        return None, None, None

    chatid = str(msg.chat_id)
    user_id = str(cq.from_user.id) if cq.from_user else ""
    message_thread_id = msg.message_thread_id if getattr(msg, "is_topic_message", False) else None

    try:
        from config import VIVENTIUM_TELEGRAM_BACKEND
    except Exception:
        VIVENTIUM_TELEGRAM_BACKEND = "librechat"

    if VIVENTIUM_TELEGRAM_BACKEND == "librechat":
        if message_thread_id:
            convo_id = f"{chatid}:{message_thread_id}:{user_id}"
        else:
            convo_id = f"{chatid}:{user_id}"
    else:
        convo_id = chatid

    return chatid, convo_id, message_thread_id
# === VIVENTIUM END ===


def safe_get(data, *keys):
    for key in keys:
        try:
            data = data[key] if isinstance(data, (dict, list)) else data.get(key)
        except (KeyError, IndexError, AttributeError, TypeError):
            return None
    return data

def is_emoji(character):
    if len(character) != 1:
        return False

    code_point = ord(character)

    # Define emoji Unicode ranges
    emoji_ranges = [
        (0x1F300, 0x1F5FF),  # Miscellaneous Symbols and Pictographs
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F680, 0x1F6FF),  # Transport and Map Symbols
        (0x2600, 0x26FF),    # Miscellaneous Symbols
        (0x2700, 0x27BF),    # Dingbats
        (0x1F900, 0x1F9FF)   # Supplemental Symbols and Pictographs
    ]

    # Check if character's Unicode code point is in any emoji range
    return any(start <= code_point <= end for start, end in emoji_ranges)
