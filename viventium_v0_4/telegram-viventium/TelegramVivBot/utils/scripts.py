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

def detect_mime_from_path(file_path: str) -> str:
    """Detect MIME type from file path extension."""
    if not file_path:
        return "application/octet-stream"
    ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return EXTENSION_TO_MIME.get(ext, "application/octet-stream")


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
    try:
        if max_bytes is None:
            max_bytes = getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10_485_760)
        # Get file info from Telegram
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
            return None, "", ""

        # Check file size before downloading (if available)
        if hasattr(file, "file_size") and file.file_size and file.file_size > max_bytes:
            logger.warning(f"File too large: {file.file_size} > {max_bytes} bytes")
            return None, "", ""

        # Download file bytes
        file_bytes = await file.download_as_bytearray()
        if not file_bytes:
            logger.warning(f"Downloaded file is empty for file_id={file_id}")
            return None, "", ""

        # Check size after download
        if len(file_bytes) > max_bytes:
            logger.warning(f"Downloaded file too large: {len(file_bytes)} > {max_bytes} bytes")
            return None, "", ""

        # Detect MIME type from hints or file path
        mime_type = (mime_type_hint or "").strip()
        if not mime_type:
            mime_type = detect_mime_from_path(file_path)
        if mime_type == "application/octet-stream" and filename_hint:
            mime_type = detect_mime_from_path(filename_hint)

        # Extract filename from path
        filename = (filename_hint or "").strip()
        if not filename:
            filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path

        logger.debug(f"Downloaded file: {filename}, {len(file_bytes)} bytes, {mime_type}")
        return bytes(file_bytes), mime_type, filename

    except Exception as e:
        logger.warning(f"Failed to download file {file_id}: {e}")
        return None, "", ""


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

async def get_voice(file_id: str, context) -> str:
    """Transcribe a voice message using Whisper (local or API)"""
    logger.info(f"Starting voice transcription for file_id={file_id}")

    try:
        # Download file from Telegram
        logger.debug(f"Downloading file {file_id} from Telegram")
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        logger.debug(f"Downloaded {len(file_bytes)} bytes from Telegram")

        if not file_bytes:
            logger.error("Downloaded file is empty")
            return "error: Downloaded audio file is empty"

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
            return f"error: Transcription timed out after {timeout_s}s"
        finally:
            elapsed = time.monotonic() - start_ts
            logger.info("Transcription elapsed=%.2fs bytes=%d", elapsed, len(file_bytes))
        
        if not transcript or transcript.startswith("error:"):
            logger.warning(f"Transcription failed or returned error: {transcript}")
        else:
            logger.info(f"Transcription successful, length: {len(transcript)} characters")

        return transcript

    except Exception as e:
        logger.exception(f"Exception during voice transcription: {e}")
        return f"error: Temporarily unable to use voice function: {str(e)}"

import os
import sys
import tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def transcribe_video(file_id: str, context) -> str:
    from aient.aient.utils.scripts import extract_audio_from_video, transcribe_audio_file

    try:
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()

        file_ext = os.path.splitext(file.file_path or "")[1]
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

        return transcript

    except Exception as e:
        return f"error: Temporarily unable to process video note: {str(e)}"

async def GetMesage(update_message, context, voice=True, *, override_user_id: Optional[str] = None):
    from aient.aient.utils.scripts import Document_extract
    image_url = None
    file_url = None
    reply_to_message_text = None
    message = None
    rawtext = None
    voice_text = None
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

    if voice and update_message.voice:
        voice = update_message.voice.file_id
        voice_text = await get_voice(voice, context)

        if update_message.caption:
            message = rawtext = CutNICK(update_message.caption, update_message)

    if voice and update_message.video_note:
        video_note = update_message.video_note.file_id
        voice_text = await transcribe_video(video_note, context)

        if update_message.caption:
            message = rawtext = CutNICK(update_message.caption, update_message)

    if voice and update_message.video:
        video = update_message.video.file_id
        voice_text = await transcribe_video(video, context)

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
    return message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list
    # === VIVENTIUM END ===

async def GetMesageInfo(update, context, voice=True):
    # === VIVENTIUM START ===
    # Updated to include file_data_list return value
    if update.edited_message:
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list = await GetMesage(update.edited_message, context, voice)
        update_message = update.edited_message
    elif update.callback_query:
        # === VIVENTIUM START ===
        # Feature: Use callback_query.from_user for per-user convo_id resolution.
        callback_user_id = (
            str(update.callback_query.from_user.id)
            if update.callback_query and update.callback_query.from_user
            else None
        )
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list = await GetMesage(
            update.callback_query.message,
            context,
            voice,
            override_user_id=callback_user_id,
        )
        # === VIVENTIUM END ===
        update_message = update.callback_query.message
    elif update.message:
        message, rawtext, image_url, chatid, messageid, reply_to_message_text, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list = await GetMesage(update.message, context, voice)
        update_message = update.message
    else:
        return None, None, None, None, None, None, None, None, None, None, None, None, []
    return message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list
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
