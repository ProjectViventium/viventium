import re
import sys
import warnings
sys.dont_write_bytecode = True
# Suppress non-critical warnings from third-party libraries
warnings.filterwarnings("ignore", category=SyntaxWarning, module="md2tgmd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telegram.ext._application")
import base64
import time
import uuid
import logging
import traceback
import utils.decorators as decorators
from typing import Any, Optional
from datetime import datetime, timezone

from md2tgmd.src.md2tgmd import escape, split_code, replace_all
from io import BytesIO
from aient.aient.utils.scripts import Document_extract
from aient.aient.core.utils import get_engine  # Still needed for document extraction
# REMOVED: get_image_message, get_text_message - Not used with LiveKit Bridge
import config
from config import (
    WEB_HOOK,
    PORT,
    BOT_TOKEN,
    Users,
    PREFERENCES,
    RESET_TIME,
    get_robot,
    reset_ENGINE,
    update_info_message,
    update_menu_buttons,
    update_first_buttons_message,
    get_telegram_call_link_result,
    get_telegram_call_url,
    CONNECTION_POOL_SIZE,
    GET_UPDATES_CONNECTION_POOL_SIZE,
    TIMEOUT,
    CONCURRENT_UPDATES,
    POLLING_TIMEOUT,
    # REMOVED: Model-related imports - Model selection handled by Viventium
    # REMOVED: Model/Plugin-related imports - Model selection and plugins handled by Viventium
    # GET_MODELS, PLUGINS, remove_no_text_model, update_initial_model,
    # update_models_buttons, get_all_available_models, get_model_groups,
    # CUSTOM_MODELS_LIST, MODEL_GROUPS, get_initial_model
)

# REMOVED: i18n - Using hardcoded English strings for simplicity
from utils.scripts import GetMesageInfo, safe_get, is_emoji
from utils.tts import synthesize_speech
from utils.livekit_bridge import LiveKitBridge
# === VIVENTIUM START ===
# Feature: Centralized voice reply gating helper.
from utils.voice import should_send_voice_reply
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Feature: Telegram account linking flow + citation-safe formatting helpers.
from utils.librechat_bridge import (
    TelegramLinkRequired,
    render_telegram_markdown,
    sanitize_telegram_text,
    is_no_response_only,
    strip_trailing_nta,
)
from utils.telegram_html import strip_html_tags
from utils.librechat_attachments import (
    fetch_librechat_bytes,
    send_librechat_attachments,
)

