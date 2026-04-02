from __future__ import annotations

import asyncio
import contextlib
import io
import logging
from collections import defaultdict
from pathlib import Path

from telegram import BotCommand, Message, Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.access_control import AccessControl, AccessDecision, PendingPair
from app.codex_cli_bridge import CodexCliBridge
from app.project_registry import ProjectRegistry
from app.session_store import SessionStore
from app.telegram_files import (
    StagedTelegramAttachment,
    build_attachment_prompt,
    build_staged_attachment_path,
    default_extension_for_mime,
    sanitize_attachment_name,
    send_local_files,
    split_message_and_attachment_paths,
    summarize_attachments,
)
from app.telegram_rendering import RenderedChunk, render_telegram_chunks, sanitize_telegram_text
from app.transcribe_local import LocalWhisperTranscriber


logger = logging.getLogger(__name__)

_STREAM_EDIT_INTERVAL_SECONDS = 0.75
_STREAM_PREVIEW_LIMIT = 2800
_TRANSCRIPT_PREVIEW_LIMIT = 700


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate_text(text: str, *, limit: int) -> str:
    cleaned = sanitize_telegram_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 1)].rstrip() + "…"


def _panel_chunk(title: str, *, lines: list[str] | None = None, quote: str | None = None) -> RenderedChunk:
    safe_lines = [line for line in (lines or []) if line]
    plain_parts = [title]
    html_parts = [f"<b>{_escape_html(title)}</b>"]

    if safe_lines:
        plain_parts.extend(safe_lines)
        html_parts.extend(_escape_html(line) for line in safe_lines)

    if quote:
        plain_parts.extend(["", quote])
        html_parts.extend(["", f"<blockquote>{_escape_html(quote)}</blockquote>"])

    return RenderedChunk(
        html="\n".join(html_parts).strip(),
        plain="\n".join(plain_parts).strip(),
    )


def _preview_chunk(text: str) -> RenderedChunk:
    cleaned = sanitize_telegram_text(text).strip()
    if not cleaned:
        return _panel_chunk("Working on it…")

    if len(cleaned) <= 220 and cleaned.count("\n") <= 2:
        return _panel_chunk("Status", quote=cleaned)

    rendered_chunks = render_telegram_chunks(cleaned, limit=_STREAM_PREVIEW_LIMIT)
    if not rendered_chunks:
        return _panel_chunk("Live preview", quote=_truncate_text(cleaned, limit=_STREAM_PREVIEW_LIMIT))

    first_chunk = rendered_chunks[0]
    truncated = len(rendered_chunks) > 1
    html_body = first_chunk.html or _escape_html(first_chunk.plain)
    plain_body = first_chunk.plain or sanitize_telegram_text(first_chunk.html)
    if truncated:
        html_body = f"{html_body}\n\n…"
        plain_body = f"{plain_body}\n\n…"
    return RenderedChunk(
        html=f"<b>Live preview</b>\n\n{html_body}".strip(),
        plain=f"Live preview\n\n{plain_body}".strip(),
    )


