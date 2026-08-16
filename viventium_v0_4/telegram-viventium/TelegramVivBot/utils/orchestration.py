"""Telegram adapter for Viventium's account-wide Parallel Work control plane.

Core remains authoritative for identity, preference, work lifecycle, and allowed actions. This
module only validates Core responses and stores short-lived opaque Telegram callback capabilities.
"""

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import stat
import sys
import time
import urllib.parse
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx


ORCHESTRATION_PATH = "/api/viventium/telegram/orchestration"
ALLOWED_ACTIONS = frozenset(
    {"queue", "message", "steer", "pause", "resume", "stop", "retry", "dismiss"}
)
INSTRUCTION_ACTIONS = frozenset({"queue", "message", "steer"})
CONFIRM_ACTIONS = frozenset({"stop"})
ACTIVE_STATES = frozenset({"fresh", "stale", "unavailable"})
WORK_REF_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


def default_callback_store_path() -> Path:
    configured = str(os.environ.get("VIVENTIUM_TELEGRAM_STATE_DIR") or "").strip()
    if configured:
        root = Path(configured).expanduser()
    elif sys.platform == "darwin":
        root = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Viventium"
            / "runtime"
            / "telegram"
        )
    else:
        state_home = str(os.environ.get("XDG_STATE_HOME") or "").strip()
        root = (
            Path(state_home).expanduser() / "viventium" / "telegram"
            if state_home
            else Path.home() / ".local" / "state" / "viventium" / "telegram"
        )
    return root / "parallel-work-callbacks.sqlite3"


class OrchestrationError(RuntimeError):
    """A safe, user-presentable orchestration boundary failure."""

    def __init__(self, message: str, *, indeterminate: bool = False):
        self.indeterminate = bool(indeterminate)
        super().__init__(message)


class OrchestrationLinkRequired(OrchestrationError):
    def __init__(self, message: str, link_url: str = ""):
        self.link_url = str(link_url or "").strip()
        super().__init__(message or "Link your Viventium account to manage parallel work.")


@dataclass(frozen=True)
class WorkItem:
    work_ref: str
    title: str
    state: str
    status_summary: str
    updated_at: str
    actions: tuple[str, ...]


@dataclass(frozen=True)
class ActionReceipt:
    accepted: bool
    action: str
    message: str


@dataclass(frozen=True)
class OrchestrationSnapshot:
    linked: bool
    parallel_work_available: bool
    parallel_work_enabled: bool
    active_state: str
    generated_at: str
    items: tuple[WorkItem, ...]
    has_more: bool
    overflow_count: int
    next_cursor: str
    has_known_work: bool
    notice: str
    action_receipt: Optional[ActionReceipt] = None


def _safe_text(value: Any, *, limit: int = 1000) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _parse_work_item(raw: Any) -> Optional[WorkItem]:
    if not isinstance(raw, dict):
        return None
    work_ref = _safe_text(raw.get("workRef"), limit=2048)
    if not WORK_REF_PATTERN.fullmatch(work_ref):
        return None
    actions: list[str] = []
    raw_actions = raw.get("actions")
    if isinstance(raw_actions, list):
        for value in raw_actions:
            action = _safe_text(value, limit=32).lower()
            if action in ALLOWED_ACTIONS and action not in actions:
                actions.append(action)
    return WorkItem(
        work_ref=work_ref,
        title=_safe_text(raw.get("title"), limit=240) or "Untitled work",
        state=_safe_text(raw.get("state"), limit=40).lower() or "unknown",
        status_summary=_safe_text(raw.get("statusSummary"), limit=1000),
        updated_at=_safe_text(raw.get("updatedAt"), limit=64),
        actions=tuple(actions),
    )