# === VIVENTIUM START ===
# Feature: Markdown stripping for plain-text fallback.
# Preserves paragraph breaks (\n\n) for readability instead of collapsing everything.
def _strip_telegram_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[\*_~]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\\([_*\[\]()~`>#+\-=|{}.!])", r"\1", cleaned)
    return cleaned.strip()
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Suppress placeholder "thinking" chunks in Telegram streams.
def _is_placeholder_chunk(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    normalized = " ".join(text.lower().strip().split())
    if not normalized:
        return False
    placeholder_phrases = {
        "thinking",
        "thinking...",
        "one moment",
        "one moment...",
        "hang on",
        "hang on...",
        "working on it",
        "working on it...",
        "checking",
        "checking...",
        "loading",
        "loading...",
    }
    if normalized in placeholder_phrases:
        return True
    if normalized.endswith("...") and len(normalized) <= 20 and normalized.replace(".", "").isalpha():
        return True
    # Handle Unicode ellipsis (…)
    if normalized.endswith("…") and len(normalized) <= 20:
        return True
    return False
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Strip leading placeholder phrases so only real content remains.
_PLACEHOLDER_PREFIX_RE = re.compile(
    # Only strip when it's clearly a meta-prefix (ex: "Thinking: ..."), not a normal sentence
    # like "Checking now." which is a deliberate hold message for tool/brewing flows.
    r"^(thinking|one moment|hang on|working on it|checking|loading)\\s*(?:[:\\-–—])\\s*",
    re.IGNORECASE,
)

def _strip_placeholder_prefix(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    stripped = text.strip()
    match = _PLACEHOLDER_PREFIX_RE.match(stripped)
    if not match:
        return text
    remainder = stripped[match.end():].lstrip()
    return remainder
# === VIVENTIUM END ===
# === VIVENTIUM END ===

from telegram.constants import ChatAction
from telegram import BotCommand, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, ApplicationBuilder, filters, CallbackQueryHandler, Application, AIORateLimiter, ContextTypes
from datetime import timedelta

import asyncio
lock = asyncio.Lock()
event = asyncio.Event()
stop_event = asyncio.Event()
# Use configurable timeout from config.py (default: 30 seconds for small deployments)
from config import TIMEOUT as time_out, POLLING_TIMEOUT

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.posthog").setLevel(logging.WARNING)
logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)

# === VIVENTIUM START ===
# Feature: Telegram timing logs (optional per-request instrumentation).
def _tg_timing_enabled() -> bool:
    return bool(getattr(config, "VIVENTIUM_TELEGRAM_TIMING_ENABLED", False))


def _tg_timing_log(trace_id: str, step: str, start_ts: float, extra: str | None = None) -> None:
    if not _tg_timing_enabled():
        return
    elapsed_ms = (time.monotonic() - start_ts) * 1000.0
    if extra:
        logger.info("[TG_TIMING] trace=%s step=%s ms=%.1f %s", trace_id, step, elapsed_ms, extra)
    else:
        logger.info("[TG_TIMING] trace=%s step=%s ms=%.1f", trace_id, step, elapsed_ms)

# Feature: Deep timing logs for microstep analysis (toggleable).
def _tg_deep_enabled() -> bool:
    return bool(getattr(config, "VIVENTIUM_TELEGRAM_TIMING_DEEP", False))


def _tg_deep_log(
    trace_id: str,
    step: str,
    start_ts: float,
    base_ts: Optional[float] = None,
    extra: Optional[str] = None,
) -> None:
    if not _tg_deep_enabled():
        return
    now = time.monotonic()
    elapsed_ms = (now - start_ts) * 1000.0
    suffix_parts = []
    if base_ts is not None:
        suffix_parts.append(f"t={((now - base_ts) * 1000.0):.1f}")
    if extra:
        suffix_parts.append(extra)
    suffix = (" " + " ".join(suffix_parts)) if suffix_parts else ""
    logger.info(
        "[TG_TIMING][deep][tg] trace=%s step=%s ms=%.1f%s",
        trace_id,
        step,
        elapsed_ms,
        suffix,
    )


def _tg_deep_log_value(
    trace_id: str,
    step: str,
    value_ms: float,
    base_ts: Optional[float] = None,
    extra: Optional[str] = None,
) -> None:
    if not _tg_deep_enabled():
        return
    suffix_parts = []
    if base_ts is not None:
        suffix_parts.append(f"t={((time.monotonic() - base_ts) * 1000.0):.1f}")
    if extra:
        suffix_parts.append(extra)
    suffix = (" " + " ".join(suffix_parts)) if suffix_parts else ""
    logger.info(
        "[TG_TIMING][deep][tg] trace=%s step=%s ms=%.1f%s",
        trace_id,
        step,
        value_ms,
        suffix,
    )


# === VIVENTIUM START ===
# Feature: Canonical proactive Telegram delivery for follow-ups/scheduled messages.
# Purpose: Keep text as the primary artifact and voice additive, matching the main reply path.
async def deliver_proactive_telegram_message(
    bot: Any,
    *,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    voice_audio: Optional[bytes] = None,
) -> None:
    rendered = ""
    effective_parse_mode: Optional[str] = None

    # Keep proactive formatting aligned with the main Telegram reply path.
    if parse_mode == "HTML":
        rendered = text
        effective_parse_mode = "HTML"
    elif parse_mode == "MarkdownV2":
        rendered = render_telegram_markdown(text)
        effective_parse_mode = "HTML"
    elif parse_mode:
        rendered = sanitize_telegram_text(text)
        effective_parse_mode = parse_mode
    else:
        rendered = _strip_telegram_markdown(sanitize_telegram_text(text))

    if rendered:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=rendered,
                parse_mode=effective_parse_mode,
            )
        except Exception as exc:
            if effective_parse_mode and "parse entities" in str(exc):
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        strip_html_tags(rendered)
                        if effective_parse_mode == "HTML"
                        else _strip_telegram_markdown(sanitize_telegram_text(text))
                    ),
                )
            else:
                raise

    if voice_audio:
        try:
            audio_stream = BytesIO(voice_audio)
            audio_stream.name = "Voice"
            audio_stream.seek(0)
            await bot.send_audio(
                chat_id=chat_id,
                audio=audio_stream,
                title="Voice",
            )
        except Exception as exc:
            logger.warning(
                "Failed to deliver proactive voice message to %s after text send: %s",
                chat_id,
                exc,
            )
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: LibreChat attachment delivery is implemented in `utils/librechat_attachments.py`.
# Keep bot.py focused on orchestration and Telegram UI behavior.
# === VIVENTIUM END ===

class SpecificStringFilter(logging.Filter):
    def __init__(self, specific_string):
        super().__init__()
        self.specific_string = specific_string

    def filter(self, record):
        return self.specific_string not in record.getMessage()

specific_string = "httpx.RemoteProtocolError: Server disconnected without sending a response."
my_filter = SpecificStringFilter(specific_string)

update_logger = logging.getLogger("telegram.ext.Updater")
update_logger.addFilter(my_filter)
update_logger = logging.getLogger("root")
update_logger.addFilter(my_filter)

# Define a cache to store messages
from collections import defaultdict
message_cache = defaultdict(lambda: [])
time_stamps = defaultdict(lambda: [])

@decorators.GroupAuthorization
@decorators.Authorization
@decorators.APICheck
async def command_bot(update, context, title="", has_command=True):
    stop_event.clear()
    # === VIVENTIUM START ===
    # Feature: Timing hooks for Telegram request lifecycle.
    request_start_ts = time.monotonic()
    # === VIVENTIUM END ===
    # === VIVENTIUM START ===
    # Updated to capture file_data_list for LibreChat agent file upload
    message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list = await GetMesageInfo(update, context)
    # === VIVENTIUM END ===
    # === VIVENTIUM START ===
    trace_id = f"tg-{chatid}-{messageid}-{uuid.uuid4().hex[:6]}"
    _tg_timing_log(trace_id, "get_message_info", request_start_ts)
    # === VIVENTIUM START ===
    # Deep timing: capture Telegram update lag and message metadata.
    if _tg_deep_enabled() and update_message and update_message.date:
        try:
            msg_time = update_message.date
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=timezone.utc)
            lag_ms = (datetime.now(timezone.utc) - msg_time).total_seconds() * 1000.0
            _tg_deep_log_value(
                trace_id,
                "telegram_update_lag",
                lag_ms,
                base_ts=request_start_ts,
                extra=f"chat_id={chatid}",
            )
        except Exception:
            pass
    _tg_deep_log(
        trace_id,
        "message_info_done",
        request_start_ts,
        base_ts=request_start_ts,
        extra=(
            f"voice_note={int(bool(update_message and (update_message.voice or update_message.video_note or update_message.audio)))} "
            f"files={len(file_data_list) if file_data_list else 0}"
        ),
    )
    # === VIVENTIUM END ===
    # === VIVENTIUM END ===
    voice_note_detected = bool(update_message and (update_message.voice or update_message.video_note or update_message.audio))

    if has_command == False or len(context.args) > 0:
        if has_command:
            message = ' '.join(context.args)
        # REMOVED: pass_history - Not used by LiveKit Bridge, Viventium handles conversation history
        
        # Handle voice note transcription
        if message == None and voice_text:
            transcription_display = f"🎤 Transcription:\n> {voice_text}"
            escaped_display = escape(transcription_display, italic=False)
            if len(escaped_display) <= 4096:
                await context.bot.send_message(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    text=escaped_display,
                    parse_mode='MarkdownV2',
                    reply_to_message_id=messageid,
                )
            else:
                preview_text = voice_text[:3500] + "…" if len(voice_text) > 3500 else voice_text
                preview_display = f"🎤 Transcription (preview):\n> {preview_text}"
                await context.bot.send_message(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    text=escape(preview_display, italic=False),
                    parse_mode='MarkdownV2',
                    reply_to_message_id=messageid,
                )
                transcript_io = BytesIO(voice_text.encode('utf-8'))
                transcript_io.name = 'transcription.txt'
                transcript_io.seek(0)
                await context.bot.send_document(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    document=transcript_io,
                    filename='transcription.txt',
                    reply_to_message_id=messageid,
                )
            # === VIVENTIUM START ===
            # Voice mode metadata is passed to LibreChat; keep the user text clean.
            message = voice_text
            # === VIVENTIUM END ===
        elif message == None:
            message = voice_text
            
        if message and len(message) == 1 and is_emoji(message):
            return

        message_has_nick = False
        botNick = config.NICK.lower() if config.NICK else None
        if rawtext and rawtext.split()[0].lower() == botNick:
            message_has_nick = True

        if message_has_nick and update_message.reply_to_message and update_message.reply_to_message.caption and not message:
            message = update_message.reply_to_message.caption

        if message:
            # REMOVED: pass_history check - Not used by LiveKit Bridge, Viventium handles conversation history
            # Always schedule cleanup task
            # Remove existing task (if any)
            remove_job_if_exists(convo_id, context)
            # Add new scheduled task
            context.job_queue.run_once(
                scheduled_function,
                    when=timedelta(seconds=RESET_TIME),
                    chat_id=chatid,
                    name=convo_id
                )

            bot_info_username = None
            try:
                bot_info = await context.bot.get_me(read_timeout=time_out, write_timeout=time_out, connect_timeout=time_out, pool_timeout=time_out)
                bot_info_username = bot_info.username
            except Exception as e:
                bot_info_username = update_message.reply_to_message.from_user.username
                logger.error(f"Error getting bot info: {e}")

            if update_message.reply_to_message \
            and update_message.from_user.is_bot == False \
            and (update_message.reply_to_message.from_user.username == bot_info_username or message_has_nick):
                # REMOVED: TITLE preference check - Not needed, always include reply context
                if reply_to_message_text:
                    message = message + "\n" + reply_to_message_text
                if reply_to_message_file_content:
                    message = message + "\n" + reply_to_message_file_content
            elif update_message.reply_to_message and update_message.reply_to_message.from_user.is_bot \
            and update_message.reply_to_message.from_user.username != bot_info_username:
                return

            robot, _, api_key, api_url = get_robot(convo_id)  # api_key/api_url only for residual features
            # REMOVED: engine - Model selection handled by Viventium

            if Users.get_config(convo_id, "LONG_TEXT"):
                async with lock:
                    message_cache[convo_id].append(message)
                    time_stamps[convo_id].append(time.time())
                    if len(message_cache[convo_id]) == 1:
                        logger.debug(f"First message len: {len(message_cache[convo_id][0])}")
                        if len(message_cache[convo_id][0]) > 800:
                            event.clear()
                        else:
                            event.set()
                    else:
                        return
                try:
                    # === VIVENTIUM START ===
                    # Feature: Keep LONG_TEXT merge window short for faster first-token latency.
                    long_text_wait_s = getattr(config, "VIVENTIUM_TELEGRAM_LONG_TEXT_WAIT_S", 0.35) or 0.35
                    try:
                        long_text_wait_s = float(long_text_wait_s)
                    except Exception:
                        long_text_wait_s = 0.35
                    long_text_wait_s = max(0.0, min(long_text_wait_s, 2.0))
                    if long_text_wait_s > 0:
                        await asyncio.wait_for(event.wait(), timeout=long_text_wait_s)
                    # === VIVENTIUM END ===
                except asyncio.TimeoutError:
                    logger.debug("asyncio.wait timeout!")

                intervals = [
                    time_stamps[convo_id][i] - time_stamps[convo_id][i - 1]
                    for i in range(1, len(time_stamps[convo_id]))
                ]
                if intervals:
                    logger.debug(f"Chat ID {convo_id} time intervals: {intervals}, total time: {sum(intervals)}")

                message = "\n".join(message_cache[convo_id])
                message_cache[convo_id] = []
                time_stamps[convo_id] = []
            # REMOVED: TITLE preference - Not needed, title is always None with LiveKit Bridge
            # REMOVED: REPLY preference - LiveKit Bridge handles message threading automatically

            # === VIVENTIUM START ===
            # Optional: Text extraction fallback for files when vision/file support is unavailable.
            if getattr(config, "VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK", False) and (image_url or file_url):
                engine = Users.get_config(convo_id, "engine")
                engine_type, _ = get_engine({"base_url": api_url}, endpoint=None, original_model=engine)
                try:
                    extracted_text = await Document_extract(file_url, image_url, engine_type)
                except Exception as e:
                    extracted_text = None
                    logger.warning(f"[VIVENTIUM] Document_extract failed: {e}")

                if extracted_text:
                    if message:
                        message = f"{extracted_text}\n{message}"
                    else:
                        message = extracted_text
            # === VIVENTIUM END ===

            # Prepend sender name for group chats to provide identity context
            if update_message.chat.type in ['group', 'supergroup']:
                sender_name = update_message.from_user.first_name
                # Clean name to avoid Markdown conflicts if needed, but simple prepend is usually safe
                # We use a clear format "Name: Message" (Standard script format, no brackets to avoid LLM confusion)
                message = f"{sender_name}: {message}"

            # REMOVED: api_key, api_url, engine, pass_history parameters - Not used with LiveKit Bridge
            # === VIVENTIUM START ===
            # Pass file_data_list for LibreChat agent file upload support
            if file_data_list:
                logger.info(f"[VIVENTIUM] Sending {len(file_data_list)} file(s) to agent: {[f.get('filename', 'unknown') for f in file_data_list]}")
            await getViventiumResponse(
                update_message,
                context,
                title,
                robot,
                message,
                chatid,
                messageid,
                convo_id,
                message_thread_id,
                voice_note_detected=voice_note_detected,
                files=file_data_list,
                trace_id=trace_id,
                telegram_message_id=messageid,
                telegram_update_id=getattr(update, "update_id", None),
            )
            _tg_timing_log(trace_id, "request_complete", request_start_ts)
            _tg_deep_log(trace_id, "request_complete", request_start_ts, base_ts=request_start_ts)
            # === VIVENTIUM END ===
    else:
        message = await context.bot.send_message(
            chat_id=chatid,
            message_thread_id=message_thread_id,
            text=escape("Please enter text after the command"),
            parse_mode='MarkdownV2',
            reply_to_message_id=messageid,
        )

async def delete_message(update, context, messageid = [], delay=60):
    await asyncio.sleep(delay)
    if isinstance(messageid, list):
        for mid in messageid:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=mid)
            except Exception as e:
                pass

from telegram.error import Forbidden, TelegramError
async def is_bot_blocked(bot, user_id: int) -> bool:
    try:
        # Attempt to send a test message to the user
        await bot.send_chat_action(chat_id=user_id, action="typing")
        return False  # If successfully sent, the bot is not blocked
    except Forbidden:
        logger.warning(f"Bot has been blocked by user {user_id}")
        return True  # If Forbidden error received, the bot is blocked
    except TelegramError:
        # Handle other possible errors
        return False  # If other error, assume bot is not blocked

async def getViventiumResponse(
    update_message,
    context,
    title,
    robot,
    message,
    chatid,
    messageid,
    convo_id,
    message_thread_id,
    voice_note_detected=False,
    files=None,
    trace_id=None,
    telegram_message_id=None,
    telegram_update_id=None,
):
    # REMOVED: api_key, api_url, engine parameters - Not used with LiveKit Bridge
    # === VIVENTIUM START ===
    # Added: files parameter for LibreChat agent file upload support
    # === VIVENTIUM END ===
    """
    Simplified chat handler - sends text to LiveKit Bridge, which forwards to Viventium.
    All model selection, system prompts, plugins, etc. are handled by Viventium.
    Files (images, documents) are passed to the agent for vision model processing.
    """
    lastresult = title or ""
    # Ensure message is a string (not a list from broken image formatting)
    if message is None:
        text = ""
    elif isinstance(message, list):
        # Extract text from list if it exists
        text = " ".join([str(m) for m in message if isinstance(m, str)])
        logger.warning("Received list message, extracting text only. Image support not available with LiveKit Bridge.")
    else:
        text = str(message)
    
    result = ""
    tmpresult = ""
    time_out = 600
    image_has_send = 0
    # === VIVENTIUM START ===
    # Feature: Track per-request timing for Telegram responses.
    if not trace_id:
        trace_id = f"tg-{chatid}-{messageid}-{uuid.uuid4().hex[:6]}"
    response_start_ts = time.monotonic()
    # === VIVENTIUM END ===
    
    # REMOVED: Model selection, system prompt, plugins, language, API keys
    # All of these are handled by Viventium, not the bot
    # REMOVED: Model-specific logic (-web suffix, frequency modifications)
    # REMOVED: Memory manager injection (LiveKitBridge doesn't have this)
    # REMOVED: Voice note system prompt injection (Viventium handles this)
    
    # === VIVENTIUM START ===
    # Feature: OpenClaw-style time-based stream throttling (coalesced previews).
    stream_edit_interval_s = getattr(config, "VIVENTIUM_TELEGRAM_STREAM_EDIT_INTERVAL_S", 0.35) or 0.35
    try:
        stream_edit_interval_s = float(stream_edit_interval_s)
    except Exception:
        stream_edit_interval_s = 0.35
    stream_edit_interval_s = max(0.1, min(stream_edit_interval_s, 3.0))
    # === VIVENTIUM END ===

    if await is_bot_blocked(context.bot, chatid):
        return

    answer_messageid = None
    # === VIVENTIUM START ===
    # Feature: Use Telegram typing indicator instead of "thinking" message.
    typing_stop = asyncio.Event()

    async def _typing_loop():
        interval = getattr(config, "VIVENTIUM_TELEGRAM_TYPING_INTERVAL_S", 4.0) or 4.0
        typing_kwargs = {}
        if message_thread_id is not None:
            typing_kwargs["message_thread_id"] = message_thread_id
        while not typing_stop.is_set():
            try:
                await context.bot.send_chat_action(
                    chat_id=chatid,
                    action=ChatAction.TYPING,
                    **typing_kwargs,
                )
            except Exception as e:
                logger.debug("Typing indicator failed: %s", e)
            try:
                await asyncio.wait_for(typing_stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    typing_task = None
    typing_task = asyncio.create_task(_typing_loop())
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Use Telegram sender identity for LibreChat account linking.
    telegram_user_id = str(update_message.from_user.id) if update_message.from_user else ""
    telegram_username = update_message.from_user.username if update_message.from_user else ""

    # Voice vs text surface formatting (voice mode = no markdown).
    voice_mode = bool(voice_note_detected)
    # === VIVENTIUM START ===
    _tg_timing_log(
        trace_id,
        "response_start",
        response_start_ts,
        extra=f"voice={int(voice_mode)} files={len(files) if files else 0}",
    )
    _tg_deep_log(
        trace_id,
        "response_start",
        response_start_ts,
        base_ts=response_start_ts,
        extra=f"voice={int(voice_mode)} files={len(files) if files else 0}",
    )
    # === VIVENTIUM END ===
    # Feature: Pass per-chat timezone when available for accurate time context.
    client_timezone = Users.get_config(chatid, "CLIENT_TIMEZONE") if Users else ""
    if isinstance(client_timezone, str):
        client_timezone = client_timezone.strip()
    else:
        client_timezone = ""
    # === VIVENTIUM START ===
    # Feature: Fallback to deployment default timezone when per-chat value is empty.
    if not client_timezone:
        fallback_timezone = getattr(config, "VIVENTIUM_TELEGRAM_DEFAULT_TIMEZONE", "")
        if isinstance(fallback_timezone, str):
            fallback_timezone = fallback_timezone.strip()
        else:
            fallback_timezone = ""
        if fallback_timezone:
            client_timezone = fallback_timezone
    # === VIVENTIUM END ===

    def _render_telegram_response(text: str):
        # === VIVENTIUM NOTE ===
        # Fix: Always render HTML for text display, even when input was a voice note.
        # Voice-note input should NOT degrade text readability.
        # TTS synthesis has its own sanitization path (prepare_tts_text in tts.py).
        return render_telegram_markdown(text), "HTML"
        # === VIVENTIUM NOTE END ===
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: No-response tag ({NTA}) should never be delivered to Telegram users.
    # We guard during streaming so `{NTA}` doesn't flash as a visible message before suppression.
    def _is_no_response_tag_prefix(text: str) -> bool:
        if not isinstance(text, str):
            return False
        trimmed = text.strip()
        if not trimmed:
            return True
        canonical = "{NTA}"
        if len(trimmed) > len(canonical):
            return False
        return canonical.lower().startswith(trimmed.lower())
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Create the response message lazily once we have content.
    async def _ensure_answer_message(rendered_text, parse_mode, *, fallback_text=None):
        nonlocal answer_messageid, lastresult
        if answer_messageid:
            return answer_messageid
        send_kwargs = {
            "chat_id": chatid,
            "message_thread_id": message_thread_id,
            "text": rendered_text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
            "read_timeout": time_out,
            "write_timeout": time_out,
            "pool_timeout": time_out,
            "connect_timeout": time_out,
            "reply_to_message_id": messageid,
        }
        try:
            send_start_ts = time.monotonic() if _tg_deep_enabled() else None
            msg = await context.bot.send_message(**send_kwargs)
            if send_start_ts is not None:
                _tg_deep_log(
                    trace_id,
                    "telegram_send_text",
                    send_start_ts,
                    base_ts=response_start_ts,
                    extra=f"len={len(rendered_text) if rendered_text else 0}",
                )
        except Exception as e:
            if parse_mode and "parse entities" in str(e):
                if fallback_text is not None:
                    safe_text = fallback_text
                elif parse_mode == "HTML":
                    safe_text = strip_html_tags(rendered_text)
                else:
                    safe_text = _strip_telegram_markdown(sanitize_telegram_text(rendered_text))
                send_start_ts = time.monotonic() if _tg_deep_enabled() else None
                msg = await context.bot.send_message(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    text=safe_text,
                    disable_web_page_preview=True,
                    read_timeout=time_out,
                    write_timeout=time_out,
                    pool_timeout=time_out,
                    connect_timeout=time_out,
                    reply_to_message_id=messageid,
                )
                if send_start_ts is not None:
                    _tg_deep_log(
                        trace_id,
                        "telegram_send_text",
                        send_start_ts,
                        base_ts=response_start_ts,
                        extra=f"len={len(safe_text) if safe_text else 0} mode=fallback",
                    )
            else:
                raise
        answer_messageid = msg.message_id
        lastresult = rendered_text
        typing_stop.set()
        return answer_messageid
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Coalesced non-blocking stream edits (keeps token ingestion hot).
    stream_preview_pending: Optional[dict[str, Any]] = None
    stream_preview_task: Optional[asyncio.Task] = None
    stream_preview_lock = asyncio.Lock()
    stream_preview_last_sent_ts = 0.0

    async def _apply_stream_preview(preview: dict[str, Any]) -> None:
        nonlocal answer_messageid, lastresult, stream_preview_last_sent_ts
        rendered_text = str(preview.get("rendered_text") or "")
        parse_mode = preview.get("parse_mode")
        fallback_text = preview.get("fallback_text")
        if not rendered_text or lastresult == rendered_text:
            return
        if answer_messageid is None:
            await _ensure_answer_message(
                rendered_text,
                parse_mode,
                fallback_text=fallback_text,
            )
            stream_preview_last_sent_ts = time.monotonic()
            return
        try:
            edit_start_ts = time.monotonic() if _tg_deep_enabled() else None
            await context.bot.edit_message_text(
                chat_id=chatid,
                message_id=answer_messageid,
                text=rendered_text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
                read_timeout=time_out,
                write_timeout=time_out,
                pool_timeout=time_out,
                connect_timeout=time_out,
            )
            if edit_start_ts is not None:
                _tg_deep_log(
                    trace_id,
                    "telegram_stream_edit",
                    edit_start_ts,
                    base_ts=response_start_ts,
                    extra=f"len={len(rendered_text)}",
                )
            lastresult = rendered_text
            stream_preview_last_sent_ts = time.monotonic()
        except Exception as e:
            if parse_mode and "parse entities" in str(e):
                if fallback_text is not None:
                    fallback = fallback_text
                elif parse_mode == "HTML":
                    fallback = strip_html_tags(rendered_text)
                else:
                    fallback = _strip_telegram_markdown(sanitize_telegram_text(rendered_text))
                fallback_start_ts = time.monotonic() if _tg_deep_enabled() else None
                await context.bot.edit_message_text(
                    chat_id=chatid,
                    message_id=answer_messageid,
                    text=fallback,
                    disable_web_page_preview=True,
                    read_timeout=time_out,
                    write_timeout=time_out,
                    pool_timeout=time_out,
                    connect_timeout=time_out,
                )
                if fallback_start_ts is not None:
                    _tg_deep_log(
                        trace_id,
                        "telegram_stream_edit",
                        fallback_start_ts,
                        base_ts=response_start_ts,
                        extra=f"len={len(fallback)} mode=fallback",
                    )
                lastresult = rendered_text
                stream_preview_last_sent_ts = time.monotonic()
            else:
                raise

    async def _drain_stream_previews() -> None:
        nonlocal stream_preview_pending, stream_preview_task, stream_preview_last_sent_ts
        try:
            while True:
                async with stream_preview_lock:
                    preview = stream_preview_pending
                    stream_preview_pending = None
                    if preview is None:
                        return
                force_flush = bool(preview.get("force"))
                if not force_flush and stream_preview_last_sent_ts > 0:
                    elapsed_s = time.monotonic() - stream_preview_last_sent_ts
                    if elapsed_s < stream_edit_interval_s:
                        await asyncio.sleep(stream_edit_interval_s - elapsed_s)
                await _apply_stream_preview(preview)
        finally:
            async with stream_preview_lock:
                if stream_preview_task is asyncio.current_task():
                    stream_preview_task = None

    async def _queue_stream_preview(
        rendered_text: str,
        parse_mode: Optional[str],
        *,
        fallback_text: Optional[str] = None,
        force: bool = False,
    ) -> None:
        nonlocal stream_preview_pending, stream_preview_task
        if not rendered_text:
            return
        async with stream_preview_lock:
            prev_force = bool(stream_preview_pending.get("force")) if stream_preview_pending else False
            stream_preview_pending = {
                "rendered_text": rendered_text,
                "parse_mode": parse_mode,
                "fallback_text": fallback_text,
                "force": bool(force or prev_force),
            }
            if stream_preview_task is None or stream_preview_task.done():
                stream_preview_task = asyncio.create_task(_drain_stream_previews())

    async def _flush_stream_previews() -> None:
        nonlocal stream_preview_task
        while True:
            async with stream_preview_lock:
                task = stream_preview_task
                if task and task.done():
                    stream_preview_task = None
                    task = None
            if not task:
                return
            await asyncio.gather(task, return_exceptions=True)

    async def _cancel_stream_previews() -> None:
        nonlocal stream_preview_pending, stream_preview_task
        async with stream_preview_lock:
            stream_preview_pending = None
            task = stream_preview_task
            stream_preview_task = None
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.gather(task, return_exceptions=True)
            except Exception:
                pass
    # === VIVENTIUM END ===

    try:
        # Simplified: Only send text and convo_id to bridge
        # All other parameters (model, language, system_prompt, plugins, api_key, api_url, pass_history) are ignored by LiveKitBridge
        # === VIVENTIUM START ===
        # Pass files for vision model support + message timestamp for time context
        message_timestamp = update_message.date.isoformat() if update_message and update_message.date else None
        stream_start_ts = time.monotonic()
        _tg_deep_log(
            trace_id,
            "lc_stream_start",
            stream_start_ts,
            base_ts=response_start_ts,
            extra=f"convo_id={convo_id}",
        )
        first_chunk_logged = False
        # === VIVENTIUM START ===
        # Feature: Capture LibreChat attachment events (files/images) for Telegram delivery.
        lc_attachments: list[dict[str, Any]] = []
        # === VIVENTIUM END ===
        async for data in robot.ask_stream_async(
            text,
            convo_id=convo_id,
            telegram_chat_id=chatid,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_message_id=telegram_message_id,
            telegram_update_id=telegram_update_id,
            voice_mode=voice_mode,
            input_mode="voice_note" if voice_mode else "text",
            files=files if files else None,  # File data for vision models
            message_timestamp=message_timestamp,  # Time context for scheduling
            client_timezone=client_timezone,  # Timezone for time context formatting
            trace_id=trace_id,
        ):
        # === VIVENTIUM END ===
            # === VIVENTIUM START ===
            # If the bridge emits structured events (e.g., attachments), capture them and continue.
            if isinstance(data, dict):
                if data.get("type") == "attachment":
                    attachment = data.get("attachment")
                    if isinstance(attachment, dict):
                        lc_attachments.append(attachment)
                continue
            # === VIVENTIUM END ===
            if stop_event.is_set() and convo_id == target_convo_id and answer_messageid and answer_messageid < reset_mess_id:
                return
            if not first_chunk_logged:
                _tg_timing_log(trace_id, "stream_first_chunk", stream_start_ts)
                _tg_deep_log(trace_id, "stream_first_chunk", stream_start_ts, base_ts=response_start_ts)
                first_chunk_logged = True
            if "message_search_stage_" not in data:
                # === VIVENTIUM START ===
                # Skip placeholder "thinking" chunks so Telegram only shows real content.
                if not result:
                    data = _strip_placeholder_prefix(data)
                    if not data or _is_placeholder_chunk(data):
                        logger.debug("Skipping placeholder chunk: %s", data)
                        continue
                # === VIVENTIUM END ===
                result = result + data
                # === VIVENTIUM START ===
                # Feature: No-response tag ({NTA}) suppression for direct Telegram replies.
                if answer_messageid is None and _is_no_response_tag_prefix(result):
                    continue
                # === VIVENTIUM END ===
            image_match = re.search(r"!\[image\]\(data:image\/png;base64,([a-zA-Z0-9+/=]+)\)", result)
            if image_match and image_has_send == 0:
                base64_str = image_match.group(1)
                try:
                    img_url = base64.b64decode(base64_str)
                    media_group = []
                    media_group.append(InputMediaPhoto(media=img_url))
                    await context.bot.send_media_group(
                        chat_id=chatid,
                        media=media_group,
                        message_thread_id=message_thread_id,
                        reply_to_message_id=messageid,
                    )
                    result = result.replace(image_match.group(0), "")
                    image_has_send = 1
                except Exception as e:
                    logger.warning(f"Could not process base64 image: {e}")
                continue
            tmpresult = result
            if re.sub(r"```", '', result.split("\n")[-1]).count("`") % 2 != 0:
                tmpresult = result + "`"
            if sum([line.strip().startswith("```") for line in result.split('\n')]) % 2 != 0:
                tmpresult = tmpresult + "\n```"
            tmpresult = (title or "") + tmpresult
            # REMOVED: message_search_stage_ strings - Web search plugin removed
            if "message_search_stage_" in data:
                tmpresult = "🌐 Processing..."  # Placeholder for removed search stages
            split_len = 3500
            if len(tmpresult) > split_len and Users.get_config(convo_id, "LONG_TEXT_SPLIT"):
                # === VIVENTIUM START ===
                # Feature: Preserve ordering by flushing pending stream edits before split rotation.
                await _flush_stream_previews()
                # === VIVENTIUM END ===

                replace_text = replace_all(tmpresult, r"(```[\D\d\s]+?```)", split_code)
                if "@|@|@|@" in replace_text:
                    logger.debug(f"Found code split marker in response")
                    split_messages = replace_text.split("@|@|@|@")
                    send_split_message = split_messages[0]
                    result = split_messages[1][:-4]
                else:
                    logger.debug(f"Processing replace_text (length: {len(replace_text)})")
                    if replace_text.strip().endswith("```"):
                        replace_text = replace_text.strip()[:-4]
                    split_messages_new = []
                    split_messages = replace_text.split("```")
                    for index, item in enumerate(split_messages):
                        if index % 2 == 1:
                            item = "```" + item
                            if index != len(split_messages) - 1:
                                item = item + "```"
                            split_messages_new.append(item)
                        if index % 2 == 0:
                            item_split_new = []
                            item_split = item.split("\n\n")
                            for sub_index, sub_item in enumerate(item_split):
                                if sub_index % 2 == 1:
                                    sub_item = "\n\n" + sub_item
                                    if sub_index != len(item_split) - 1:
                                        sub_item = sub_item + "\n\n"
                                    item_split_new.append(sub_item)
                                if sub_index % 2 == 0:
                                    item_split_new.append(sub_item)
                            split_messages_new.extend(item_split_new)

                    split_index = 0
                    for index, _ in enumerate(split_messages_new):
                        if len("".join(split_messages_new[:index])) < split_len:
                            split_index += 1
                            continue
                        else:
                            break
                    send_split_message = ''.join(split_messages_new[:split_index])
                    matches = re.findall(r"(```.*?\n)", send_split_message)
                    if len(matches) % 2 != 0:
                        send_split_message = send_split_message + "```\n"
                    tmp = ''.join(split_messages_new[split_index:])
                    if tmp.strip().endswith("```"):
                        result = tmp[:-4]
                    else:
                        result = tmp
                    matches = re.findall(r"(```.*?\n)", send_split_message)
                    result_matches = re.findall(r"(```.*?\n)", result)
                    if len(result_matches) > 0 and result_matches[0].startswith("```\n") and len(result_matches) >= 2:
                        result = matches[-2] + result

                title = ""
                rendered_split, split_parse_mode = _render_telegram_response(send_split_message)
                if lastresult != rendered_split:
                    if answer_messageid is None:
                        await _ensure_answer_message(
                            rendered_split,
                            split_parse_mode,
                            fallback_text=_strip_telegram_markdown(sanitize_telegram_text(send_split_message)),
                        )
                    else:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=chatid,
                                message_id=answer_messageid,
                                text=rendered_split,
                                parse_mode=split_parse_mode,
                                disable_web_page_preview=True,
                                read_timeout=time_out,
                                write_timeout=time_out,
                                pool_timeout=time_out,
                                connect_timeout=time_out
                            )
                            lastresult = rendered_split
                        except Exception as e:
                            if split_parse_mode and "parse entities" in str(e):
                                fallback = strip_html_tags(rendered_split) if split_parse_mode == "HTML" else _strip_telegram_markdown(sanitize_telegram_text(send_split_message))
                                await context.bot.edit_message_text(
                                    chat_id=chatid,
                                    message_id=answer_messageid,
                                    text=fallback,
                                    disable_web_page_preview=True,
                                    read_timeout=time_out,
                                    write_timeout=time_out,
                                    pool_timeout=time_out,
                                    connect_timeout=time_out
                                )
                                logger.error(f"Error sending split message: {send_split_message[:100]}")
                            else:
                                logger.error(f"Error in message sending: {e}")
                answer_messageid = None

            now_result, now_parse_mode = _render_telegram_response(tmpresult)
            force_preview = "message_search_stage_" in data
            if now_result and (lastresult != now_result or force_preview):
                await _queue_stream_preview(
                    now_result,
                    now_parse_mode,
                    fallback_text=_strip_telegram_markdown(sanitize_telegram_text(tmpresult)),
                    force=force_preview,
                )
        # === VIVENTIUM START ===
        # Feature: Ensure latest coalesced draft is delivered before stream finalization.
        await _flush_stream_previews()
        # === VIVENTIUM END ===
        # === VIVENTIUM START ===
        # Feature: Strip trailing {NTA} from content+tag responses before delivery/suppression check.
        result = strip_trailing_nta(result)
        # Feature: If the main assistant response is `{NTA}` (no-response-only), do not deliver anything.
        if is_no_response_only(result):
            if answer_messageid:
                try:
                    await context.bot.delete_message(chat_id=chatid, message_id=answer_messageid)
                except Exception:
                    pass
            return
        # === VIVENTIUM END ===
        _tg_timing_log(trace_id, "stream_complete", stream_start_ts)
        _tg_deep_log(trace_id, "stream_complete", stream_start_ts, base_ts=response_start_ts)
        # === VIVENTIUM START ===
        # Feature: Send any LibreChat attachments (images/files) back to the Telegram user.
        try:
            max_bytes = int(getattr(config, "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE", 10485760) or 10485760)
            text_fallback = bool(getattr(config, "VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK", False))

            async def _fetch_with_timing(**kwargs):
                dl_start_ts = time.monotonic()
                blob, content_type = await fetch_librechat_bytes(**kwargs)
                _tg_deep_log(
                    trace_id,
                    "lc_attachment_download",
                    dl_start_ts,
                    base_ts=response_start_ts,
                    extra=f"bytes={len(blob)}",
                )
                return blob, content_type

            await send_librechat_attachments(
                bot=context.bot,
                base_url=getattr(robot, "base_url", "") or "",
                secret=getattr(robot, "secret", "") or "",
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                telegram_chat_id=str(chatid),
                attachments=lc_attachments,
                message_thread_id=message_thread_id,
                reply_to_message_id=messageid,
                max_bytes=max_bytes,
                text_fallback=text_fallback,
                fetch_bytes=_fetch_with_timing,
            )
        except Exception as exc:
            logger.warning("LibreChat attachment delivery failed: %s", exc)
        # === VIVENTIUM END ===
    # === VIVENTIUM START ===
    # Feature: Prompt Telegram users to link their LibreChat account.
    # === VIVENTIUM END ===
    except TelegramLinkRequired as link_exc:
        await _cancel_stream_previews()
        link_url = link_exc.link_url
        link_message = f"Please link your Viventium account to continue:\n{link_url}"
        dm_message = escape(link_message, italic=False)
        group_notice = escape("I sent you a DM with a linking URL. Please check your inbox.", italic=False)
        fallback_notice = escape("Please start a private chat with me to link your account.", italic=False)

        try:
            if update_message.chat.type == "private":
                if answer_messageid:
                    await context.bot.edit_message_text(
                        chat_id=chatid,
                        message_id=answer_messageid,
                        text=dm_message,
                        parse_mode='MarkdownV2',
                        disable_web_page_preview=True,
                        read_timeout=time_out,
                        write_timeout=time_out,
                        pool_timeout=time_out,
                        connect_timeout=time_out,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chatid,
                        message_thread_id=message_thread_id,
                        text=dm_message,
                        parse_mode='MarkdownV2',
                        disable_web_page_preview=True,
                        reply_to_message_id=messageid,
                    )
            else:
                try:
                    await context.bot.send_message(
                        chat_id=int(telegram_user_id),
                        text=dm_message,
                        parse_mode='MarkdownV2',
                        disable_web_page_preview=True,
                    )
                    if answer_messageid:
                        await context.bot.edit_message_text(
                            chat_id=chatid,
                            message_id=answer_messageid,
                            text=group_notice,
                            parse_mode='MarkdownV2',
                            disable_web_page_preview=True,
                            read_timeout=time_out,
                            write_timeout=time_out,
                            pool_timeout=time_out,
                            connect_timeout=time_out,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chatid,
                            message_thread_id=message_thread_id,
                            text=group_notice,
                            parse_mode='MarkdownV2',
                            disable_web_page_preview=True,
                            reply_to_message_id=messageid,
                        )
                except Exception:
                    if answer_messageid:
                        await context.bot.edit_message_text(
                            chat_id=chatid,
                            message_id=answer_messageid,
                            text=fallback_notice,
                            parse_mode='MarkdownV2',
                            disable_web_page_preview=True,
                            read_timeout=time_out,
                            write_timeout=time_out,
                            pool_timeout=time_out,
                            connect_timeout=time_out,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chatid,
                            message_thread_id=message_thread_id,
                            text=fallback_notice,
                            parse_mode='MarkdownV2',
                            disable_web_page_preview=True,
                            reply_to_message_id=messageid,
                        )
        except Exception as send_exc:
            logger.warning(f"Failed to deliver Telegram link prompt: {send_exc}")
        return
    except Exception as e:
        await _cancel_stream_previews()
        logger.error("Exception in command_bot:", exc_info=True)
        logger.error(f"Failed result: {tmpresult[:200]}")
        # REMOVED: system_prompt parameter - LiveKitBridge.reset() ignores it, Viventium handles system prompts
        robot.reset(convo_id=convo_id)
        if "parse entities" in str(e):
            if answer_messageid:
                await context.bot.edit_message_text(chat_id=chatid, message_id=answer_messageid, text=tmpresult, disable_web_page_preview=True, read_timeout=time_out, write_timeout=time_out, pool_timeout=time_out, connect_timeout=time_out)
            else:
                await context.bot.send_message(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    text=tmpresult,
                    disable_web_page_preview=True,
                    reply_to_message_id=messageid,
                )
        else:
            tmpresult = f"{tmpresult}\n\n`{e}`"
    finally:
        await _cancel_stream_previews()
        # === VIVENTIUM START ===
        # Feature: Stop typing indicator once we have a result or exit.
        typing_stop.set()
        if typing_task:
            try:
                await asyncio.gather(typing_task, return_exceptions=True)
            except Exception:
                pass
        # === VIVENTIUM END ===
    logger.debug(f"Command result: {tmpresult[:100]}")

    # Add image URL detection and sending
    if image_has_send == 0:
        image_extensions = r'(https?://[^\s<>\"()]+(?:\.(?:webp|jpg|jpeg|png|gif)|/image)[^\s<>\"()]*)'
        image_urls = re.findall(image_extensions, tmpresult, re.IGNORECASE)
        image_urls_result = [url[0] if isinstance(url, tuple) else url for url in image_urls]
        if image_urls_result:
            try:
                # Limit the number of images to 10 (Telegram limit for albums)
                image_urls_result = image_urls_result[:10]

                # We send an album with all images
                media_group = []
                for img_url in image_urls_result:
                    media_group.append(InputMediaPhoto(media=img_url))

                await context.bot.send_media_group(
                    chat_id=chatid,
                    media=media_group,
                    message_thread_id=message_thread_id,
                    reply_to_message_id=messageid,
                )
            except Exception as e:
                logger.warning(f"Failed to send image(s): {str(e)}")

    now_result, now_parse_mode = _render_telegram_response(tmpresult)
    if lastresult != now_result:
        if "Can't parse entities: can't find end of code entity at byte offset" in tmpresult:
            # === VIVENTIUM START ===
            # Strip citations before plain-text fallback replies.
            await update_message.reply_text(sanitize_telegram_text(tmpresult))
            # === VIVENTIUM END ===
            logger.debug(f"Now result: {now_result[:100]}")
        elif now_result:
            if answer_messageid:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chatid,
                        message_id=answer_messageid,
                        text=now_result,
                        parse_mode=now_parse_mode,
                        disable_web_page_preview=True,
                        read_timeout=time_out,
                        write_timeout=time_out,
                        pool_timeout=time_out,
                        connect_timeout=time_out,
                    )
                except Exception as e:
                    if now_parse_mode and "parse entities" in str(e):
                        fallback = strip_html_tags(now_result) if now_parse_mode == "HTML" else sanitize_telegram_text(tmpresult)
                        await context.bot.edit_message_text(
                            chat_id=chatid,
                            message_id=answer_messageid,
                            text=fallback,
                            disable_web_page_preview=True,
                            read_timeout=time_out,
                            write_timeout=time_out,
                            pool_timeout=time_out,
                            connect_timeout=time_out,
                        )
                        # === VIVENTIUM END ===
            else:
                await _ensure_answer_message(
                    now_result,
                    now_parse_mode,
                    fallback_text=sanitize_telegram_text(tmpresult),
                )

    # Check if user wants voice responses (either sent voice note OR always_voice_response enabled)
    always_voice = False
    voice_responses_enabled = True
    try:
        always_voice = Users.get_config(convo_id, "ALWAYS_VOICE_RESPONSE")
    except Exception:
        pass  # Default to False if preference not set
    # === VIVENTIUM START ===
    # Feature: Allow per-chat enable/disable of voice replies.
    try:
        voice_responses_enabled = Users.get_config(convo_id, "VOICE_RESPONSES_ENABLED")
    except Exception:
        pass  # Default to True if preference not set
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Centralized gating for voice replies (honors user preference).
    should_send_voice = should_send_voice_reply(
        voice_note_detected=voice_note_detected,
        always_voice=always_voice,
        voice_enabled=voice_responses_enabled,
        text=tmpresult,
    )
    _tg_timing_log(
        trace_id,
        "voice_gate",
        response_start_ts,
        extra=(
            f"voice_note={int(bool(voice_note_detected))} "
            f"always_voice={int(bool(always_voice))} "
            f"voice_enabled={int(bool(voice_responses_enabled))} "
            f"send={int(bool(should_send_voice))}"
        ),
    )
    _tg_deep_log(
        trace_id,
        "voice_gate",
        response_start_ts,
        base_ts=response_start_ts,
        extra=(
            f"voice_note={int(bool(voice_note_detected))} "
            f"always_voice={int(bool(always_voice))} "
            f"voice_enabled={int(bool(voice_responses_enabled))} "
            f"send={int(bool(should_send_voice))}"
        ),
    )
    # === VIVENTIUM END ===
    
    if should_send_voice:
        cleaned_voice = config.prepare_tts_text(tmpresult)
        if cleaned_voice:
            try:
                voice_route = robot.get_cached_voice_route(str(chatid)) if hasattr(robot, "get_cached_voice_route") else None
                tts_provider = ""
                if isinstance(voice_route, dict):
                    tts_config = voice_route.get("tts")
                    if isinstance(tts_config, dict):
                        provider_value = tts_config.get("provider")
                        if isinstance(provider_value, str):
                            tts_provider = provider_value.strip().lower()
                # === VIVENTIUM START ===
                # Feature: Timing for TTS synthesis + send.
                tts_start_ts = time.monotonic()
                # === VIVENTIUM END ===
                # Chunk long text to prevent audio degradation and cutoffs (ElevenLabs best practice: < 800 chars)
                # Split by sentences to maintain natural flow
                # Note: 're' is already imported at top of file
                max_chunk_size = 800
                if "chatterbox" in tts_provider:
                    chunks = [cleaned_voice]
                elif len(cleaned_voice) > max_chunk_size:
                    # Split by sentences (periods, exclamation, question marks followed by space)
                    sentences = re.split(r'([.!?]\s+)', cleaned_voice)
                    chunks = []
                    current_chunk = ""
                    for i in range(0, len(sentences), 2):
                        sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")
                        if len(current_chunk) + len(sentence) <= max_chunk_size:
                            current_chunk += sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                else:
                    chunks = [cleaned_voice]
                
                # Synthesize all chunks and concatenate
                all_audio_chunks = []
                for i, chunk in enumerate(chunks):
                    logger.debug(f"Synthesizing TTS chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                    chunk_start_ts = time.monotonic() if _tg_deep_enabled() else None
                    voice_bytes = await synthesize_speech(chunk, convo_id, voice_route=voice_route)
                    if voice_bytes:
                        all_audio_chunks.append(voice_bytes)
                        if chunk_start_ts is not None:
                            _tg_deep_log(
                                trace_id,
                                "tts_chunk",
                                chunk_start_ts,
                                base_ts=response_start_ts,
                                extra=f"idx={i+1}/{len(chunks)} chars={len(chunk)} bytes={len(voice_bytes)}",
                            )
                        # Small delay between chunks to ensure complete audio (prevents cutoff)
                        if i < len(chunks) - 1:
                            await asyncio.sleep(0.1)
                
                if all_audio_chunks:
                    # Concatenate all audio chunks
                    combined_audio = b"".join(all_audio_chunks)
                    
                    # Small delay to ensure audio is fully ready (prevents last 0.5s cutoff)
                    await asyncio.sleep(0.2)
                    
                    audio_stream = BytesIO(combined_audio)
                    is_wav_provider = "chatterbox" in tts_provider or tts_provider == "cartesia"
                    audio_stream.name = "Voice.wav" if is_wav_provider else "Voice.mp3"
                    audio_stream.seek(0)

                    send_kwargs = {
                        "chat_id": chatid,
                        "audio": audio_stream,
                        "title": "Voice",  # Set title to "Voice" instead of filename
                        "caption": escape("", italic=False), # it was "Voice response" but i removed it because it was not needed
                        "parse_mode": 'MarkdownV2',
                        "read_timeout": time_out,
                        "write_timeout": time_out,
                        "connect_timeout": time_out,
                        "pool_timeout": time_out,
                    }
                    if message_thread_id:
                        send_kwargs["message_thread_id"] = message_thread_id
                    if messageid:
                        send_kwargs["reply_to_message_id"] = messageid

                    send_voice_start_ts = time.monotonic() if _tg_deep_enabled() else None
                    await context.bot.send_audio(**send_kwargs)
                    # === VIVENTIUM START ===
                    _tg_timing_log(
                        trace_id,
                        "tts_send",
                        tts_start_ts,
                        extra=f"chunks={len(all_audio_chunks)} bytes={len(combined_audio)}",
                    )
                    _tg_deep_log(
                        trace_id,
                        "tts_send",
                        tts_start_ts,
                        base_ts=response_start_ts,
                        extra=f"chunks={len(all_audio_chunks)} bytes={len(combined_audio)}",
                    )
                    if send_voice_start_ts is not None:
                        _tg_deep_log(
                            trace_id,
                            "telegram_send_voice",
                            send_voice_start_ts,
                            base_ts=response_start_ts,
                            extra=f"bytes={len(combined_audio)}",
                        )
                    # === VIVENTIUM END ===
            except Exception as e:
                logger.warning(f"Failed to send voice response: {e}")

    # REMOVED: FOLLOW_UP feature - Uses SummaryBot which is None (not available with LiveKit Bridge)
    # Follow-up questions should be handled by Viventium if needed

    # REMOVED: Memory manager - LiveKitBridge doesn't have memory_manager
    # Memory is handled by Viventium, not the bot

# === VIVENTIUM START ===
# Performance: Removed @AdminAuthorization, @GroupAuthorization, @Authorization
# decorators from button_press.  Each decorator calls GetMesageInfo which downloads
# files, extracts documents, transcribes voice — adding ~500ms+ per decorator.
# For inline button callbacks, auth is already enforced by Telegram (only the
# original user can click their own inline keyboard buttons).
# === VIVENTIUM END ===
async def button_press(update, context):
    """Handle Preferences inline keyboard button presses (fast path)."""
    import time as _time
    _t0 = _time.monotonic()
    callback_query = update.callback_query
    data = callback_query.data
    import telegram
    # === VIVENTIUM START ===
    # Performance: overlap callback acknowledgement network latency with local
    # preference processing and markup edits. The callback is still answered for
    # Telegram UX correctness; this just removes unnecessary serialization.
    async def _answer_callback_query():
        _ack_start = _time.monotonic()
        try:
            await callback_query.answer()
        except telegram.error.BadRequest as e:
            if "Query is too old" in str(e) or "response timeout expired" in str(e):
                pass
            else:
                logger.warning("Callback query answer failed: %s", e)
        except Exception as e:
            logger.warning("Callback query answer unexpected failure: %s", e)
        return (_time.monotonic() - _ack_start) * 1000.0

    answer_task = asyncio.create_task(_answer_callback_query())
    _t1 = _time.monotonic()
    # === VIVENTIUM END ===
    # Fast convo_id extraction — no file downloads or document processing
    from utils.scripts import get_callback_ids
    _, convo_id, _ = get_callback_ids(update)
    info_message = update_info_message(convo_id)
    info_message_md = escape(info_message, italic=False)
    _t2 = _time.monotonic()
    info_ms = (_t2 - _t1) * 1000.0

    # === VIVENTIUM START ===
    # Feature: Edit the existing menu message in-place.  Only send a new message
    # when the original is genuinely unreachable (deleted/not found), NOT on
    # transient errors — otherwise every toggle click creates a duplicate menu.
    async def _edit_or_send_menu(*, reply_markup, fallback_text):
        import telegram
        try:
            if callback_query.message:
                return await callback_query.edit_message_reply_markup(reply_markup=reply_markup)
        except telegram.error.BadRequest as e:
            err_str = str(e)
            if "Message is not modified" in err_str:
                return
            if "Message to edit not found" in err_str or "message can't be edited" in err_str:
                logger.info("Menu message gone; sending a fresh one: %s", e)
                return await context.bot.send_message(
                    chat_id=callback_query.message.chat_id if callback_query.message else update.effective_chat.id,
                    message_thread_id=getattr(callback_query.message, "message_thread_id", None),
                    text=fallback_text,
                    reply_markup=reply_markup,
                    parse_mode='MarkdownV2',
                    disable_web_page_preview=True,
                )
            logger.warning("Failed to edit menu message: %s", e)
        except Exception:
            logger.exception("Unexpected error editing menu message")
    # === VIVENTIUM END ===
    try:
        # REMOVED: Model selection callbacks - Model selection is handled by Viventium
        if False:  # Placeholder to maintain structure
            pass

        # REMOVED: Language selection - Using English-only UI for simplicity

        if data.endswith("_PREFERENCES"):
            pref_key = data[:-12]
            _t3 = _time.monotonic()
            try:
                Users.toggle_config(convo_id, pref_key)
            except Exception as e:
                logger.info(e)
            _t4 = _time.monotonic()
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(update_menu_buttons(PREFERENCES, "_PREFERENCES", convo_id)),
                fallback_text=info_message_md,
            )
            _t5 = _time.monotonic()
            logger.info("[PREF_TIMING] toggle=%s set=%.0fms edit=%.0fms total=%.0fms", pref_key, (_t4-_t3)*1000, (_t5-_t4)*1000, (_t5-_t0)*1000)

        elif data.startswith("PREFERENCES"):
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(update_menu_buttons(PREFERENCES, "_PREFERENCES", convo_id)),
                fallback_text=info_message_md,
            )
            _t5 = _time.monotonic()
            logger.info("[PREF_TIMING] open_menu edit=%.0fms total=%.0fms", (_t5-_t2)*1000, (_t5-_t0)*1000)

        elif data.startswith("BACK"):
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(update_first_buttons_message(convo_id)),
                fallback_text=info_message_md,
            )
            _t5 = _time.monotonic()
            logger.info("[PREF_TIMING] back edit=%.0fms total=%.0fms", (_t5-_t2)*1000, (_t5-_t0)*1000)
    except Exception:
        logger.exception("Unexpected Preferences handler error")
        # === VIVENTIUM START ===
        # Feature: Always send a fresh Preferences menu on unexpected errors.
        try:
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(update_menu_buttons(PREFERENCES, "_PREFERENCES", convo_id)),
                fallback_text=info_message_md,
            )
        except Exception:
            logger.exception("Failed to send Preferences fallback menu after unexpected error")
        # === VIVENTIUM END ===
    finally:
        answer_ms = await answer_task
        logger.info(
            "[PREF_TIMING] data=%s answer=%.0fms info=%.0fms convo_id=%s",
            data,
            answer_ms,
            info_ms,
            convo_id,
        )