class TelegramCodexBot:
    def __init__(
        self,
        *,
        token: str,
        bot_username: str,
        private_chat_only: bool,
        pairing_base_url: str,
        access_control: AccessControl,
        session_store: SessionStore,
        project_registry: ProjectRegistry,
        codex_bridge: CodexCliBridge,
        transcriber: LocalWhisperTranscriber,
    ) -> None:
        self._token = token
        self._bot_username = bot_username
        self._private_chat_only = private_chat_only
        self._pairing_base_url = pairing_base_url
        self._access_control = access_control
        self._session_store = session_store
        self._project_registry = project_registry
        self._codex_bridge = codex_bridge
        self._transcriber = transcriber
        self._application: Application | None = None
        self._chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def start(self) -> None:
        application = Application.builder().token(self._token).build()
        self._application = application
        application.add_handler(CommandHandler("start", self._handle_start))
        application.add_handler(CommandHandler("help", self._handle_help))
        application.add_handler(CommandHandler("pair", self._handle_pair))
        application.add_handler(CommandHandler("projects", self._handle_projects))
        application.add_handler(CommandHandler("use", self._handle_use))
        application.add_handler(CommandHandler("status", self._handle_status))
        application.add_handler(CommandHandler("reset", self._handle_reset))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice))
        application.add_handler(
            MessageHandler(
                filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.ANIMATION,
                self._handle_attachment,
            )
        )
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        await application.initialize()
        me = await application.bot.get_me()
        if me.username:
            self._bot_username = me.username
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Show help and pairing status"),
                BotCommand("pair", "Create or inspect the local pairing link"),
                BotCommand("projects", "List available project aliases"),
                BotCommand("use", "Switch the active project for this chat"),
                BotCommand("status", "Show the current project and Codex session"),
                BotCommand("reset", "Clear the current Codex thread for this chat"),
            ]
        )
        await application.start()
        if application.updater is None:
            raise RuntimeError("Telegram updater is unavailable")
        await application.updater.start_polling(drop_pending_updates=False)

    async def stop(self) -> None:
        if self._application is None:
            return
        if self._application.updater is not None:
            await self._application.updater.stop()
        await self._application.stop()
        await self._application.shutdown()

    async def notify_pair_confirmed(self, pending: PendingPair) -> None:
        if self._application is None:
            return
        chat_id = int(pending.chat_id)
        await self._send_chunk(
            chat_id,
            _panel_chunk(
                "Pairing complete",
                lines=[
                    "This bot is now locked to your Telegram user id.",
                    "Telegram only identifies the account, not the specific client device.",
                ],
            ),
        )

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private_chat(update):
            return
        decision = self._access_decision(update)
        session = self._session_store.get(update.effective_chat.id)
        project = self._project_registry.get(session.project_alias)
        await self._reply_chunk(
            update.effective_message,
            _panel_chunk(
                "telegram_codex",
                lines=[
                    f"Bot: @{self._bot_username}",
                    f"Current project: {project.alias}",
                    "Commands",
                    "• /projects",
                    "• /use <alias>",
                    "• /status",
                    "• /reset",
                    "• /pair",
                    "Security",
                    "• Pairing link is localhost-only.",
                    "• After pairing, the bot accepts only the paired Telegram user id.",
                    "• Telegram cannot verify which device sent a later message.",
                ],
            ),
        )
        if not decision.allowed:
            await self._send_access_decision(update, decision)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_start(update, context)

    async def _handle_pair(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private_chat(update):
            return
        decision = self._access_decision(update)
        if decision.allowed:
            await self._reply_chunk(
                update.effective_message,
                _panel_chunk(
                    "Already paired",
                    lines=["This Telegram account is already paired for this bot."],
                ),
            )
            return
        await self._send_access_decision(update, decision)

    async def _handle_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        session = self._session_store.get(update.effective_chat.id)
        lines = []
        for project in self._project_registry.all_projects():
            marker = " (current)" if project.alias == session.project_alias else ""
            lines.append(f"• {project.alias}: {project.path}{marker}")
        await self._reply_chunk(update.effective_message, _panel_chunk("Projects", lines=lines))

    async def _handle_use(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        if not context.args:
            await self._reply_chunk(update.effective_message, _panel_chunk("Usage", lines=["/use <project_alias>"]))
            return
        alias = context.args[0].strip()
        if alias not in self._project_registry.aliases():
            await self._reply_chunk(
                update.effective_message,
                _panel_chunk("Unknown project", lines=[alias]),
            )
            return
        session = self._session_store.set_project(update.effective_chat.id, alias, clear_thread=True)
        project = self._project_registry.get(session.project_alias)
        await self._reply_chunk(
            update.effective_message,
            _panel_chunk(
                "Project switched",
                lines=[
                    f"Active project: {project.alias}",
                    "The previous Codex thread was cleared for safety.",
                ],
            ),
        )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        session = self._session_store.get(update.effective_chat.id)
        project = self._project_registry.get(session.project_alias)
        thread_id = session.thread_id or "(new thread on next message)"
        await self._reply_chunk(
            update.effective_message,
            _panel_chunk(
                "Status",
                lines=[
                    f"Project: {project.alias}",
                    f"Path: {project.path}",
                    f"Codex thread: {thread_id}",
                ],
            ),
        )

    async def _handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        self._session_store.reset(update.effective_chat.id)
        await self._reply_chunk(
            update.effective_message,
            _panel_chunk("Thread cleared", lines=["The current Codex thread for this chat was reset."]),
        )

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        text = (update.effective_message.text or "").strip()
        if not text:
            return
        await self._process_prompt(update, text=text, input_mode="text")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return
        voice = update.effective_message.voice or update.effective_message.audio
        if voice is None:
            await self._reply_chunk(update.effective_message, _panel_chunk("Voice note", lines=["No voice payload was found."]))
            return

        status_message = await self._reply_chunk(
            update.effective_message,
            _panel_chunk("Voice note", lines=["Transcribing locally with whisper.cpp…"]),
        )
        tg_file = await context.bot.get_file(voice.file_id)
        buffer = io.BytesIO()
        await tg_file.download_to_memory(out=buffer)
        suffix = ".ogg" if update.effective_message.voice else ".mp3"
        transcript = await self._transcriber.transcribe_bytes(buffer.getvalue(), suffix=suffix)
        if not transcript:
            await self._edit_chunk(
                status_message,
                _panel_chunk("Voice note", lines=["The transcription came back empty."]),
            )
            return

        await self._edit_chunk(
            status_message,
            _panel_chunk(
                "Transcript ready",
                lines=["Sending the transcript to Codex…"],
                quote=_truncate_text(transcript, limit=_TRANSCRIPT_PREVIEW_LIMIT),
            ),
        )
        await self._process_prompt(
            update,
            text=transcript,
            input_mode="voice",
            status_message=status_message,
        )

    async def _handle_attachment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_authorized(update):
            return

        session = self._session_store.get(update.effective_chat.id)
        project = self._project_registry.get(session.project_alias)
        attachments = await self._download_message_attachments(update, context, project.path)
        if not attachments:
            return

        caption = (update.effective_message.caption or "").strip()
        status_message = await self._reply_chunk(
            update.effective_message,
            _panel_chunk(
                "Attachment received",
                lines=summarize_attachments(attachments) + (["Prompt included in caption."] if caption else []),
            ),
        )
        await self._process_prompt(
            update,
            text=build_attachment_prompt(user_text=caption, attachments=attachments),
            input_mode="attachment",
            image_paths=[attachment.path for attachment in attachments if attachment.mime_type.startswith("image/")],
            status_message=status_message,
        )

    async def _download_message_attachments(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        project_path: Path,
    ) -> list[StagedTelegramAttachment]:
        message = update.effective_message
        chat_id = update.effective_chat.id
        if message is None:
            return []

        attachments: list[StagedTelegramAttachment] = []

        if message.photo:
            photo = message.photo[-1]
            filename = sanitize_attachment_name(
                f"photo_{message.message_id}.jpg",
                default_stem="photo",
                default_suffix=".jpg",
            )
            path = build_staged_attachment_path(
                project_root=project_path,
                chat_id=chat_id,
                message_id=message.message_id,
                filename=filename,
            )
            tg_file = await context.bot.get_file(photo.file_id)
            buffer = io.BytesIO()
            await tg_file.download_to_memory(out=buffer)
            path.write_bytes(buffer.getvalue())
            attachments.append(
                StagedTelegramAttachment(
                    path=path,
                    filename=path.name,
                    mime_type="image/jpeg",
                    kind="image",
                )
            )

        document = message.document
        if document is not None:
            mime_type = document.mime_type or "application/octet-stream"
            filename = sanitize_attachment_name(
                document.file_name or "",
                default_stem="document",
                default_suffix=Path(document.file_name or "").suffix or default_extension_for_mime(mime_type),
            )
            path = build_staged_attachment_path(
                project_root=project_path,
                chat_id=chat_id,
                message_id=message.message_id,
                filename=filename,
            )
            tg_file = await context.bot.get_file(document.file_id)
            buffer = io.BytesIO()
            await tg_file.download_to_memory(out=buffer)
            path.write_bytes(buffer.getvalue())
            kind = "image" if mime_type.startswith("image/") else "file"
            attachments.append(
                StagedTelegramAttachment(
                    path=path,
                    filename=path.name,
                    mime_type=mime_type,
                    kind=kind,
                )
            )

        video = message.video
        if video is not None:
            mime_type = video.mime_type or "video/mp4"
            filename = sanitize_attachment_name(
                video.file_name or f"video_{message.message_id}.mp4",
                default_stem="video",
                default_suffix=Path(video.file_name or "").suffix or default_extension_for_mime(mime_type) or ".mp4",
            )
            path = build_staged_attachment_path(
                project_root=project_path,
                chat_id=chat_id,
                message_id=message.message_id,
                filename=filename,
            )
            tg_file = await context.bot.get_file(video.file_id)
            buffer = io.BytesIO()
            await tg_file.download_to_memory(out=buffer)
            path.write_bytes(buffer.getvalue())
            attachments.append(
                StagedTelegramAttachment(
                    path=path,
                    filename=path.name,
                    mime_type=mime_type,
                    kind="file",
                )
            )

        animation = message.animation
        if animation is not None:
            mime_type = animation.mime_type or "video/mp4"
            filename = sanitize_attachment_name(
                animation.file_name or f"animation_{message.message_id}.mp4",
                default_stem="animation",
                default_suffix=Path(animation.file_name or "").suffix or default_extension_for_mime(mime_type) or ".mp4",
            )
            path = build_staged_attachment_path(
                project_root=project_path,
                chat_id=chat_id,
                message_id=message.message_id,
                filename=filename,
            )
            tg_file = await context.bot.get_file(animation.file_id)
            buffer = io.BytesIO()
            await tg_file.download_to_memory(out=buffer)
            path.write_bytes(buffer.getvalue())
            attachments.append(
                StagedTelegramAttachment(
                    path=path,
                    filename=path.name,
                    mime_type=mime_type,
                    kind="file",
                )
            )

        return attachments

    async def _process_prompt(
        self,
        update: Update,
        *,
        text: str,
        input_mode: str,
        image_paths: list[Path] | None = None,
        status_message: Message | None = None,
    ) -> None:
        chat_id = update.effective_chat.id
        lock = self._chat_locks[chat_id]
        if lock.locked():
            await self._reply_chunk(
                update.effective_message,
                _panel_chunk("Busy", lines=["A Codex task is already running in this chat."]),
            )
            return

        async with lock:
            session = self._session_store.get(chat_id)
            project = self._project_registry.get(session.project_alias)
            typing_task = asyncio.create_task(self._typing_loop(chat_id))
            preview_message = status_message or await self._reply_chunk(
                update.effective_message,
                _panel_chunk("Working on it…", lines=[f"Project: {project.alias}"]),
            )
            preview_pending: RenderedChunk | None = None
            preview_task: asyncio.Task | None = None
            preview_lock = asyncio.Lock()
            preview_last_sent = 0.0

            async def _apply_preview(chunk: RenderedChunk) -> None:
                nonlocal preview_message, preview_last_sent
                preview_message = await self._edit_chunk(preview_message, chunk)
                preview_last_sent = asyncio.get_running_loop().time()

            async def _drain_previews() -> None:
                nonlocal preview_pending, preview_task, preview_last_sent
                try:
                    while True:
                        async with preview_lock:
                            chunk = preview_pending
                            preview_pending = None
                            if chunk is None:
                                return
                        if preview_last_sent > 0:
                            elapsed = asyncio.get_running_loop().time() - preview_last_sent
                            if elapsed < _STREAM_EDIT_INTERVAL_SECONDS:
                                await asyncio.sleep(_STREAM_EDIT_INTERVAL_SECONDS - elapsed)
                        await _apply_preview(chunk)
                finally:
                    async with preview_lock:
                        if preview_task is asyncio.current_task():
                            preview_task = None

            async def _queue_preview(text_value: str) -> None:
                nonlocal preview_pending, preview_task
                if not text_value.strip():
                    return
                async with preview_lock:
                    preview_pending = _preview_chunk(text_value)
                    if preview_task is None or preview_task.done():
                        preview_task = asyncio.create_task(_drain_previews())

            async def _flush_preview() -> None:
                nonlocal preview_task
                while True:
                    async with preview_lock:
                        task = preview_task
                        if task and task.done():
                            preview_task = None
                            task = None
                    if task is None:
                        return
                    await asyncio.gather(task, return_exceptions=True)

            async def _cancel_preview() -> None:
                nonlocal preview_pending, preview_task
                async with preview_lock:
                    preview_pending = None
                    task = preview_task
                    preview_task = None
                if task and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

            async def _on_agent_message(message: str) -> None:
                await _queue_preview(message)

            async def _on_agent_message_delta(message: str) -> None:
                await _queue_preview(message)

            try:
                result = await self._codex_bridge.run_turn(
                    cwd=project.path,
                    project_alias=project.alias,
                    user_prompt=text,
                    thread_id=session.thread_id,
                    input_mode=input_mode,
                    image_paths=image_paths or [],
                    on_agent_message=_on_agent_message,
                    on_agent_message_delta=_on_agent_message_delta,
                )
                await _flush_preview()
                self._session_store.set_thread(chat_id, result.thread_id)

                if not result.agent_messages:
                    await self._edit_chunk(
                        preview_message,
                        _panel_chunk("Done", lines=["Codex completed without an assistant message."]),
                    )
                    return

                display_text, attachment_paths = split_message_and_attachment_paths(
                    result.final_message,
                    allowed_root=project.path,
                )
                final_chunks = render_telegram_chunks(display_text) if display_text else []

                if len(final_chunks) == 1:
                    preview_message = await self._edit_chunk(preview_message, final_chunks[0])
                else:
                    await self._delete_message(chat_id, preview_message.message_id)
                    if final_chunks:
                        await self._send_rendered_chunks(
                            chat_id,
                            final_chunks,
                            reply_to_message_id=update.effective_message.message_id,
                        )
                    else:
                        await self._send_chunk(
                            chat_id,
                            _panel_chunk(
                                "Output ready",
                                lines=["See the attachment(s) below."] if attachment_paths else ["Codex completed."],
                            ),
                            reply_to_message_id=update.effective_message.message_id,
                        )

                if attachment_paths and self._application is not None:
                    await send_local_files(
                        bot=self._application.bot,
                        chat_id=chat_id,
                        paths=attachment_paths,
                        reply_to_message_id=update.effective_message.message_id,
                        text_fallback=True,
                    )
            except Exception:
                logger.exception("Codex relay failed")
                await _cancel_preview()
                await self._edit_chunk(
                    preview_message,
                    _panel_chunk("Codex relay failed", lines=["Check the local relay log for details."]),
                )
            finally:
                typing_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await typing_task

    def _access_decision(self, update: Update) -> AccessDecision:
        user = update.effective_user
        return self._access_control.authorize_or_begin_pairing(
            telegram_user_id=str(user.id),
            telegram_username=user.username or user.full_name or "",
            chat_id=str(update.effective_chat.id),
            base_url=self._pairing_base_url,
        )

    async def _ensure_authorized(self, update: Update) -> bool:
        if not await self._ensure_private_chat(update):
            return False
        decision = self._access_decision(update)
        if decision.allowed:
            return True
        await self._send_access_decision(update, decision)
        return False

    async def _ensure_private_chat(self, update: Update) -> bool:
        if not self._private_chat_only:
            return True
        chat = update.effective_chat
        if chat is not None and chat.type == ChatType.PRIVATE:
            return True
        await self._reply_chunk(update.effective_message, _panel_chunk("Private chat only", lines=["Use this bot in a private DM."]))
        return False

    async def _send_access_decision(self, update: Update, decision: AccessDecision) -> None:
        if decision.state == "pairing_required" and decision.pairing_url:
            await self._reply_chunk(
                update.effective_message,
                _panel_chunk(
                    "Pairing required",
                    lines=[
                        decision.message,
                        "Open this link from Telegram on this laptop:",
                        decision.pairing_url,
                        "After the first approval, this bot will accept only that Telegram user id.",
                    ],
                ),
            )
            return
        await self._reply_chunk(update.effective_message, _panel_chunk("Access", lines=[decision.message]))

    async def _typing_loop(self, chat_id: int) -> None:
        if self._application is None:
            return
        while True:
            await self._application.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)

    async def _reply_chunk(self, message: Message, chunk: RenderedChunk) -> Message:
        try:
            return await message.reply_text(
                text=chunk.html or chunk.plain,
                parse_mode=ParseMode.HTML if chunk.html else None,
                disable_web_page_preview=True,
            )
        except BadRequest:
            return await message.reply_text(
                text=chunk.plain or chunk.html,
                disable_web_page_preview=True,
            )

    async def _send_chunk(
        self,
        chat_id: int,
        chunk: RenderedChunk,
        *,
        reply_to_message_id: int | None = None,
    ) -> Message:
        if self._application is None:
            raise RuntimeError("Telegram application is unavailable")
        try:
            return await self._application.bot.send_message(
                chat_id=chat_id,
                text=chunk.html or chunk.plain,
                parse_mode=ParseMode.HTML if chunk.html else None,
                disable_web_page_preview=True,
                reply_to_message_id=reply_to_message_id,
            )
        except BadRequest:
            return await self._application.bot.send_message(
                chat_id=chat_id,
                text=chunk.plain or chunk.html,
                disable_web_page_preview=True,
                reply_to_message_id=reply_to_message_id,
            )

    async def _edit_chunk(self, message: Message, chunk: RenderedChunk) -> Message:
        try:
            return await message.edit_text(
                text=chunk.html or chunk.plain,
                parse_mode=ParseMode.HTML if chunk.html else None,
                disable_web_page_preview=True,
            )
        except BadRequest as exc:
            lowered = str(exc).lower()
            if "message is not modified" in lowered:
                return message
            if chunk.html:
                try:
                    return await message.edit_text(
                        text=chunk.plain or chunk.html,
                        disable_web_page_preview=True,
                    )
                except BadRequest as fallback_exc:
                    if "message is not modified" in str(fallback_exc).lower():
                        return message
                    raise
            raise

    async def _delete_message(self, chat_id: int, message_id: int) -> None:
        if self._application is None:
            return
        with contextlib.suppress(BadRequest):
            await self._application.bot.delete_message(chat_id=chat_id, message_id=message_id)

    async def _send_rendered_chunks(
        self,
        chat_id: int,
        chunks: list[RenderedChunk],
        *,
        reply_to_message_id: int | None = None,
    ) -> None:
        for index, chunk in enumerate(chunks):
            if not chunk.html and not chunk.plain:
                continue
            await self._send_chunk(
                chat_id,
                chunk,
                reply_to_message_id=reply_to_message_id if index == 0 else None,
            )