def parse_snapshot(
    preference_payload: Any,
    active_work_payload: Any = None,
    *,
    action_receipt: Optional[ActionReceipt] = None,
) -> OrchestrationSnapshot:
    """Validate the canonical preference and Active work responses into one Telegram model."""

    if not isinstance(preference_payload, dict):
        raise OrchestrationError("Parallel work is unavailable right now. Please try again.")
    available = preference_payload.get("available") is True
    has_known_work = preference_payload.get("hasKnownWork") is True
    mode = _safe_text(preference_payload.get("mode"), limit=32).lower()
    if mode not in {"focused", "parallel"}:
        raise OrchestrationError("Parallel work returned an invalid account preference.")

    active = active_work_payload if isinstance(active_work_payload, dict) else None
    state = _safe_text(active.get("snapshot"), limit=32).lower() if active else "unavailable"
    if state not in ACTIVE_STATES:
        state = "unavailable"
    raw_items = active.get("work") if active else None
    items: list[WorkItem] = []
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            parsed = _parse_work_item(raw_item)
            if parsed is not None:
                items.append(parsed)

    notice = ""
    if state == "stale":
        notice = "Showing the last known active work. Refresh for current status."
    elif state == "unavailable":
        notice = "Active work is unavailable right now. Existing work may still be running."

    overflow_count = _safe_int(active.get("overflowCount")) if active else 0
    next_cursor = _safe_text(active.get("cursor"), limit=2048) if active else ""
    if next_cursor and not re.fullmatch(r"[A-Za-z0-9._~:@+\-]+", next_cursor):
        next_cursor = ""

    return OrchestrationSnapshot(
        linked=True,
        parallel_work_available=available,
        parallel_work_enabled=mode == "parallel",
        active_state=state,
        generated_at="",
        items=tuple(items),
        # Overflow remains truthful even if a malformed/missing cursor means the
        # bot cannot offer a Load more action for this snapshot.
        has_more=overflow_count > 0,
        overflow_count=overflow_count,
        next_cursor=next_cursor,
        has_known_work=has_known_work,
        notice=(
            notice
            if available or state != "unavailable"
            else "Parallel work launches are unavailable. Existing work may still be running."
        ),
        action_receipt=action_receipt,
    )