@decorators.GroupAuthorization
@decorators.Authorization
@decorators.APICheck
async def handle_file(update, context):
    # === VIVENTIUM START ===
    # Handle file-only messages by sending attachments to LibreChat agent.
    message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, file_data_list = await GetMesageInfo(update, context)
    robot, _, api_key, api_url = get_robot(convo_id)  # api_key/api_url only for document extraction
    engine = Users.get_config(convo_id, "engine")  # Default value used for document extraction only

    text = rawtext
    if not text and voice_text:
        text = voice_text

    if getattr(config, "VIVENTIUM_TELEGRAM_FILE_TEXT_FALLBACK", False) and (file_url or image_url):
        engine_type, _ = get_engine({"base_url": api_url}, endpoint=None, original_model=engine)
        try:
            extracted_text = await Document_extract(file_url, image_url, engine_type)
        except Exception as e:
            extracted_text = None
            logger.warning(f"[VIVENTIUM] Document_extract failed: {e}")
        if extracted_text:
            if text:
                text = f"{extracted_text}\n{text}"
            else:
                text = extracted_text

    if update_message and update_message.chat.type in ['group', 'supergroup'] and text:
        sender_name = update_message.from_user.first_name
        text = f"{sender_name}: {text}"

    await getViventiumResponse(
        update_message,
        context,
        title="",
        robot=robot,
        message=text,
        chatid=chatid,
        messageid=messageid,
        convo_id=convo_id,
        message_thread_id=message_thread_id,
        voice_note_detected=False,
        files=file_data_list,
    )
    # === VIVENTIUM END ===

    return

