from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.config import CodexSettings


logger = logging.getLogger(__name__)

AgentMessageCallback = Callable[[str], Awaitable[None]]
AgentDeltaCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class CodexRunResult:
    thread_id: str
    agent_messages: list[str] = field(default_factory=list)
    final_message: str = ""
    raw_events: list[dict[str, Any]] = field(default_factory=list)


class CodexCliBridge:
    def __init__(self, settings: CodexSettings) -> None:
        self._settings = settings

    async def run_turn(
        self,
        *,
        cwd: Path,
        project_alias: str,
        user_prompt: str,
        thread_id: str | None = None,
        input_mode: str = "text",
        image_paths: list[Path] | None = None,
        on_agent_message: AgentMessageCallback | None = None,
        on_agent_message_delta: AgentDeltaCallback | None = None,
    ) -> CodexRunResult:
        relay_prompt = self._build_relay_prompt(
            user_prompt=user_prompt,
            project_alias=project_alias,
            cwd=cwd,
            input_mode=input_mode,
        )
        if thread_id:
            return await self._run_resume_turn(
                cwd=cwd,
                relay_prompt=relay_prompt,
                thread_id=thread_id,
                image_paths=image_paths or [],
                on_agent_message=on_agent_message,
            )
        return await self._run_new_turn(
            cwd=cwd,
            relay_prompt=relay_prompt,
            image_paths=image_paths or [],
            on_agent_message=on_agent_message,
            on_agent_message_delta=on_agent_message_delta,
        )

    async def _run_new_turn(
        self,
        *,
        cwd: Path,
        relay_prompt: str,
        image_paths: list[Path],
        on_agent_message: AgentMessageCallback | None,
        on_agent_message_delta: AgentDeltaCallback | None,
    ) -> CodexRunResult:
        command = self._build_new_turn_command(
            cwd=cwd,
            relay_prompt=relay_prompt,
            image_paths=image_paths,
        )
        logger.info("Starting Codex command in %s", cwd)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if process.stdout is None or process.stderr is None:
            raise RuntimeError("Failed to start Codex subprocess")

        stderr_task = asyncio.create_task(self._drain_stderr(process.stderr))

        seen_agent_messages: list[str] = []
        raw_events: list[dict[str, Any]] = []
        current_thread_id = ""
        stream_buffers: dict[str, str] = {}
        last_stream_text = ""

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                stripped = line.decode("utf-8", errors="ignore").strip()
                if not stripped.startswith("{"):
                    continue
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                raw_events.append(event)

                stream_text = self._accumulate_stream_text(event, stream_buffers)
                cleaned_stream_text = stream_text.strip() if stream_text else ""
                if cleaned_stream_text and cleaned_stream_text != last_stream_text:
                    last_stream_text = cleaned_stream_text
                    if on_agent_message_delta is not None:
                        await on_agent_message_delta(cleaned_stream_text)

                if event.get("type") == "thread.started":
                    current_thread_id = str(event.get("thread_id") or current_thread_id)
                    continue

                if event.get("type") != "item.completed":
                    continue

                item = event.get("item") or {}
                if item.get("type") != "agent_message":
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                seen_agent_messages.append(text)
                if on_agent_message is not None:
                    await on_agent_message(text)

            return_code = await process.wait()
            if return_code != 0:
                raise RuntimeError(f"Codex command failed with exit code {return_code}")
            if not current_thread_id:
                raise RuntimeError("Codex did not emit a thread id")
            return CodexRunResult(
                thread_id=current_thread_id,
                agent_messages=seen_agent_messages,
                final_message=seen_agent_messages[-1] if seen_agent_messages else "",
                raw_events=raw_events,
            )
        finally:
            await stderr_task

    async def _run_resume_turn(
        self,
        *,
        cwd: Path,
        relay_prompt: str,
        thread_id: str,
        image_paths: list[Path],
        on_agent_message: AgentMessageCallback | None,
    ) -> CodexRunResult:
        temp_file = tempfile.NamedTemporaryFile(prefix="telegram-codex-last-message-", delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        command = self._build_resume_command(
            relay_prompt=relay_prompt,
            thread_id=thread_id,
            image_paths=image_paths,
            output_file=temp_path,
        )
        logger.info("Resuming Codex command in %s", cwd)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_data, stderr_data = await process.communicate()
        return_code = process.returncode
        stdout_text = stdout_data.decode("utf-8", errors="ignore")
        stderr_text = stderr_data.decode("utf-8", errors="ignore")
        try:
            if return_code != 0:
                self._log_resume_stderr(stderr_text, failed=True)
                raise RuntimeError(f"Codex command failed with exit code {return_code}")

            final_message = temp_path.read_text(encoding="utf-8").strip() if temp_path.exists() else ""
            if not final_message:
                final_message = self._extract_resume_stdout_message(stdout_text)
            self._log_resume_stderr(stderr_text, failed=False)
            if not final_message:
                raise RuntimeError("Codex resume completed without a final assistant message")
            if on_agent_message is not None:
                await on_agent_message(final_message)
            return CodexRunResult(
                thread_id=thread_id,
                agent_messages=[final_message],
                final_message=final_message,
                raw_events=[],
            )
        finally:
            with contextlib.suppress(OSError):
                temp_path.unlink()

    def _build_new_turn_command(
        self,
        *,
        cwd: Path,
        relay_prompt: str,
        image_paths: list[Path],
    ) -> list[str]:
        command = [self._settings.command]
        for image_path in image_paths:
            command.extend(["-i", str(image_path)])
        if self._settings.model:
            command.extend(["-m", self._settings.model])
        if self._settings.sandbox == "danger-full-access":
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.extend(["-s", self._settings.sandbox, "-a", self._settings.approval_policy])

        command.extend(["exec", "--json"])
        if self._settings.skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.extend(["-C", str(cwd), relay_prompt])
        return command

    def _build_resume_command(
        self,
        *,
        relay_prompt: str,
        thread_id: str,
        image_paths: list[Path],
        output_file: Path,
    ) -> list[str]:
        command = [self._settings.command]
        for image_path in image_paths:
            command.extend(["-i", str(image_path)])
        if self._settings.model:
            command.extend(["-m", self._settings.model])
        if self._settings.sandbox == "danger-full-access":
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.extend(["-s", self._settings.sandbox, "-a", self._settings.approval_policy])

        command.extend(["exec"])
        if self._settings.skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.extend(["-o", str(output_file), "resume", thread_id, relay_prompt])
        return command

    @staticmethod
    def _build_relay_prompt(*, user_prompt: str, project_alias: str, cwd: Path, input_mode: str) -> str:
        return (
            "You are working through a private Telegram relay on the owner's laptop.\n"
            "Turn rules:\n"
            "- If the task is non-trivial, send short progress updates as separate assistant messages while you work.\n"
            "- Keep the final answer concise and readable in Telegram.\n"
            "- If you changed files, mention the key absolute file paths in the final answer.\n"
            "- If you want the Telegram relay to send user-facing files back into chat, add an `Attachments:` section at the end with one absolute file path per line.\n"
            "- Do not reveal secrets, tokens, or local environment values unless the user explicitly asks for them.\n"
            f"- Selected project alias: {project_alias}\n"
            f"- Working directory: {cwd}\n"
            f"- Input mode: {input_mode}\n"
            "\n"
            "User request:\n"
            f"{user_prompt.strip()}"
        )

    @staticmethod
    async def _drain_stderr(stream: asyncio.StreamReader) -> None:
        while True:
            line = await stream.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="ignore").strip()
            if text:
                if CodexCliBridge._is_benign_stderr_line(text):
                    logger.debug("codex stderr (benign): %s", text)
                else:
                    logger.warning("codex stderr: %s", text)

    @staticmethod
    def _is_benign_stderr_line(text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        benign_markers = (
            "authrequired(authrequirederror",
            "authentication required",
            "oauth-protected-resource",
            "transport channel closed, when authrequired",
        )
        return any(marker in normalized for marker in benign_markers)

    @staticmethod
    def _accumulate_stream_text(event: dict[str, Any], buffers: dict[str, str]) -> str:
        event_type = str(event.get("type") or "")

        if event_type in {"agent_message_delta", "agent_message_content_delta"}:
            item_id = str(event.get("item_id") or event.get("id") or "_current")
            delta = CodexCliBridge._first_string(event.get("delta"), event.get("text"), event.get("content"))
            if delta:
                buffers[item_id] = buffers.get(item_id, "") + delta
                return buffers[item_id]
            return ""

        if event_type not in {"item.updated", "item.completed"}:
            return ""

        item = event.get("item") or {}
        if item.get("type") != "agent_message":
            return ""
        item_id = str(item.get("id") or event.get("item_id") or "_current")
        text = CodexCliBridge._first_string(item.get("text"), event.get("text"), event.get("content"))
        if not text:
            return ""
        buffers[item_id] = text
        return text

    @staticmethod
    def _first_string(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _extract_resume_stdout_message(stdout_text: str) -> str:
        lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        if not lines:
            return ""
        return lines[-1]

    def _log_resume_stderr(self, stderr_text: str, *, failed: bool) -> None:
        for raw_line in stderr_text.splitlines():
            text = raw_line.strip()
            if not text:
                continue
            if self._is_benign_resume_stderr_line(text):
                logger.debug("codex resume stderr (ignored): %s", text)
                continue
            if self._is_benign_stderr_line(text):
                logger.debug("codex stderr (benign): %s", text)
                continue
            if failed:
                logger.warning("codex stderr: %s", text)
            else:
                logger.debug("codex resume stderr: %s", text)

    @staticmethod
    def _is_benign_resume_stderr_line(text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        if normalized.startswith("openai codex v"):
            return True
        if normalized in {"--------", "user", "codex"}:
            return True
        benign_prefixes = (
            "workdir:",
            "model:",
            "provider:",
            "approval:",
            "sandbox:",
            "reasoning effort:",
            "reasoning summaries:",
            "session id:",
            "mcp:",
            "mcp startup:",
            "tokens used",
        )
        return normalized.startswith(benign_prefixes)