def safe_link_url(value: Any) -> str:
    candidate = _safe_text(value, limit=2048)
    if not candidate:
        return ""
    try:
        parsed = urllib.parse.urlparse(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return candidate


def _state_label(value: str) -> str:
    cleaned = str(value or "unknown").replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Unknown"


def format_active_work(snapshot: OrchestrationSnapshot) -> str:
    """Render plain Telegram text without interpreting work content as markup."""

    mode = "On" if snapshot.parallel_work_enabled else "Off"
    lines = ["Active work", f"Parallel work: {mode}"]
    if not snapshot.parallel_work_enabled:
        lines.append("New automatic delegation is focused. Existing work remains visible and controllable.")

    if snapshot.active_state == "unavailable":
        lines.extend(
            [
                "",
                snapshot.notice
                or "Active work is unavailable right now. Existing work may still be running.",
            ]
        )
        return "\n".join(lines)

    if snapshot.active_state == "stale":
        lines.extend(
            [
                "",
                snapshot.notice or "Showing the last known active work. Refresh for current status.",
            ]
        )

    if not snapshot.items:
        lines.extend(["", "No active work."])
    else:
        for index, item in enumerate(snapshot.items, start=1):
            lines.extend(["", f"{index}. {item.title}", _state_label(item.state)])
            if item.status_summary:
                lines.append(item.status_summary)

    if snapshot.has_more:
        lines.append("")
        if snapshot.overflow_count:
            noun = "item is" if snapshot.overflow_count == 1 else "items are"
            lines.append(f"{snapshot.overflow_count} more active {noun} not shown.")
        else:
            lines.append("More active work is not shown in this Telegram view.")
    return "\n".join(lines)


def format_parallel_work_settings(snapshot: OrchestrationSnapshot) -> str:
    lines = ["Parallel work", "Account-wide setting for Telegram, Web, and Voice."]
    if not snapshot.parallel_work_available:
        lines.extend(
            [
                "",
                "Parallel work is unavailable for this agent or account right now.",
                "Active work remains visible when Core can retrieve it.",
            ]
        )
        return "\n".join(lines)
    lines.extend(
        [
            "",
            f"Status: {'On' if snapshot.parallel_work_enabled else 'Off'}",
            (
                "Main can hand independent substantial work to durable background workers while staying available."
                if snapshot.parallel_work_enabled
                else "Main stays focused unless you explicitly delegate. Existing work keeps running and remains visible."
            ),
        ]
    )
    return "\n".join(lines)


class OrchestrationClient:
    def __init__(self, base_url: str, secret: str, *, timeout_s: float = 10.0):
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.secret = str(secret or "").strip()
        self.timeout_s = max(float(timeout_s), 0.1)

    async def get_snapshot(self, telegram_user_id: str, *, cursor: str = "") -> OrchestrationSnapshot:
        user_id = self._require_user_id(telegram_user_id)
        normalized_cursor = _safe_text(cursor, limit=2048)
        if normalized_cursor and not re.fullmatch(r"[A-Za-z0-9._~:@+\-]+", normalized_cursor):
            raise ValueError("Active work cursor is invalid")
        work_params = {"telegramUserId": user_id}
        if normalized_cursor:
            work_params["cursor"] = normalized_cursor
        preference_result, work_result = await asyncio.gather(
            self._request_json(
                "GET",
                ORCHESTRATION_PATH,
                params={"telegramUserId": user_id},
            ),
            self._request_json(
                "GET",
                f"{ORCHESTRATION_PATH}/work",
                params=work_params,
            ),
            return_exceptions=True,
        )
        if isinstance(preference_result, BaseException):
            raise preference_result
        if isinstance(work_result, BaseException):
            raise work_result
        return parse_snapshot(preference_result, work_result)

    async def get_preference(self, telegram_user_id: str) -> OrchestrationSnapshot:
        user_id = self._require_user_id(telegram_user_id)
        preference = await self._request_json(
            "GET",
            ORCHESTRATION_PATH,
            params={"telegramUserId": user_id},
        )
        return parse_snapshot(preference)

    async def set_parallel_work(
        self,
        telegram_user_id: str,
        enabled: bool,
    ) -> OrchestrationSnapshot:
        user_id = self._require_user_id(telegram_user_id)
        preference = await self._request_json(
            "PATCH",
            ORCHESTRATION_PATH,
            json_body={
                "telegramUserId": user_id,
                "mode": "parallel" if enabled is True else "focused",
            },
        )
        return parse_snapshot(preference)

    async def act(
        self,
        telegram_user_id: str,
        work_ref: str,
        action: str,
        *,
        instruction: Optional[str] = None,
        operation_id: str,
    ) -> OrchestrationSnapshot:
        user_id = self._require_user_id(telegram_user_id)
        normalized_action = _safe_text(action, limit=32).lower()
        if normalized_action not in ALLOWED_ACTIONS:
            raise ValueError("Unsupported work action")
        normalized_instruction = _safe_text(instruction, limit=8000)
        if normalized_action in INSTRUCTION_ACTIONS and not normalized_instruction:
            raise ValueError("This action requires an instruction")
        normalized_work_ref = _safe_text(work_ref, limit=160)
        if not WORK_REF_PATTERN.fullmatch(normalized_work_ref):
            raise ValueError("workRef is invalid")
        normalized_operation_id = _safe_text(operation_id, limit=64)
        try:
            parsed_operation_id = str(uuid.UUID(normalized_operation_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("operation_id must be a UUID") from exc
        body = {
            "telegramUserId": user_id,
            "action": normalized_action,
            "operationId": parsed_operation_id,
        }
        if normalized_instruction:
            body["instruction"] = normalized_instruction
        encoded_ref = urllib.parse.quote(normalized_work_ref, safe="")
        action_result = await self._request_json(
            "POST",
            f"{ORCHESTRATION_PATH}/work/{encoded_ref}/actions",
            json_body=body,
        )
        snapshot = await self.get_snapshot(user_id)
        status = _safe_text(action_result.get("status"), limit=64) or "accepted"
        label = normalized_action.replace("_", " ").capitalize()
        return replace(
            snapshot,
            action_receipt=ActionReceipt(
                accepted=True,
                action=normalized_action,
                message=f"{label} {status}.",
            ),
        )

    @staticmethod
    def _require_user_id(value: str) -> str:
        user_id = _safe_text(value, limit=128)
        if not user_id:
            raise ValueError("telegramUserId is required")
        return user_id

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, str]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.base_url or not self.secret:
            raise OrchestrationError("Parallel work is unavailable because Viventium is not connected.")
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        kwargs: dict[str, Any] = {"headers": headers}
        if params is not None:
            kwargs["params"] = params
        if json_body is not None:
            kwargs["json"] = json_body
        timeout = httpx.Timeout(
            self.timeout_s,
            connect=min(self.timeout_s, 5.0),
            read=self.timeout_s,
            write=self.timeout_s,
            pool=min(self.timeout_s, 5.0),
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.RequestError as exc:
            raise OrchestrationError(
                "Parallel work is unavailable right now. Existing work may still be running.",
                indeterminate=True,
            ) from exc

        payload: Any = {}
        try:
            payload = response.json()
        except Exception:
            payload = {}
        raw_error = payload.get("error") if isinstance(payload, dict) else None
        flat_error = _safe_text(raw_error, limit=500)
        nested_error = raw_error if isinstance(raw_error, dict) else {}
        error_message = _safe_text(nested_error.get("message"), limit=500) or flat_error
        error_code = (
            _safe_text(payload.get("code"), limit=100)
            if isinstance(payload, dict)
            else ""
        ) or _safe_text(nested_error.get("code"), limit=100)
        if (
            response.status_code in {401, 403}
            and isinstance(payload, dict)
            and error_code == "TELEGRAM_ACCOUNT_NOT_LINKED"
            and payload.get("linkRequired") is True
        ):
            raise OrchestrationLinkRequired(
                "This Telegram account is not linked to Viventium. Send /start to link it before managing Parallel work.",
                _safe_text(payload.get("linkUrl"), limit=2048) if isinstance(payload, dict) else "",
            )
        if response.status_code >= 400:
            message = error_message or "Parallel work could not be updated. Please refresh and try again."
            raise OrchestrationError(
                message,
                indeterminate=response.status_code >= 500
                or response.status_code in {408, 425, 429},
            )
        if not isinstance(payload, dict):
            raise OrchestrationError(
                "Parallel work returned an invalid response.",
                indeterminate=True,
            )
        return payload


@dataclass(frozen=True)
class CallbackTarget:
    token: str
    work_ref: str
    action: str


@dataclass(frozen=True)
class ActionReservation:
    target: CallbackTarget
    operation_id: str
    replay: bool


@dataclass(frozen=True)
class PageReservation:
    token: str
    cursor: str
    replay: bool


class CallbackCapabilityStore:
    """Durable short-lived mapping from Telegram-safe opaque tokens to server work capabilities."""

    def __init__(self, path: str | Path, *, ttl_s: int = 900, action_lease_s: int = 15):
        self.path = Path(path)
        self.ttl_s = max(int(ttl_s), 1)
        self.action_lease_s = max(int(action_lease_s), 1)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._secure_database_file()
        self._initialize()
        self._secure_storage_files()

    @staticmethod
    def _harden_regular_file(path: Path, *, create: bool = False) -> None:
        """Make a state file owner-only without ever following a symlink."""

        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
        if create:
            flags |= os.O_CREAT
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileNotFoundError:
            if create:
                raise
            return
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise RuntimeError(f"Telegram state path is not a regular file: {path}")
            getuid = getattr(os, "getuid", None)
            if callable(getuid) and file_stat.st_uid != getuid():
                raise PermissionError(f"Telegram state path is not owned by this user: {path}")
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

    def _secure_database_file(self) -> None:
        self._harden_regular_file(self.path, create=True)

    def _secure_storage_files(self) -> None:
        """Harden the database plus any SQLite sidecars left by this or an older build."""

        self._secure_database_file()
        for suffix in ("-wal", "-shm", "-journal"):
            self._harden_regular_file(
                self.path.with_name(f"{self.path.name}{suffix}"),
                create=False,
            )

    def _connect(self) -> sqlite3.Connection:
        self._secure_storage_files()
        connection = sqlite3.connect(str(self.path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        # SQLite derives new journal/WAL permissions from the already-hardened database. This
        # second pass also upgrades sidecars that appeared while opening an older database.
        self._secure_storage_files()
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_work_callbacks (
                    token TEXT PRIMARY KEY,
                    telegram_user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    prompt_message_id TEXT,
                    work_ref TEXT NOT NULL,
                    action TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL
                )
                """
            )
            existing_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(telegram_work_callbacks)"
                ).fetchall()
            }
            for name, definition in (
                ("action_state", "TEXT NOT NULL DEFAULT 'available'"),
                ("operation_id", "TEXT"),
                ("lease_until", "REAL"),
                ("receipt", "TEXT"),
                ("completed_at", "REAL"),
                ("instruction", "TEXT"),
            ):
                if name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE telegram_work_callbacks ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_telegram_work_prompt ON telegram_work_callbacks(telegram_user_id, chat_id, prompt_message_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_work_pages (
                    token TEXT PRIMARY KEY,
                    telegram_user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    cursor TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL
                )
                """
            )
            page_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(telegram_work_pages)").fetchall()
            }
            for name, definition in (
                ("fetch_state", "TEXT NOT NULL DEFAULT 'available'"),
                ("lease_until", "REAL"),
                ("completed_at", "REAL"),
            ):
                if name not in page_columns:
                    connection.execute(
                        f"ALTER TABLE telegram_work_pages ADD COLUMN {name} {definition}"
                    )

    def issue_actions(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        targets: Iterable[tuple[str, str]],
        now: Optional[float] = None,
    ) -> tuple[CallbackTarget, ...]:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        expires_at = (time.time() if now is None else float(now)) + self.ttl_s
        issued: list[CallbackTarget] = []
        with self._connect() as connection:
            for work_ref, action in targets:
                normalized_ref = _safe_text(work_ref, limit=160)
                normalized_action = _safe_text(action, limit=32).lower()
                if normalized_action not in ALLOWED_ACTIONS:
                    raise ValueError("Unsupported work action")
                if not WORK_REF_PATTERN.fullmatch(normalized_ref):
                    raise ValueError("workRef is invalid")
                token = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO telegram_work_callbacks
                      (token, telegram_user_id, chat_id, work_ref, action, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (token, user_id, normalized_chat_id, normalized_ref, normalized_action, expires_at),
                )
                issued.append(CallbackTarget(token, normalized_ref, normalized_action))
            connection.execute(
                """
                DELETE FROM telegram_work_callbacks
                WHERE expires_at < ? OR action_state = 'succeeded'
                """,
                (time.time() if now is None else float(now),),
            )
        return tuple(issued)

    def issue_page(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        cursor: str,
        now: Optional[float] = None,
    ) -> str:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        normalized_cursor = _safe_text(cursor, limit=2048)
        if not normalized_cursor or not re.fullmatch(r"[A-Za-z0-9._~:@+\-]+", normalized_cursor):
            raise ValueError("Active work cursor is invalid")
        token = str(uuid.uuid4())
        current = time.time() if now is None else float(now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_work_pages
                  (token, telegram_user_id, chat_id, cursor, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token, user_id, normalized_chat_id, normalized_cursor, current + self.ttl_s),
            )
            connection.execute(
                "DELETE FROM telegram_work_pages WHERE expires_at < ? OR fetch_state = 'succeeded'",
                (current,),
            )
        return token

    def reserve_page(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        now: Optional[float] = None,
    ) -> Optional[PageReservation]:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        current = time.time() if now is None else float(now)
        normalized_token = _safe_text(token, limit=64)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT token, cursor, fetch_state, lease_until
                FROM telegram_work_pages
                WHERE token = ? AND telegram_user_id = ? AND chat_id = ?
                  AND expires_at >= ?
                """,
                (normalized_token, user_id, normalized_chat_id, current),
            ).fetchone()
            if row is None:
                return None
            state = str(row["fetch_state"] or "available")
            if state in {"succeeded", "failed"}:
                return None
            lease_until = float(row["lease_until"] or 0)
            if state == "executing" and lease_until > current:
                return None
            connection.execute(
                """
                UPDATE telegram_work_pages
                SET fetch_state = 'executing', lease_until = ?, consumed_at = NULL
                WHERE token = ?
                """,
                (current + self.action_lease_s, row["token"]),
            )
        return PageReservation(
            token=str(row["token"]),
            cursor=str(row["cursor"]),
            replay=state in {"executing", "uncertain", "failed"},
        )

    def complete_page(
        self,
        reservation: PageReservation,
        *,
        succeeded: bool,
        definitive: bool = True,
        now: Optional[float] = None,
    ) -> None:
        current = time.time() if now is None else float(now)
        state = "succeeded" if succeeded else ("failed" if definitive else "uncertain")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE telegram_work_pages
                SET fetch_state = ?, lease_until = NULL, completed_at = ?, consumed_at = ?
                WHERE token = ?
                """,
                (
                    state,
                    current if succeeded or definitive else None,
                    current if succeeded else None,
                    reservation.token,
                ),
            )

    def consume_page(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        now: Optional[float] = None,
    ) -> Optional[str]:
        reservation = self.reserve_page(
            token,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            now=now,
        )
        if reservation is None:
            return None
        self.complete_page(reservation, succeeded=True, now=now)
        return reservation.cursor

    def reserve_action(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        now: Optional[float] = None,
    ) -> Optional[ActionReservation]:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        current = time.time() if now is None else float(now)
        normalized_token = _safe_text(token, limit=64)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT token, work_ref, action, action_state, operation_id, lease_until
                FROM telegram_work_callbacks
                WHERE token = ? AND telegram_user_id = ? AND chat_id = ?
                  AND prompt_message_id IS NULL AND expires_at >= ?
                """,
                (normalized_token, user_id, normalized_chat_id, current),
            ).fetchone()
            if row is None:
                return None
            state = str(row["action_state"] or "available")
            if state in {"succeeded", "failed"}:
                return None
            lease_until = float(row["lease_until"] or 0)
            if state == "executing" and lease_until > current:
                return None
            operation_id = str(row["operation_id"] or row["token"])
            replay = state in {"executing", "uncertain"} or bool(row["operation_id"])
            connection.execute(
                """
                UPDATE telegram_work_callbacks
                SET action_state = 'executing', operation_id = ?, lease_until = ?,
                    consumed_at = NULL
                WHERE token = ?
                """,
                (operation_id, current + self.action_lease_s, row["token"]),
            )
        return ActionReservation(
            CallbackTarget(row["token"], row["work_ref"], row["action"]),
            operation_id,
            replay,
        )

    def complete_action(
        self,
        reservation: ActionReservation,
        *,
        succeeded: bool,
        definitive: bool = True,
        receipt: str = "",
        now: Optional[float] = None,
    ) -> None:
        current = time.time() if now is None else float(now)
        state = "succeeded" if succeeded else ("failed" if definitive else "uncertain")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE telegram_work_callbacks
                SET action_state = ?, lease_until = NULL, receipt = ?,
                    completed_at = ?, consumed_at = ?
                WHERE token = ? AND operation_id = ?
                """,
                (
                    state,
                    _safe_text(receipt, limit=1000),
                    current if succeeded or definitive else None,
                    current if succeeded or definitive else None,
                    reservation.target.token,
                    reservation.operation_id,
                ),
            )

    def consume_action(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        now: Optional[float] = None,
    ) -> Optional[CallbackTarget]:
        """Compatibility helper for non-network confirmation/setup call sites."""

        reservation = self.reserve_action(
            token,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            now=now,
        )
        if reservation is None:
            return None
        self.complete_action(reservation, succeeded=True, receipt="consumed", now=now)
        return reservation.target

    def issue_prompt(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        prompt_message_id: str,
        work_ref: str,
        action: str,
        now: Optional[float] = None,
    ) -> CallbackTarget:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        normalized_action = _safe_text(action, limit=32).lower()
        if normalized_action not in INSTRUCTION_ACTIONS:
            raise ValueError("Unsupported instruction action")
        normalized_prompt_id = _safe_text(prompt_message_id, limit=64)
        normalized_ref = _safe_text(work_ref, limit=160)
        if not normalized_prompt_id or not WORK_REF_PATTERN.fullmatch(normalized_ref):
            raise ValueError("prompt_message_id and workRef are required")
        token = str(uuid.uuid4())
        current = time.time() if now is None else float(now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_work_callbacks
                  (token, telegram_user_id, chat_id, prompt_message_id, work_ref, action, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    user_id,
                    normalized_chat_id,
                    normalized_prompt_id,
                    normalized_ref,
                    normalized_action,
                    current + self.ttl_s,
                ),
            )
        return CallbackTarget(token, normalized_ref, normalized_action)

    def reserve_prompt(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        work_ref: str,
        action: str,
        now: Optional[float] = None,
    ) -> CallbackTarget:
        """Persist instruction authority before Telegram sends the ForceReply prompt."""

        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        normalized_action = _safe_text(action, limit=32).lower()
        if normalized_action not in INSTRUCTION_ACTIONS:
            raise ValueError("Unsupported instruction action")
        normalized_ref = _safe_text(work_ref, limit=160)
        if not WORK_REF_PATTERN.fullmatch(normalized_ref):
            raise ValueError("workRef is invalid")
        token = str(uuid.uuid4())
        current = time.time() if now is None else float(now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_work_callbacks
                  (token, telegram_user_id, chat_id, prompt_message_id, work_ref, action, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    user_id,
                    normalized_chat_id,
                    token,
                    normalized_ref,
                    normalized_action,
                    current + self.ttl_s,
                ),
            )
        return CallbackTarget(token, normalized_ref, normalized_action)

    def consume_prompt(
        self,
        *,
        telegram_user_id: str,
        chat_id: str,
        prompt_message_id: str,
        now: Optional[float] = None,
    ) -> Optional[CallbackTarget]:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        current = time.time() if now is None else float(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT token, work_ref, action FROM telegram_work_callbacks
                WHERE telegram_user_id = ? AND chat_id = ? AND prompt_message_id = ?
                  AND consumed_at IS NULL AND expires_at >= ?
                ORDER BY rowid DESC LIMIT 1
                """,
                (
                    user_id,
                    normalized_chat_id,
                    _safe_text(prompt_message_id, limit=64),
                    current,
                ),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE telegram_work_callbacks SET consumed_at = ? WHERE token = ? AND consumed_at IS NULL",
                (current, row["token"]),
            )
        return CallbackTarget(row["token"], row["work_ref"], row["action"])

    def consume_prompt_token(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        now: Optional[float] = None,
    ) -> Optional[CallbackTarget]:
        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        current = time.time() if now is None else float(now)
        normalized_token = _safe_text(token, limit=64)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT token, work_ref, action FROM telegram_work_callbacks
                WHERE token = ? AND telegram_user_id = ? AND chat_id = ?
                  AND prompt_message_id IS NOT NULL AND consumed_at IS NULL AND expires_at >= ?
                """,
                (normalized_token, user_id, normalized_chat_id, current),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE telegram_work_callbacks SET consumed_at = ? WHERE token = ? AND consumed_at IS NULL",
                (current, row["token"]),
            )
        return CallbackTarget(row["token"], row["work_ref"], row["action"])

    def reserve_prompt_action(
        self,
        token: str,
        *,
        telegram_user_id: str,
        chat_id: str,
        instruction: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Optional[tuple[ActionReservation, str]]:
        """Reserve an instruction action while retaining its exact operation and instruction.

        The first ForceReply stores the instruction atomically with the reservation. A retry after
        a transport loss or process restart may omit it and reuses the stored instruction plus the
        original operation id. A changed instruction never mutates an in-flight operation.
        """

        user_id, normalized_chat_id = self._scope(telegram_user_id, chat_id)
        current = time.time() if now is None else float(now)
        normalized_token = _safe_text(token, limit=64)
        supplied_instruction = _safe_text(instruction, limit=8000)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT token, work_ref, action, action_state, operation_id, lease_until,
                       instruction
                FROM telegram_work_callbacks
                WHERE token = ? AND telegram_user_id = ? AND chat_id = ?
                  AND prompt_message_id IS NOT NULL AND expires_at >= ?
                """,
                (normalized_token, user_id, normalized_chat_id, current),
            ).fetchone()
            if row is None:
                return None
            state = str(row["action_state"] or "available")
            if state in {"succeeded", "failed"}:
                return None
            lease_until = float(row["lease_until"] or 0)
            if state == "executing" and lease_until > current:
                return None
            stored_instruction = _safe_text(row["instruction"], limit=8000)
            if stored_instruction and supplied_instruction and stored_instruction != supplied_instruction:
                return None
            effective_instruction = stored_instruction or supplied_instruction
            if not effective_instruction:
                return None
            operation_id = str(row["operation_id"] or row["token"])
            replay = state in {"executing", "uncertain"} or bool(row["operation_id"])
            connection.execute(
                """
                UPDATE telegram_work_callbacks
                SET action_state = 'executing', operation_id = ?, lease_until = ?,
                    instruction = ?, consumed_at = NULL
                WHERE token = ?
                """,
                (
                    operation_id,
                    current + self.action_lease_s,
                    effective_instruction,
                    row["token"],
                ),
            )
        return (
            ActionReservation(
                CallbackTarget(row["token"], row["work_ref"], row["action"]),
                operation_id,
                replay,
            ),
            effective_instruction,
        )

    @staticmethod
    def _scope(telegram_user_id: str, chat_id: str) -> tuple[str, str]:
        user_id = _safe_text(telegram_user_id, limit=128)
        normalized_chat_id = _safe_text(chat_id, limit=128)
        if not user_id or not normalized_chat_id:
            raise ValueError("Telegram user and chat scope are required")
        return user_id, normalized_chat_id


def action_callback_data(token: str) -> str:
    normalized = _safe_text(token, limit=48)
    if not normalized:
        raise ValueError("callback token is required")
    data = f"PW:A:{normalized}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("Telegram callback_data exceeds 64 bytes")
    return data


def confirmation_callback_data(token: str, confirmed: bool) -> str:
    normalized = _safe_text(token, limit=48)
    if not normalized:
        raise ValueError("callback token is required")
    data = f"PW:C:{'Y' if confirmed else 'N'}:{normalized}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("Telegram callback_data exceeds 64 bytes")
    return data


def prompt_retry_callback_data(token: str) -> str:
    normalized = _safe_text(token, limit=48)
    if not normalized:
        raise ValueError("callback token is required")
    data = f"PW:R:{normalized}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("Telegram callback_data exceeds 64 bytes")
    return data


def page_callback_data(token: str) -> str:
    normalized = _safe_text(token, limit=48)
    if not normalized:
        raise ValueError("page token is required")
    data = f"PW:P:{normalized}"
    if len(data.encode("utf-8")) > 64:
        raise ValueError("Telegram callback_data exceeds 64 bytes")
    return data