# REMOVED: inlinequery function - Inline queries disabled, all messages route through LiveKit Bridge
# REMOVED: change_model function - Model selection is handled by Viventium, not the bot

async def scheduled_function(context: ContextTypes.DEFAULT_TYPE) -> None:
    """This function will execute once after RESET_TIME seconds, resetting the specific user's conversation"""
    job = context.job
    chat_id = job.chat_id

    if config.ADMIN_LIST and chat_id in config.ADMIN_LIST:
        return

    # REMOVED: Memory manager save - LiveKitBridge doesn't have memory_manager
    # Memory is handled by Viventium, not the bot

    # === VIVENTIUM START ===
    # Prefer the per-user convo id (job name) when LibreChat uses per-user histories.
    convo_id = job.name or str(chat_id)
    reset_ENGINE(convo_id)
    # === VIVENTIUM END ===

    # Automatically remove after task completes
    remove_job_if_exists(str(chat_id), context)

def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove task with specified name if it exists"""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

# Define a global variable to store chatid
target_convo_id = None
reset_mess_id = 9999

@decorators.GroupAuthorization
@decorators.Authorization
async def reset_chat(update, context):
    global target_convo_id, reset_mess_id
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, _, _ = await GetMesageInfo(update, context)
    reset_mess_id = user_message_id
    target_convo_id = convo_id
    stop_event.set()
    message = None
    if (len(context.args) > 0):
        message = ' '.join(context.args)
    reset_ENGINE(target_convo_id, message)

    remove_keyboard = ReplyKeyboardRemove()
    message = await context.bot.send_message(
        chat_id=chatid,
        message_thread_id=message_thread_id,
        text=escape("Reset successfully!"),
        reply_markup=remove_keyboard,
        parse_mode='MarkdownV2',
    )
    # REMOVED: GET_MODELS - Model fetching is not needed, Viventium handles models
    await delete_message(update, context, [message.message_id, user_message_id])

@decorators.AdminAuthorization
@decorators.GroupAuthorization
@decorators.Authorization
async def info(update, context):
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, voice_text, _ = await GetMesageInfo(update, context)
    info_message = update_info_message(convo_id)
    message = await context.bot.send_message(
        chat_id=chatid,
        message_thread_id=message_thread_id,
        text=escape(info_message, italic=False),
        reply_markup=InlineKeyboardMarkup(update_first_buttons_message(convo_id)),
        parse_mode='MarkdownV2',
        disable_web_page_preview=True,
        read_timeout=600,
    )
    await delete_message(update, context, [message.message_id, user_message_id])


@decorators.GroupAuthorization
@decorators.Authorization
async def call(update, context):
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, _, _ = await GetMesageInfo(
        update, context
    )
    call_link = get_telegram_call_link_result(convo_id)
    call_url = str(call_link.get("url") or "").strip()

    if not call_url:
        if call_link.get("link_required"):
            error_text = (
                "This Telegram account is not linked to Viventium yet. Open Preferences and link it, then try /call again."
            )
        elif call_link.get("public_url_required"):
            error_text = (
                "Telegram calls need a public Viventium voice URL. This local install is still using localhost."
            )
        else:
            error_text = (
                "I couldn't create the call link right now. Please try again in a moment."
            )
        message = await context.bot.send_message(
            chat_id=chatid,
            message_thread_id=message_thread_id,
            text=escape(
                error_text,
                italic=False,
            ),
            parse_mode='MarkdownV2',
            disable_web_page_preview=True,
            read_timeout=600,
        )
        await delete_message(update, context, [message.message_id, user_message_id])
        return

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Call Viventium", url=call_url)]]
    )
    message = await context.bot.send_message(
        chat_id=chatid,
        message_thread_id=message_thread_id,
        text=escape(
            "Tap below to open the live Viventium call for your linked account.",
            italic=False,
        ),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2',
        disable_web_page_preview=True,
        read_timeout=600,
    )
    await delete_message(update, context, [message.message_id, user_message_id])

@decorators.GroupAuthorization
@decorators.Authorization
async def start(update, context):
    # === VIVENTIUM NOTE ===
    # Feature: Route /start through getViventiumResponse for dynamic agent-driven onboarding.
    # Preserves legacy API key arg handling for residual features.
    # === VIVENTIUM NOTE ===
    _, _, _, chatid, messageid, _, update_message, message_thread_id, convo_id, _, _, _, _ = await GetMesageInfo(update, context)

    if len(context.args) == 2 and context.args[1].startswith("sk-"):
        api_url = context.args[0]
        api_key = context.args[1]
        Users.set_config(convo_id, "api_key", api_key)
        Users.set_config(convo_id, "api_url", api_url)

    if len(context.args) == 1 and context.args[0].startswith("sk-"):
        api_key = context.args[0]
        Users.set_config(convo_id, "api_key", api_key)
        Users.set_config(convo_id, "api_url", "https://api.openai.com/v1/chat/completions")

    robot, _, _, _ = get_robot(convo_id)
    trace_id = f"tg-start-{chatid}-{messageid}-{uuid.uuid4().hex[:6]}"
    try:
        await getViventiumResponse(
            update_message,
            context,
            title="",
            robot=robot,
            message="Hello! I just started a conversation with you.",
            chatid=chatid,
            messageid=messageid,
            convo_id=convo_id,
            message_thread_id=message_thread_id,
            trace_id=trace_id,
        )
    except TelegramLinkRequired as link_exc:
        link_message = f"Welcome to Viventium! Please link your account to get started:\n{link_exc.link_url}"
        await update.message.reply_text(
            escape(link_message, italic=False),
            parse_mode='MarkdownV2',
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.warning("[VIVENTIUM] /start agent handoff failed, sending static greeting: %s", exc)
        user = update.effective_user
        fallback = f"Hi `{user.username}`! I am **Viventium**, your cognitive AI system. I will do my best to help answer your questions.\n\n"
        await update.message.reply_text(
            escape(fallback, italic=False),
            parse_mode='MarkdownV2',
            disable_web_page_preview=True,
        )

async def error(update, context):
    traceback_string = traceback.format_exception(None, context.error, context.error.__traceback__)
    if "telegram.error.TimedOut: Timed out" in traceback_string:
        logger.warning('error: telegram.error.TimedOut: Timed out')
        return
    if "Message to be replied not found" in traceback_string:
        logger.warning('error: telegram.error.BadRequest: Message to be replied not found')
        return
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    logger.warning('Error traceback: %s', ''.join(traceback_string))

# REMOVED: MCP Commands - MCP integration is handled by Viventium agent directly
# The bot no longer needs separate MCP client commands since Viventium manages MCP servers

# ========================================

# REMOVED: unknown function - Returns immediately, does nothing. Handler still registered but function removed.

async def post_init(application: Application) -> None:
    # REMOVED: GET_MODELS - Model fetching is not needed, Viventium handles models
    
    # Register callback for proactive messages from LiveKit agent
    # This allows the agent to send messages when the user hasn't initiated a request
    # === VIVENTIUM START ===
    # Feature: Proactive follow-up voice delivery parity.
    # Purpose: Allow callback callers to pass synthesized audio while preserving text fallback.
    async def on_proactive_message(
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        voice_audio: Optional[bytes] = None,
    ):
        try:
            await deliver_proactive_telegram_message(
                application.bot,
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                voice_audio=voice_audio,
            )
        except Exception as e:
            logging.error(f"Failed to deliver proactive message to {chat_id}: {e}")

    if config.ChatGPTbot:
        config.ChatGPTbot.set_on_message_callback(on_proactive_message)
        logging.info(
            "✅ Registered proactive message callback with Telegram bridge (%s)",
            getattr(config, "VIVENTIUM_TELEGRAM_BACKEND", "unknown"),
        )

    await application.bot.set_my_commands([
        BotCommand('call', 'Open a live Viventium call'),
        BotCommand('info', 'Basic information'),
        BotCommand('reset', 'Reset the bot'),
        BotCommand('start', 'Start the bot'),
        # REMOVED: model command - Model selection handled by Viventium
        # REMOVED: MCP commands - MCP integration handled by Viventium
    ])
    description = (
        "I am an Assistant, a large language model trained by OpenAI. I will do my best to help answer your questions."
    )
    await application.bot.set_my_description(description)

if __name__ == '__main__':
    # ========================================================================
    # APPLICATION BUILDER - Resource Optimization Settings
    # ========================================================================
    # These settings control CPU and memory usage. Configure them in config.env:
    # - CONNECTION_POOL_SIZE: Max HTTP connections for sending (default: 8)
    # - GET_UPDATES_CONNECTION_POOL_SIZE: Max connections for receiving (default: 8)
    # - TIMEOUT: API timeout in seconds (default: 30)
    # - CONCURRENT_UPDATES: Enable parallel processing (default: false)
    # - POLLING_TIMEOUT: Polling timeout in seconds (default: 30)
    #
    # See config.py for detailed documentation on each setting.
    # Defaults are optimized for small deployments (1-10 users).
    # ========================================================================
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        # Enable/disable concurrent update processing
        # Set CONCURRENT_UPDATES in config.env (default: false for small deployments)
        .concurrent_updates(CONCURRENT_UPDATES)
        # Maximum HTTP connections for sending messages to Telegram API
        # Set CONNECTION_POOL_SIZE in config.env (default: 8, was 65536)
        .connection_pool_size(CONNECTION_POOL_SIZE)
        # Maximum HTTP connections for receiving updates from Telegram API
        # Set GET_UPDATES_CONNECTION_POOL_SIZE in config.env (default: 8, was 65536)
        .get_updates_connection_pool_size(GET_UPDATES_CONNECTION_POOL_SIZE)
        # Timeout settings for all API operations (read, write, connect, pool)
        # Set TIMEOUT in config.env (default: 30 seconds, was 600)
        .read_timeout(time_out)
        .write_timeout(time_out)
        .connect_timeout(time_out)
        .pool_timeout(time_out)
        .get_updates_read_timeout(time_out)
        .get_updates_write_timeout(time_out)
        .get_updates_connect_timeout(time_out)
        .get_updates_pool_timeout(time_out)
        # Rate limiter to prevent hitting Telegram API limits
        .rate_limiter(AIORateLimiter(max_retries=5))
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("call", call))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_chat))
    # REMOVED: Model selection handler - Model selection is handled by Viventium
    # REMOVED: MCP command handlers - MCP integration handled by Viventium agent directly
    # REMOVED: InlineQueryHandler - Inline queries disabled, all messages route through LiveKit Bridge
    application.add_handler(CallbackQueryHandler(button_press, block=False))
    application.add_handler(MessageHandler((filters.TEXT | filters.VOICE | filters.VIDEO_NOTE | filters.VIDEO) & ~filters.COMMAND, lambda update, context: command_bot(update, context, has_command=False), block = False))
    application.add_handler(MessageHandler(
        filters.CAPTION &
        (
            (filters.PHOTO & ~filters.COMMAND) |
            (
                filters.Document.PDF |
                filters.Document.TXT |
                filters.Document.DOC |
                filters.Document.FileExtension("jpg") |
                filters.Document.FileExtension("jpeg") |
                filters.Document.FileExtension("png") |
                filters.Document.FileExtension("md") |
                filters.Document.FileExtension("py") |
                filters.Document.FileExtension("yml") |
                filters.Document.FileExtension("mp4") |
                filters.Document.FileExtension("mov") |
                filters.Document.FileExtension("avi") |
                filters.Document.FileExtension("mkv") |
                filters.Document.FileExtension("webm")
            )
        ), lambda update, context: command_bot(update, context, has_command=False)))
    application.add_handler(MessageHandler(
        ~filters.CAPTION &
        (
            (filters.PHOTO & ~filters.COMMAND) |
            (
                filters.Document.PDF |
                filters.Document.TXT |
                filters.Document.DOC |
                filters.Document.FileExtension("jpg") |
                filters.Document.FileExtension("jpeg") |
                filters.Document.FileExtension("png") |
                filters.Document.FileExtension("md") |
                filters.Document.FileExtension("py") |
                filters.Document.FileExtension("yml") |
                filters.AUDIO |
                filters.Document.FileExtension("wav") |
                filters.Document.FileExtension("mp4") |
                filters.Document.FileExtension("mov") |
                filters.Document.FileExtension("avi") |
                filters.Document.FileExtension("mkv") |
                filters.Document.FileExtension("webm")
            )
        ), handle_file))
    # REMOVED: unknown handler - Function removed, does nothing
    application.add_error_handler(error)

    if WEB_HOOK:
        logger.info(f"Starting webhook server on {WEB_HOOK}")
        # === VIVENTIUM START ===
        # Feature: Ensure callback_query updates reach the bot (Preferences UI).
        application.run_webhook(
            "0.0.0.0",
            PORT,
            webhook_url=WEB_HOOK,
            allowed_updates=Update.ALL_TYPES,
        )
        # === VIVENTIUM END ===
    else:
        # Polling mode: Check Telegram API for new updates
        # Set POLLING_TIMEOUT in config.env (default: 30 seconds, was 600)
        # Lower values = more frequent checks (more CPU) but faster updates
        # Higher values = less frequent checks (less CPU) but slower updates
        logger.info(f"Starting polling mode with timeout={POLLING_TIMEOUT}s")
        application.run_polling(timeout=POLLING_TIMEOUT, allowed_updates=Update.ALL_TYPES)
