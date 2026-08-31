import asyncio
import fcntl
import hashlib
import re
import os
import sys
import warnings
sys.dont_write_bytecode = True
# Suppress non-critical warnings from third-party libraries
warnings.filterwarnings("ignore", category=SyntaxWarning, module="md2tgmd")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telegram.ext._application")
import base64
import json
import sqlite3
import time
import uuid
import logging
import traceback
import utils.decorators as decorators
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Optional
from datetime import datetime, timezone
from pathlib import Path

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
from utils.tts import resolve_tts_selection, summarize_voice_markup, synthesize_speech
from utils.livekit_bridge import LiveKitBridge
from utils.env import coerce_bool
from local_qa_service_ack import acknowledge_local_qa_service
from utils.singleton import (
    SingletonAlreadyRunning,
    acquire_telegram_singleton_lock,
    cancel_telegram_singleton_readiness,
    clear_telegram_singleton_receipt,
    schedule_telegram_singleton_readiness,
)
# === VIVENTIUM START ===
# Feature: Centralized voice reply gating helper.
from utils.voice import (
    normalize_delivery_disposition,
    normalize_voice_preference,
    resolve_delivery_audio_gate,
    should_request_audio_reply,
    should_send_voice_reply,
)
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Feature: Telegram account linking flow + citation-safe formatting helpers.
from utils.librechat_bridge import (
    TelegramLinkRequired,
    render_telegram_markdown,
    sanitize_telegram_display_text,
    sanitize_telegram_text,
    is_no_response_only,
    strip_trailing_nta,
)
from utils.telegram_html import strip_html_tags
from utils.telegram_chunks import first_telegram_html_chunk, split_telegram_html
from utils.tr014_local_qa import (
    TR014_LOCAL_QA_MODE,
    SyntheticTelegramSourceEvent,
    maybe_delay_tr014_core_ingestion,
)
from utils.orchestration import (
    CONFIRM_ACTIONS,
    INSTRUCTION_ACTIONS,
    ActionReservation,
    CallbackCapabilityStore,
    OrchestrationClient,
    OrchestrationError,
    OrchestrationLinkRequired,
    action_callback_data,
    confirmation_callback_data,
    default_callback_store_path,
    format_active_work,
    format_parallel_work_settings,
    page_callback_data,
    prompt_retry_callback_data,
    safe_link_url,
)
from utils.librechat_attachments import (
    fetch_librechat_bytes,
    send_librechat_attachments,
)
from delivery_controls import parse_delivery_controls, strip_incomplete_control_suffix

_PENDING_INFO_CALL_REFRESHES = set()
TELEGRAM_DELIVERY_INTERRUPTED_NOTICE = (
    "I couldn't finish delivering that response. Please try again."
)


def _telegram_source_event_id(chat_id, message_id=None, update_id=None) -> str:
    """Build a stable opaque ingress identity without authoring trusted turn policy."""

    chat_part = str(chat_id or "").strip()
    if message_id is not None and str(message_id).strip():
        return f"telegram:chat:{chat_part}:message:{str(message_id).strip()}"
    if update_id is not None and str(update_id).strip():
        return f"telegram:update:{str(update_id).strip()}"
    return ""

# === VIVENTIUM START ===
# Feature: Telegram source-order presentation fence.
# Purpose: Telegram message numbers are authoritative before Core finishes admitting a later
# revision. Keep only the newest user source per chat/topic and recheck it before any visible send.
_LATEST_TELEGRAM_SOURCE_MESSAGES: dict[tuple[str, str, str], dict[str, Any]] = {}
_TELEGRAM_PRESENTATION_MUTEXES: dict[tuple[str, str], asyncio.Lock] = {}
_TELEGRAM_PRESENTATION_MUTEX_USERS: dict[tuple[str, str], int] = {}
_TELEGRAM_HELD_PRESENTATION_FENCES: set[tuple[str, str]] = set()
_TELEGRAM_PRESENTATION_LOCK_SLOTS = 4096
_TELEGRAM_PROCESS_ID_PID = os.getpid()
_TELEGRAM_PROCESS_ID = f"{_TELEGRAM_PROCESS_ID_PID}:{time.monotonic_ns()}:{uuid.uuid4().hex}"


def _telegram_process_start_identity() -> str:
    global _TELEGRAM_PROCESS_ID_PID, _TELEGRAM_PROCESS_ID
    current_pid = os.getpid()
    if current_pid != _TELEGRAM_PROCESS_ID_PID:
        _TELEGRAM_PROCESS_ID_PID = current_pid
        _TELEGRAM_PROCESS_ID = f"{current_pid}:{time.monotonic_ns()}:{uuid.uuid4().hex}"
    return _TELEGRAM_PROCESS_ID


def _telegram_presentation_lock_file(store_path, chat_id, message_id) -> Path:
    ledger_path = Path(store_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(ledger_path.parent, 0o700)
    lock_root = ledger_path.parent / f".{ledger_path.name}.presentation-locks"
    lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(lock_root, 0o700)
    identity_hash = hashlib.sha256(
        f"{str(chat_id)}\0{str(message_id)}".encode("utf-8")
    ).digest()
    slot = int.from_bytes(identity_hash[:8], "big") % _TELEGRAM_PRESENTATION_LOCK_SLOTS
    return lock_root / f"{slot:04x}.lock"


def _telegram_presentation_fence_key(store_path, chat_id, message_id) -> tuple[str, str]:
    return (str(Path(store_path).resolve()), f"{str(chat_id)}:{str(message_id)}")


def _open_telegram_presentation_lock(store_path, chat_id, message_id) -> int:
    lock_path = _telegram_presentation_lock_file(store_path, chat_id, message_id)
    descriptor = os.open(
        lock_path,
        os.O_CREAT
        | os.O_RDWR
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.chmod(lock_path, 0o600)
    return descriptor


def _telegram_existing_message_fence_is_held(store_path, chat_id, message_id) -> bool:
    key = _telegram_presentation_fence_key(store_path, chat_id, message_id)
    if key in _TELEGRAM_HELD_PRESENTATION_FENCES:
        return True
    lock_path = _telegram_presentation_lock_file(store_path, chat_id, message_id)
    if not lock_path.exists():
        return False
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


@asynccontextmanager
async def _telegram_existing_message_fence(store_path, chat_id, message_id):
    """Serialize one existing Telegram message until this exact process exits or returns."""

    key = _telegram_presentation_fence_key(store_path, chat_id, message_id)
    mutex = _TELEGRAM_PRESENTATION_MUTEXES.setdefault(key, asyncio.Lock())
    _TELEGRAM_PRESENTATION_MUTEX_USERS[key] = _TELEGRAM_PRESENTATION_MUTEX_USERS.get(key, 0) + 1
    descriptor = None
    try:
        async with mutex:
            descriptor = _open_telegram_presentation_lock(store_path, chat_id, message_id)
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(0.01)
            process_identity = _telegram_process_start_identity().encode("utf-8")
            os.ftruncate(descriptor, 0)
            os.write(descriptor, process_identity)
            os.fsync(descriptor)
            _TELEGRAM_HELD_PRESENTATION_FENCES.add(key)
            try:
                yield
            finally:
                _TELEGRAM_HELD_PRESENTATION_FENCES.discard(key)
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
                descriptor = None
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        remaining = _TELEGRAM_PRESENTATION_MUTEX_USERS.get(key, 1) - 1
        if remaining <= 0:
            _TELEGRAM_PRESENTATION_MUTEX_USERS.pop(key, None)
            if _TELEGRAM_PRESENTATION_MUTEXES.get(key) is mutex and not mutex.locked():
                _TELEGRAM_PRESENTATION_MUTEXES.pop(key, None)
        else:
            _TELEGRAM_PRESENTATION_MUTEX_USERS[key] = remaining


def _telegram_source_order_key(
    chat_id, message_thread_id=None, telegram_user_id=None
) -> tuple[str, str, str]:
    return (
        str(chat_id or ""),
        str(message_thread_id or ""),
        str(telegram_user_id or ""),
    )


def _telegram_source_cache_ttl_s() -> float:
    try:
        value = float(os.getenv("VIVENTIUM_TELEGRAM_SOURCE_CACHE_TTL_S", "3600"))
    except (TypeError, ValueError):
        value = 3600.0
    return max(1.0, min(value, 86400.0))


def _cleanup_telegram_source_order_cache(now: Optional[float] = None) -> None:
    current = time.monotonic() if now is None else float(now)
    for key, entry in list(_LATEST_TELEGRAM_SOURCE_MESSAGES.items()):
        if int(entry.get("active", 0)) <= 0 and float(entry.get("expires_at", 0)) <= current:
            _LATEST_TELEGRAM_SOURCE_MESSAGES.pop(key, None)


def _note_telegram_source_message(
    chat_id, message_thread_id, message_id, telegram_user_id=None
) -> int:
    try:
        sequence = int(message_id)
    except (TypeError, ValueError):
        return 0
    now = time.monotonic()
    _cleanup_telegram_source_order_cache(now)
    key = _telegram_source_order_key(chat_id, message_thread_id, telegram_user_id)
    existing = _LATEST_TELEGRAM_SOURCE_MESSAGES.get(key, {})
    _LATEST_TELEGRAM_SOURCE_MESSAGES[key] = {
        "sequence": max(sequence, int(existing.get("sequence", 0))),
        "expires_at": now + _telegram_source_cache_ttl_s(),
        "active": int(existing.get("active", 0)),
    }
    return sequence


def _activate_telegram_source_message(
    chat_id, message_thread_id, message_id, telegram_user_id=None
) -> tuple[str, str, str]:
    _note_telegram_source_message(chat_id, message_thread_id, message_id, telegram_user_id)
    key = _telegram_source_order_key(chat_id, message_thread_id, telegram_user_id)
    entry = _LATEST_TELEGRAM_SOURCE_MESSAGES[key]
    entry["active"] = int(entry.get("active", 0)) + 1
    return key


def _release_telegram_source_message(key: tuple[str, str, str]) -> None:
    entry = _LATEST_TELEGRAM_SOURCE_MESSAGES.get(key)
    if not entry:
        return
    entry["active"] = max(0, int(entry.get("active", 0)) - 1)
    entry["expires_at"] = time.monotonic() + _telegram_source_cache_ttl_s()
    _cleanup_telegram_source_order_cache()


def _is_newest_telegram_source_message(
    chat_id, message_thread_id, message_id, telegram_user_id=None
) -> bool:
    try:
        sequence = int(message_id)
    except (TypeError, ValueError):
        return True
    now = time.monotonic()
    _cleanup_telegram_source_order_cache(now)
    keys = [_telegram_source_order_key(chat_id, message_thread_id, telegram_user_id)]
    if telegram_user_id:
        keys.append(_telegram_source_order_key(chat_id, message_thread_id, None))
    entries = [_LATEST_TELEGRAM_SOURCE_MESSAGES.get(key) for key in keys]
    entries = [entry for entry in entries if entry]
    if not entries:
        return True
    for entry in entries:
        entry["expires_at"] = now + _telegram_source_cache_ttl_s()
    latest = max(int(entry.get("sequence", sequence)) for entry in entries)
    return sequence >= latest


class _TelegramRetractionStore:
    """Small durable retry ledger for Telegram messages that could not be deleted."""

    def __init__(self, path=None, *, ttl_s=604800, retry_delay_s=5):
        configured = path or os.getenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH")
        self.path = Path(configured) if configured else default_callback_store_path().with_name(
            "source-order-retractions.sqlite3"
        )
        self.ttl_s = max(60, int(ttl_s))
        self.retry_delay_s = max(0, int(retry_delay_s))

    def _repair_private_modes(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        os.chmod(self.path, 0o600)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{self.path}{suffix}")
            if sidecar.exists():
                os.chmod(sidecar, 0o600)

    def _preserve_live_presentation_operations(self, connection, now: float) -> None:
        rows = connection.execute(
            """
            SELECT telegram_user_id, chat_id, thread_id, source_sequence, operation_key
            FROM telegram_source_presentation_operations
            WHERE operation_token != '' AND expires_at <= ? AND operation_key LIKE 'message:%'
            """,
            (now,),
        ).fetchall()
        for telegram_user_id, chat_id, thread_id, source_sequence, operation_key in rows:
            prefix = f"message:{chat_id}:"
            if not str(operation_key).startswith(prefix):
                continue
            message_id = str(operation_key)[len(prefix):]
            if not message_id or not _telegram_existing_message_fence_is_held(
                self.path, chat_id, message_id
            ):
                continue
            preserved_until = now + self.ttl_s
            connection.execute(
                """
                UPDATE telegram_source_presentation_operations
                SET expires_at = ?
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND operation_key = ? AND operation_token != ''
                """,
                (
                    preserved_until,
                    telegram_user_id,
                    chat_id,
                    thread_id,
                    source_sequence,
                    operation_key,
                ),
            )
            connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET expires_at = MAX(expires_at, ?)
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ?
                """,
                (
                    preserved_until,
                    telegram_user_id,
                    chat_id,
                    thread_id,
                    source_sequence,
                ),
            )

    def _connect(self):
        self._repair_private_modes()
        connection = sqlite3.connect(str(self.path), timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_source_retractions (
              chat_id TEXT NOT NULL,
              message_id TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              next_attempt_at REAL NOT NULL,
              expires_at REAL NOT NULL,
              PRIMARY KEY (chat_id, message_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_source_retry_terminals (
              telegram_user_id TEXT NOT NULL,
              chat_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              source_sequence INTEGER NOT NULL,
              message_id TEXT NOT NULL,
              expires_at REAL NOT NULL,
              PRIMARY KEY (telegram_user_id, chat_id, thread_id, source_sequence)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_source_pending_terminals (
              telegram_user_id TEXT NOT NULL,
              chat_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              source_sequence INTEGER NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              next_attempt_at REAL NOT NULL,
              claimed_until REAL NOT NULL DEFAULT 0,
              claim_token TEXT NOT NULL DEFAULT '',
              claim_generation INTEGER NOT NULL DEFAULT 0,
              presentation_refs TEXT NOT NULL DEFAULT '[]',
              expires_at REAL NOT NULL,
              PRIMARY KEY (telegram_user_id, chat_id, thread_id, source_sequence)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_source_presentation_operations (
              telegram_user_id TEXT NOT NULL,
              chat_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              source_sequence INTEGER NOT NULL,
              operation_key TEXT NOT NULL,
              operation_kind TEXT NOT NULL,
              operation_token TEXT NOT NULL DEFAULT '',
              operation_generation INTEGER NOT NULL DEFAULT 0,
              recovery_claim_token TEXT NOT NULL DEFAULT '',
              recovery_claim_generation INTEGER NOT NULL DEFAULT 0,
              prior_claimed_until REAL NOT NULL DEFAULT 0,
              safe_until REAL NOT NULL DEFAULT 0,
              expires_at REAL NOT NULL,
              PRIMARY KEY (
                telegram_user_id, chat_id, thread_id, source_sequence, operation_key
              )
            )
            """
        )
        pending_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(telegram_source_pending_terminals)"
            ).fetchall()
        }
        for column, declaration in (
            ("claim_token", "TEXT NOT NULL DEFAULT ''"),
            ("claim_generation", "INTEGER NOT NULL DEFAULT 0"),
            ("presentation_refs", "TEXT NOT NULL DEFAULT '[]'"),
        ):
            if column not in pending_columns:
                connection.execute(
                    f"ALTER TABLE telegram_source_pending_terminals ADD COLUMN {column} {declaration}"
                )
        now = time.time()
        self._preserve_live_presentation_operations(connection, now)
        connection.execute(
            "DELETE FROM telegram_source_retractions WHERE expires_at <= ?", (time.time(),)
        )
        connection.execute(
            "DELETE FROM telegram_source_retry_terminals WHERE expires_at <= ?", (time.time(),)
        )
        connection.execute(
            "DELETE FROM telegram_source_pending_terminals WHERE expires_at <= ?", (now,)
        )
        connection.execute(
            "DELETE FROM telegram_source_presentation_operations WHERE expires_at <= ?",
            (now,),
        )
        connection.execute(
            """
            DELETE FROM telegram_source_pending_terminals
            WHERE EXISTS (
              SELECT 1 FROM telegram_source_retry_terminals AS delivered
              WHERE delivered.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                AND delivered.chat_id = telegram_source_pending_terminals.chat_id
                AND delivered.thread_id = telegram_source_pending_terminals.thread_id
                AND delivered.source_sequence = telegram_source_pending_terminals.source_sequence
            )
            """
        )
        connection.commit()
        self._repair_private_modes()
        return connection

    def enqueue(self, chat_id, message_id) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_source_retractions
                  (chat_id, message_id, attempts, next_attempt_at, expires_at)
                VALUES (?, ?, 0, ?, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                  next_attempt_at = MIN(next_attempt_at, excluded.next_attempt_at),
                  expires_at = MAX(expires_at, excluded.expires_at)
                """,
                (str(chat_id), str(message_id), now, now + self.ttl_s),
            )

    def due(self, limit=25) -> list[tuple[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chat_id, message_id
                FROM telegram_source_retractions
                WHERE next_attempt_at <= ?
                ORDER BY next_attempt_at, chat_id, message_id
                LIMIT ?
                """,
                (time.time(), max(1, min(int(limit), 100))),
            ).fetchall()
        return [
            (chat_id, int(message_id) if str(message_id).lstrip("-").isdigit() else message_id)
            for chat_id, message_id in rows
        ]

    def mark_deleted(self, chat_id, message_id) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM telegram_source_retractions WHERE chat_id = ? AND message_id = ?",
                (str(chat_id), str(message_id)),
            )

    def reschedule(self, chat_id, message_id) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE telegram_source_retractions
                SET attempts = attempts + 1, next_attempt_at = ?
                WHERE chat_id = ? AND message_id = ?
                """,
                (time.time() + self.retry_delay_s, str(chat_id), str(message_id)),
            )

    def pending_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM telegram_source_retractions").fetchone()[0])

    def remember_retry_terminal(
        self, *, telegram_user_id, chat_id, thread_id, source_sequence, message_id
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_source_retry_terminals
                  (telegram_user_id, chat_id, thread_id, source_sequence, message_id, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id, chat_id, thread_id, source_sequence) DO UPDATE SET
                  message_id = excluded.message_id,
                  expires_at = excluded.expires_at
                """,
                (
                    str(telegram_user_id),
                    str(chat_id),
                    str(thread_id or ""),
                    int(source_sequence),
                    str(message_id),
                    time.time() + self.ttl_s,
                ),
            )

    def obsolete_retry_terminals(
        self, *, telegram_user_id, chat_id, thread_id, source_sequence
    ) -> list[tuple[str, Any, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chat_id, message_id, source_sequence
                FROM telegram_source_retry_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence < ?
                ORDER BY source_sequence
                """,
                (
                    str(telegram_user_id),
                    str(chat_id),
                    str(thread_id or ""),
                    int(source_sequence),
                ),
            ).fetchall()
        return [
            (
                row_chat_id,
                int(message_id) if str(message_id).lstrip("-").isdigit() else message_id,
                int(sequence),
            )
            for row_chat_id, message_id, sequence in rows
        ]

    def forget_retry_terminal(
        self, *, telegram_user_id, chat_id, thread_id, source_sequence
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM telegram_source_retry_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ?
                """,
                (
                    str(telegram_user_id),
                    str(chat_id),
                    str(thread_id or ""),
                    int(source_sequence),
                ),
            )

    def remember_pending_terminal(
        self,
        *,
        telegram_user_id,
        chat_id,
        thread_id,
        source_sequence,
        presentation_refs=None,
    ) -> None:
        now = time.time()
        encoded_refs = json.dumps(list(presentation_refs or []), separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO telegram_source_pending_terminals
                  (telegram_user_id, chat_id, thread_id, source_sequence,
                   attempts, next_attempt_at, claimed_until, claim_token,
                   claim_generation, presentation_refs, expires_at)
                VALUES (?, ?, ?, ?, 0, ?, 0, '', 0, ?, ?)
                ON CONFLICT(telegram_user_id, chat_id, thread_id, source_sequence) DO UPDATE SET
                  next_attempt_at = MIN(next_attempt_at, excluded.next_attempt_at),
                  presentation_refs = CASE
                    WHEN excluded.presentation_refs = '[]' THEN presentation_refs
                    ELSE excluded.presentation_refs
                  END,
                  expires_at = MAX(expires_at, excluded.expires_at)
                """,
                (
                    str(telegram_user_id),
                    str(chat_id),
                    str(thread_id or ""),
                    int(source_sequence),
                    now,
                    encoded_refs,
                    now + self.ttl_s,
                ),
            )

    def claim_pending_terminals(
        self, *, limit=25, lease_s=30
    ) -> list[dict[str, Any]]:
        now = time.time()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT telegram_user_id, chat_id, thread_id, source_sequence,
                       claim_generation, presentation_refs
                FROM telegram_source_pending_terminals AS pending
                WHERE next_attempt_at <= ? AND claimed_until <= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = pending.telegram_user_id
                      AND operation.chat_id = pending.chat_id
                      AND operation.thread_id = pending.thread_id
                      AND operation.source_sequence = pending.source_sequence
                      AND operation.operation_token != ''
                      AND operation.safe_until > ?
                  )
                ORDER BY next_attempt_at, telegram_user_id, chat_id, thread_id, source_sequence
                LIMIT ?
                """,
                (now, now, now, max(1, min(int(limit), 100))),
            ).fetchall()
            claimed = []
            for (
                telegram_user_id,
                chat_id,
                thread_id,
                source_sequence,
                claim_generation,
                presentation_refs,
            ) in rows:
                claim_token = uuid.uuid4().hex
                next_generation = int(claim_generation) + 1
                cursor = connection.execute(
                    """
                    UPDATE telegram_source_pending_terminals
                    SET claimed_until = ?, claim_token = ?, claim_generation = ?
                    WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                      AND source_sequence = ? AND claimed_until <= ?
                      AND NOT EXISTS (
                        SELECT 1 FROM telegram_source_presentation_operations AS operation
                        WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                          AND operation.chat_id = telegram_source_pending_terminals.chat_id
                          AND operation.thread_id = telegram_source_pending_terminals.thread_id
                          AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                          AND operation.operation_token != ''
                          AND operation.safe_until > ?
                      )
                    """,
                    (
                        now + max(1, int(lease_s)),
                        claim_token,
                        next_generation,
                        telegram_user_id,
                        chat_id,
                        thread_id,
                        source_sequence,
                        now,
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    try:
                        decoded_refs = json.loads(presentation_refs or "[]")
                    except (TypeError, ValueError):
                        decoded_refs = []
                    claimed.append({
                        "telegram_user_id": telegram_user_id,
                        "chat_id": chat_id,
                        "thread_id": thread_id,
                        "source_sequence": int(source_sequence),
                        "claim_token": claim_token,
                        "claim_generation": next_generation,
                        "presentation_refs": decoded_refs if isinstance(decoded_refs, list) else [],
                    })
            connection.commit()
            return claimed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def reserve_pending_terminal(
        self,
        *,
        telegram_user_id,
        chat_id,
        thread_id,
        source_sequence,
        presentation_refs,
        lease_s=30,
    ):
        now = time.time()
        identity = (
            str(telegram_user_id),
            str(chat_id),
            str(thread_id or ""),
            int(source_sequence),
        )
        encoded_refs = json.dumps(list(presentation_refs or []), separators=(",", ":"))
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO telegram_source_pending_terminals
                  (telegram_user_id, chat_id, thread_id, source_sequence,
                   attempts, next_attempt_at, claimed_until, claim_token,
                   claim_generation, presentation_refs, expires_at)
                VALUES (?, ?, ?, ?, 0, ?, 0, '', 0, ?, ?)
                ON CONFLICT(telegram_user_id, chat_id, thread_id, source_sequence) DO UPDATE SET
                  next_attempt_at = MIN(next_attempt_at, excluded.next_attempt_at),
                  presentation_refs = excluded.presentation_refs,
                  expires_at = MAX(expires_at, excluded.expires_at)
                """,
                (*identity, now, encoded_refs, now + self.ttl_s),
            )
            row = connection.execute(
                """
                SELECT claimed_until, claim_generation,
                       EXISTS (
                         SELECT 1 FROM telegram_source_presentation_operations AS operation
                         WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                           AND operation.chat_id = telegram_source_pending_terminals.chat_id
                           AND operation.thread_id = telegram_source_pending_terminals.thread_id
                           AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                           AND operation.operation_token != ''
                           AND operation.safe_until > ?
                       )
                FROM telegram_source_pending_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ?
                """,
                (now, *identity),
            ).fetchone()
            if row is None or float(row[0]) > now or bool(row[2]):
                connection.commit()
                return None
            claim_token = uuid.uuid4().hex
            claim_generation = int(row[1]) + 1
            connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET claimed_until = ?, claim_token = ?, claim_generation = ?
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claimed_until <= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                      AND operation.chat_id = telegram_source_pending_terminals.chat_id
                      AND operation.thread_id = telegram_source_pending_terminals.thread_id
                      AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                      AND operation.operation_token != ''
                      AND operation.safe_until > ?
                  )
                """,
                (
                    now + max(1, int(lease_s)),
                    claim_token,
                    claim_generation,
                    *identity,
                    now,
                    now,
                ),
            )
            connection.commit()
            return {
                "telegram_user_id": identity[0],
                "chat_id": identity[1],
                "thread_id": identity[2],
                "source_sequence": identity[3],
                "claim_token": claim_token,
                "claim_generation": claim_generation,
                "presentation_refs": list(presentation_refs or []),
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def begin_presentation_operation(
        self, claim, *, operation_key, operation_kind, lease_s
    ):
        now = time.time()
        identity = (
            str(claim["telegram_user_id"]),
            str(claim["chat_id"]),
            str(claim.get("thread_id") or ""),
            int(claim["source_sequence"]),
        )
        normalized_key = str(operation_key or "")[:256]
        normalized_kind = str(operation_kind or "")[:64]
        if not normalized_key or not normalized_kind:
            return None
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                """
                SELECT claimed_until
                FROM telegram_source_pending_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                """,
                (
                    *identity,
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                ),
            ).fetchone()
            active_operation = connection.execute(
                """
                SELECT 1
                FROM telegram_source_presentation_operations
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND operation_token != '' AND safe_until > ?
                LIMIT 1
                """,
                (*identity, now),
            ).fetchone()
            if pending is None or active_operation is not None:
                connection.rollback()
                return None
            generation_row = connection.execute(
                """
                SELECT operation_generation
                FROM telegram_source_presentation_operations
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND operation_key = ?
                """,
                (*identity, normalized_key),
            ).fetchone()
            operation_generation = int(generation_row[0] if generation_row else 0) + 1
            operation_token = uuid.uuid4().hex
            prior_claimed_until = float(pending[0])
            safe_until = now + max(2, min(int(lease_s), 300))
            operation_expires_at = max(now + self.ttl_s, safe_until + 60)
            connection.execute(
                """
                INSERT INTO telegram_source_presentation_operations
                  (telegram_user_id, chat_id, thread_id, source_sequence, operation_key,
                   operation_kind, operation_token, operation_generation,
                   recovery_claim_token, recovery_claim_generation, prior_claimed_until,
                   safe_until, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                  telegram_user_id, chat_id, thread_id, source_sequence, operation_key
                ) DO UPDATE SET
                  operation_kind = excluded.operation_kind,
                  operation_token = excluded.operation_token,
                  operation_generation = excluded.operation_generation,
                  recovery_claim_token = excluded.recovery_claim_token,
                  recovery_claim_generation = excluded.recovery_claim_generation,
                  prior_claimed_until = excluded.prior_claimed_until,
                  safe_until = excluded.safe_until,
                  expires_at = excluded.expires_at
                """,
                (
                    *identity,
                    normalized_key,
                    normalized_kind,
                    operation_token,
                    operation_generation,
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    prior_claimed_until,
                    safe_until,
                    operation_expires_at,
                ),
            )
            cursor = connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET claimed_until = ?, expires_at = MAX(expires_at, ?)
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                """,
                (
                    safe_until,
                    operation_expires_at,
                    *identity,
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            connection.commit()
            return {
                "telegram_user_id": identity[0],
                "chat_id": identity[1],
                "thread_id": identity[2],
                "source_sequence": identity[3],
                "operation_key": normalized_key,
                "operation_token": operation_token,
                "operation_generation": operation_generation,
                "claim_token": str(claim["claim_token"]),
                "claim_generation": int(claim["claim_generation"]),
                "prior_claimed_until": prior_claimed_until,
                "safe_until": safe_until,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def refresh_presentation_operation(self, operation, *, lease_s) -> bool:
        """Revalidate the exact durable generation after acquiring the process fence."""

        now = time.time()
        identity = (
            str(operation["telegram_user_id"]),
            str(operation["chat_id"]),
            str(operation.get("thread_id") or ""),
            int(operation["source_sequence"]),
        )
        safe_until = now + max(2, min(int(lease_s), 300))
        expires_at = max(now + self.ttl_s, safe_until + 60)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            operation_cursor = connection.execute(
                """
                UPDATE telegram_source_presentation_operations
                SET safe_until = ?, expires_at = MAX(expires_at, ?)
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND operation_key = ?
                  AND operation_token = ? AND operation_generation = ?
                  AND recovery_claim_token = ? AND recovery_claim_generation = ?
                """,
                (
                    safe_until,
                    expires_at,
                    *identity,
                    str(operation["operation_key"]),
                    str(operation["operation_token"]),
                    int(operation["operation_generation"]),
                    str(operation["claim_token"]),
                    int(operation["claim_generation"]),
                ),
            )
            pending_cursor = connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET claimed_until = ?, expires_at = MAX(expires_at, ?)
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                """,
                (
                    safe_until,
                    expires_at,
                    *identity,
                    str(operation["claim_token"]),
                    int(operation["claim_generation"]),
                ),
            )
            if operation_cursor.rowcount != 1 or pending_cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.commit()
            operation["safe_until"] = safe_until
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete_presentation_operation(self, operation) -> bool:
        now = time.time()
        identity = (
            str(operation["telegram_user_id"]),
            str(operation["chat_id"]),
            str(operation.get("thread_id") or ""),
            int(operation["source_sequence"]),
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE telegram_source_presentation_operations
                SET operation_token = '', safe_until = 0
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND operation_key = ?
                  AND operation_token = ? AND operation_generation = ?
                  AND recovery_claim_token = ? AND recovery_claim_generation = ?
                """,
                (
                    *identity,
                    str(operation["operation_key"]),
                    str(operation["operation_token"]),
                    int(operation["operation_generation"]),
                    str(operation["claim_token"]),
                    int(operation["claim_generation"]),
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            restored_until = max(float(operation["prior_claimed_until"]), now + 1)
            cursor = connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET claimed_until = ?
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                """,
                (
                    restored_until,
                    *identity,
                    str(operation["claim_token"]),
                    int(operation["claim_generation"]),
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete_pending_terminal(self, claim) -> bool:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM telegram_source_pending_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ?
                  AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                      AND operation.chat_id = telegram_source_pending_terminals.chat_id
                      AND operation.thread_id = telegram_source_pending_terminals.thread_id
                      AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                      AND operation.operation_token != '' AND operation.safe_until > ?
                  )
                """,
                (
                    str(claim["telegram_user_id"]),
                    str(claim["chat_id"]),
                    str(claim.get("thread_id") or ""),
                    int(claim["source_sequence"]),
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def renew_pending_terminal_claim(self, claim, *, lease_s=30) -> bool:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET claimed_until = MAX(claimed_until, ?)
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                      AND operation.chat_id = telegram_source_pending_terminals.chat_id
                      AND operation.thread_id = telegram_source_pending_terminals.thread_id
                      AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                      AND operation.operation_token != '' AND operation.safe_until > ?
                  )
                """,
                (
                    now + max(1, int(lease_s)),
                    str(claim["telegram_user_id"]),
                    str(claim["chat_id"]),
                    str(claim.get("thread_id") or ""),
                    int(claim["source_sequence"]),
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def reschedule_pending_terminal(self, claim) -> bool:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE telegram_source_pending_terminals
                SET attempts = attempts + 1, next_attempt_at = ?, claimed_until = 0,
                    claim_token = ''
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ?
                  AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                      AND operation.chat_id = telegram_source_pending_terminals.chat_id
                      AND operation.thread_id = telegram_source_pending_terminals.thread_id
                      AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                      AND operation.operation_token != '' AND operation.safe_until > ?
                  )
                """,
                (
                    now + self.retry_delay_s,
                    str(claim["telegram_user_id"]),
                    str(claim["chat_id"]),
                    str(claim.get("thread_id") or ""),
                    int(claim["source_sequence"]),
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def settle_pending_terminal(self, claim, message_id) -> bool:
        now = time.time()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                DELETE FROM telegram_source_pending_terminals
                WHERE telegram_user_id = ? AND chat_id = ? AND thread_id = ?
                  AND source_sequence = ? AND claim_token = ? AND claim_generation = ?
                  AND claimed_until > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM telegram_source_presentation_operations AS operation
                    WHERE operation.telegram_user_id = telegram_source_pending_terminals.telegram_user_id
                      AND operation.chat_id = telegram_source_pending_terminals.chat_id
                      AND operation.thread_id = telegram_source_pending_terminals.thread_id
                      AND operation.source_sequence = telegram_source_pending_terminals.source_sequence
                      AND operation.operation_token != '' AND operation.safe_until > ?
                  )
                """,
                (
                    str(claim["telegram_user_id"]),
                    str(claim["chat_id"]),
                    str(claim.get("thread_id") or ""),
                    int(claim["source_sequence"]),
                    str(claim["claim_token"]),
                    int(claim["claim_generation"]),
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return False
            connection.execute(
                """
                INSERT INTO telegram_source_retry_terminals
                  (telegram_user_id, chat_id, thread_id, source_sequence, message_id, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id, chat_id, thread_id, source_sequence) DO UPDATE SET
                  message_id = excluded.message_id,
                  expires_at = excluded.expires_at
                """,
                (
                    str(claim["telegram_user_id"]),
                    str(claim["chat_id"]),
                    str(claim.get("thread_id") or ""),
                    int(claim["source_sequence"]),
                    str(message_id),
                    now + self.ttl_s,
                ),
            )
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def pending_terminal_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM telegram_source_pending_terminals"
                ).fetchone()[0]
            )


async def _retry_source_order_retractions(bot, store=None, *, limit=25) -> int:
    if store is None:
        configured = os.getenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH")
        candidate = (
            Path(configured)
            if configured
            else default_callback_store_path().with_name("source-order-retractions.sqlite3")
        )
        if not candidate.exists():
            return 0
        store = _TelegramRetractionStore(candidate)
    completed = 0
    for chat_id, message_id in store.due(limit):
        try:
            async with _telegram_existing_message_fence(store.path, chat_id, message_id):
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as exc:
            if "message to delete not found" in str(exc).lower():
                store.mark_deleted(chat_id, message_id)
                completed += 1
            else:
                store.reschedule(chat_id, message_id)
        else:
            store.mark_deleted(chat_id, message_id)
            completed += 1
    return completed


async def _cleanup_obsolete_retry_terminals(
    bot,
    *,
    telegram_user_id,
    chat_id,
    thread_id,
    source_sequence,
    store=None,
) -> int:
    if store is None:
        configured = os.getenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH")
        candidate = (
            Path(configured)
            if configured
            else default_callback_store_path().with_name("source-order-retractions.sqlite3")
        )
        if not candidate.exists():
            return 0
        store = _TelegramRetractionStore(candidate)
    removed = 0
    for terminal_chat_id, message_id, terminal_sequence in store.obsolete_retry_terminals(
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        source_sequence=source_sequence,
    ):
        try:
            async with _telegram_existing_message_fence(
                store.path, terminal_chat_id, message_id
            ):
                await bot.delete_message(chat_id=terminal_chat_id, message_id=message_id)
        except Exception:
            store.enqueue(terminal_chat_id, message_id)
        store.forget_retry_terminal(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            thread_id=thread_id,
            source_sequence=terminal_sequence,
        )
        removed += 1
    return removed


class _StaleTelegramSourceOrder(RuntimeError):
    pass


class _TelegramPresentationOperationTimedOut(TimeoutError):
    pass


def _telegram_presentation_api_timeout_s() -> float:
    try:
        timeout_s = float(
            os.getenv("VIVENTIUM_TELEGRAM_PRESENTATION_API_TIMEOUT_S", "15")
        )
    except (TypeError, ValueError):
        timeout_s = 15.0
    return max(1.0, min(timeout_s, 60.0))


def _telegram_presentation_operation_lease_s() -> int:
    api_timeout_s = _telegram_presentation_api_timeout_s()
    try:
        configured_s = float(
            os.getenv(
                "VIVENTIUM_TELEGRAM_PRESENTATION_OPERATION_LEASE_S",
                str(api_timeout_s + 5),
            )
        )
    except (TypeError, ValueError):
        configured_s = api_timeout_s + 5
    return int(max(api_timeout_s + 1, min(configured_s, 300.0)))


class _TelegramSourceOrderGuard:
    def __init__(self, *, bot, robot, telegram_user_id, chat_id, thread_id, source_sequence):
        self.bot = bot
        self.robot = robot
        self.telegram_user_id = str(telegram_user_id or "")
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.source_sequence = source_sequence
        self.live_refs: list[tuple[Any, Any]] = []
        self._live_ref_set: set[tuple[str, str]] = set()
        self.logical_turn_id = ""
        self.revision = None
        self.source_order_scope = ""
        self.source_event_id = ""
        self.stale = False
        self._non_delivery_acked = False
        self._store = None
        self._recovery_claim = None
        self._recovery_claim_lost = False

    def bind_delivery(self, logical_turn_id, revision) -> None:
        self.logical_turn_id = str(logical_turn_id or "")
        self.revision = revision

    async def is_current(self) -> bool:
        if not _is_newest_telegram_source_message(
            self.chat_id, self.thread_id, self.source_sequence, self.telegram_user_id
        ):
            return False
        if not hasattr(self.robot, "source_order_is_current"):
            return True
        try:
            return bool(
                await self.robot.source_order_is_current(
                    telegram_user_id=self.telegram_user_id,
                    telegram_chat_id=self.chat_id,
                    telegram_message_thread_id=self.thread_id,
                    source_sequence=self.source_sequence,
                )
            )
        except TelegramLinkRequired:
            # An unlinked Telegram identity has no authenticated LibreChat owner scope yet.
            # Keep the local monotonic fence so the linking prompt itself can be shown safely.
            return True
        except Exception as exc:
            logger.error(
                "Core source-order check failed closed before Telegram presentation: %s",
                type(exc).__name__,
            )
            return False

    def _retain(self, chat_id, message_id) -> None:
        if message_id is None:
            return
        normalized = (str(chat_id), str(message_id))
        if normalized in self._live_ref_set:
            return
        self._live_ref_set.add(normalized)
        self.live_refs.append((chat_id, message_id))

    def _retain_result(self, result, kwargs) -> None:
        chat_id = kwargs.get("chat_id", self.chat_id)
        candidates = result if isinstance(result, (list, tuple)) else [result]
        for candidate in candidates:
            self._retain(getattr(candidate, "chat_id", chat_id), getattr(candidate, "message_id", None))
        if str(kwargs.get("message_id") or ""):
            self._retain(chat_id, kwargs.get("message_id"))

    async def _run_recovery_presentation_call(
        self, method_name, *, operation_key, operation_kind, **kwargs
    ):
        if self._recovery_claim is None:
            return await getattr(self.bot, method_name)(**kwargs), True
        if self._store is None:
            self._recovery_claim_lost = True
            return None, False
        operation = self._store.begin_presentation_operation(
            self._recovery_claim,
            operation_key=operation_key,
            operation_kind=operation_kind,
            lease_s=_telegram_presentation_operation_lease_s(),
        )
        if operation is None:
            self._recovery_claim_lost = True
            return None, False

        async def invoke_and_settle():
            if not self._store.refresh_presentation_operation(
                operation, lease_s=_telegram_presentation_operation_lease_s()
            ):
                self._recovery_claim_lost = True
                return None, False
            try:
                async with asyncio.timeout(_telegram_presentation_api_timeout_s()):
                    result = await getattr(self.bot, method_name)(**kwargs)
            except asyncio.TimeoutError as exc:
                self._recovery_claim_lost = True
                raise _TelegramPresentationOperationTimedOut() from exc
            except Exception:
                if not self._store.complete_presentation_operation(operation):
                    self._recovery_claim_lost = True
                raise
            if not self._store.complete_presentation_operation(operation):
                self._recovery_claim_lost = True
                return result, False
            return result, True

        chat_id = kwargs.get("chat_id")
        message_id = kwargs.get("message_id")
        existing_message_call = (
            (method_name.startswith("edit_") or method_name == "delete_message")
            and chat_id is not None
            and message_id is not None
        )
        if existing_message_call:
            async with _telegram_existing_message_fence(
                self._store.path, chat_id, message_id
            ):
                return await invoke_and_settle()
        return await invoke_and_settle()

    async def _compensate_new_message(self, chat_id, message_id) -> bool:
        if self._store is None:
            self._store = _TelegramRetractionStore()
        try:
            async with _telegram_existing_message_fence(
                self._store.path, chat_id, message_id
            ):
                async with asyncio.timeout(_telegram_presentation_api_timeout_s()):
                    await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as exc:
            try:
                if self._store is None:
                    self._store = _TelegramRetractionStore()
                self._store.enqueue(chat_id, message_id)
            except Exception as store_exc:
                logger.error(
                    "Late Telegram send compensation and durable retry failed: %s/%s",
                    type(exc).__name__,
                    type(store_exc).__name__,
                )
                return False
        normalized = (str(chat_id), str(message_id))
        self._live_ref_set.discard(normalized)
        self.live_refs = [
            ref for ref in self.live_refs if (str(ref[0]), str(ref[1])) != normalized
        ]
        return True

    async def call(self, method_name, *args, **kwargs):
        if not await self.is_current():
            await self.mark_stale()
            raise _StaleTelegramSourceOrder("stale Telegram source before presentation")
        chat_id = kwargs.get("chat_id")
        message_id = kwargs.get("message_id")
        existing_message_call = (
            (method_name.startswith("edit_") or method_name == "delete_message")
            and chat_id is not None
            and message_id is not None
        )
        stale_after_wait = False
        if existing_message_call:
            store_path = (
                self._store.path if self._store is not None else _TelegramRetractionStore().path
            )
            async with _telegram_existing_message_fence(store_path, chat_id, message_id):
                if not await self.is_current():
                    stale_after_wait = True
                    result = None
                else:
                    result = await getattr(self.bot, method_name)(*args, **kwargs)
        else:
            result = await getattr(self.bot, method_name)(*args, **kwargs)
        if stale_after_wait:
            await self.mark_stale()
            raise _StaleTelegramSourceOrder("stale Telegram source after presentation wait")
        self._retain_result(result, kwargs)
        if not await self.is_current():
            await self.mark_stale()
            raise _StaleTelegramSourceOrder("stale Telegram source after presentation")
        return result

    async def retract_ref(self, chat_id, message_id) -> bool:
        normalized = (str(chat_id), str(message_id))
        deleted = True
        try:
            if self._recovery_claim is None:
                if self._store is None:
                    self._store = _TelegramRetractionStore()
                async with _telegram_existing_message_fence(
                    self._store.path, chat_id, message_id
                ):
                    await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            else:
                _result, operation_completed = await self._run_recovery_presentation_call(
                    "delete_message",
                    operation_key=f"message:{chat_id}:{message_id}",
                    operation_kind="delete",
                    chat_id=chat_id,
                    message_id=message_id,
                )
                if not operation_completed:
                    return False
        except _TelegramPresentationOperationTimedOut:
            return False
        except Exception as exc:
            deleted = False
            try:
                if self._store is None:
                    self._store = _TelegramRetractionStore()
                self._store.enqueue(chat_id, message_id)
            except Exception as store_exc:
                logger.error(
                    "Stale Telegram deletion and durable retry both failed: %s/%s",
                    type(exc).__name__,
                    type(store_exc).__name__,
                )
                return False
        self._live_ref_set.discard(normalized)
        self.live_refs = [
            ref for ref in self.live_refs if (str(ref[0]), str(ref[1])) != normalized
        ]
        return deleted

    def _renew_recovery_claim(self) -> bool:
        if self._recovery_claim is None:
            return True
        if self._store is None or not self._store.renew_pending_terminal_claim(
            self._recovery_claim
        ):
            self._recovery_claim_lost = True
            return False
        return True

    async def retract_all(self) -> bool:
        success = True
        for chat_id, message_id in list(self.live_refs):
            success = await self.retract_ref(chat_id, message_id) and success
        return success

    async def mark_stale(self) -> bool:
        self.stale = True
        removed = await self.retract_all()
        if (
            not self._non_delivery_acked
            and self.logical_turn_id
            and self.revision is not None
            and hasattr(self.robot, "ack_delivery")
        ):
            self._non_delivery_acked = True
            try:
                await self.robot.ack_delivery(
                    self.logical_turn_id,
                    self.revision,
                    "partial_removed" if removed else "failed",
                    f"telegram:{self.chat_id}",
                )
            except Exception:
                pass
        return removed

    def presentation_refs(self) -> list[str]:
        return [f"telegram:{chat_id}:{message_id}" for chat_id, message_id in self.live_refs]

    async def _replace_live_output_with_retry_terminal(self, pending_claim, text):
        self._recovery_claim = pending_claim
        for chat_id, message_id in list(self.live_refs):
            for method_name, text_key in (
                ("edit_message_text", "text"),
                ("edit_message_caption", "caption"),
            ):
                method = getattr(self.bot, method_name, None)
                if not callable(method):
                    continue
                if not await self.is_current():
                    await self.mark_stale()
                    return False
                try:
                    _result, operation_completed = await self._run_recovery_presentation_call(
                        method_name,
                        operation_key=f"message:{chat_id}:{message_id}",
                        operation_kind="edit",
                        chat_id=chat_id,
                        message_id=message_id,
                        **{text_key: text},
                    )
                    if not operation_completed:
                        return False
                except _TelegramPresentationOperationTimedOut:
                    return False
                except Exception as exc:
                    if "message is not modified" not in str(exc).lower():
                        continue
                if not await self.is_current():
                    await self.mark_stale()
                    return False
                for other_chat_id, other_message_id in self.live_refs:
                    if (str(other_chat_id), str(other_message_id)) == (
                        str(chat_id),
                        str(message_id),
                    ):
                        continue
                    self._store.enqueue(other_chat_id, other_message_id)
                for other_chat_id, other_message_id in list(self.live_refs):
                    if (str(other_chat_id), str(other_message_id)) == (
                        str(chat_id),
                        str(message_id),
                    ):
                        continue
                    if await self.retract_ref(other_chat_id, other_message_id):
                        self._store.mark_deleted(other_chat_id, other_message_id)
                if self._recovery_claim_lost or not self._store.settle_pending_terminal(
                    pending_claim, message_id
                ):
                    return False
                return message_id
        return None

    async def send_retryable_terminal(self, *, persist=True, pending_claim=None) -> Any:
        if pending_claim is not None:
            self._recovery_claim = pending_claim
        if not await self.is_current():
            if pending_claim is not None:
                await self.retract_all()
            return None
        terminal_text = (
            "I could not safely confirm that reply. It was removed. "
            "Please retry your message."
        )
        if pending_claim is not None and self.live_refs:
            replaced_message_id = await self._replace_live_output_with_retry_terminal(
                pending_claim, terminal_text
            )
            if replaced_message_id is not None or self.stale:
                return replaced_message_id or None
            if self._recovery_claim_lost:
                return None
        if pending_claim is None:
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                message_thread_id=self.thread_id,
                text=terminal_text,
            )
            operation_completed = True
        else:
            message, operation_completed = await self._run_recovery_presentation_call(
                "send_message",
                operation_key=f"new:{uuid.uuid4().hex}",
                operation_kind="send",
                chat_id=self.chat_id,
                message_thread_id=self.thread_id,
                text=terminal_text,
            )
            if message is None:
                return None
        message_id = getattr(message, "message_id", None)
        if message_id is None:
            return None
        message_chat_id = getattr(message, "chat_id", self.chat_id)
        self._retain(message_chat_id, message_id)
        if not operation_completed:
            await self._compensate_new_message(message_chat_id, message_id)
            return None
        if not await self.is_current():
            await self.mark_stale()
            return None
        if pending_claim is not None:
            try:
                if self._store is None or not self._store.settle_pending_terminal(
                    pending_claim, message_id
                ):
                    await self._compensate_new_message(message_chat_id, message_id)
                    return None
            except BaseException:
                raise
        elif persist:
            try:
                if self._store is None:
                    self._store = _TelegramRetractionStore()
                self._store.remember_retry_terminal(
                    telegram_user_id=self.telegram_user_id,
                    chat_id=self.chat_id,
                    thread_id=self.thread_id,
                    source_sequence=self.source_sequence,
                    message_id=message_id,
                )
            except Exception as exc:
                logger.error("Could not persist Telegram retry terminal: %s", type(exc).__name__)
        return message_id

    def reserve_pending_retry_terminal(self):
        try:
            if self._store is None:
                self._store = _TelegramRetractionStore()
            return self._store.reserve_pending_terminal(
                telegram_user_id=self.telegram_user_id,
                chat_id=self.chat_id,
                thread_id=self.thread_id,
                source_sequence=self.source_sequence,
                presentation_refs=self.presentation_refs(),
            )
        except Exception as exc:
            logger.error("Could not persist Telegram retry recovery: %s", type(exc).__name__)
            return None

    def retain_presentation_refs(self, presentation_refs) -> None:
        for presentation_ref in presentation_refs or []:
            parts = str(presentation_ref).rsplit(":", 2)
            if len(parts) != 3 or parts[0] != "telegram":
                continue
            message_id = int(parts[2]) if parts[2].lstrip("-").isdigit() else parts[2]
            self._retain(parts[1], message_id)


class _SourceOrderedBotProxy:
    def __init__(self, guard):
        self._source_order_guard = guard
        self._raw_bot = guard.bot

    def __getattr__(self, name):
        attribute = getattr(self._raw_bot, name)
        if not callable(attribute):
            return attribute
        if (name.startswith("send_") and name != "send_chat_action") or name.startswith("edit_"):
            async def _guarded(*args, **kwargs):
                return await self._source_order_guard.call(name, *args, **kwargs)
            return _guarded
        return attribute


class _SourceOrderedContextProxy:
    def __init__(self, context, guard):
        self._context = context
        self.bot = _SourceOrderedBotProxy(guard)

    def __getattr__(self, name):
        return getattr(self._context, name)


async def _retry_pending_source_order_terminals(bot, robot, store=None, *, limit=25) -> int:
    if store is None:
        configured = os.getenv("VIVENTIUM_TELEGRAM_RETRACTION_STORE_PATH")
        candidate = (
            Path(configured)
            if configured
            else default_callback_store_path().with_name("source-order-retractions.sqlite3")
        )
        if not candidate.exists():
            return 0
        store = _TelegramRetractionStore(candidate)
    completed = 0
    for claim in store.claim_pending_terminals(limit=limit):
        telegram_user_id = claim["telegram_user_id"]
        chat_id = claim["chat_id"]
        thread_id = claim["thread_id"]
        source_sequence = claim["source_sequence"]
        identity = {
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": chat_id,
            "telegram_message_thread_id": thread_id,
            "source_sequence": source_sequence,
        }
        try:
            current = bool(await robot.source_order_is_current(**identity))
        except Exception:
            store.reschedule_pending_terminal(claim)
            continue
        guard = _TelegramSourceOrderGuard(
            bot=bot,
            robot=robot,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            thread_id=thread_id or None,
            source_sequence=source_sequence,
        )
        guard._store = store
        guard._recovery_claim = claim
        guard.retain_presentation_refs(claim.get("presentation_refs"))
        if not current:
            await guard.mark_stale()
            if not guard._recovery_claim_lost and store.complete_pending_terminal(claim):
                completed += 1
            continue
        try:
            message_id = await guard.send_retryable_terminal(
                persist=False, pending_claim=claim
            )
        except Exception:
            message_id = None
        if guard.stale:
            store.complete_pending_terminal(claim)
            completed += 1
        elif message_id is not None:
            completed += 1
        else:
            store.reschedule_pending_terminal(claim)
    return completed


async def _observe_ingress_source_guard(
    *, bot, robot, update_message, chat_id, thread_id, source_sequence
):
    telegram_user_id = getattr(getattr(update_message, "from_user", None), "id", "")
    _note_telegram_source_message(
        chat_id, thread_id, source_sequence, telegram_user_id
    )
    guard = _TelegramSourceOrderGuard(
        bot=bot,
        robot=robot,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        source_sequence=source_sequence,
    )
    if robot is None or not hasattr(robot, "observe_source_order"):
        logger.error("Core source-order authority is unavailable at Telegram ingress")
        return None
    try:
        observation = await robot.observe_source_order(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=chat_id,
            telegram_message_thread_id=thread_id,
            source_sequence=source_sequence,
        )
    except TelegramLinkRequired:
        return guard
    except Exception as exc:
        logger.error(
            "Core source-order observation failed before Telegram output: %s",
            type(exc).__name__,
        )
        return None
    if observation.get("stale"):
        guard.stale = True
        return None
    source_order_scope = str(observation.get("source_order_scope") or "")
    source_event_id = str(observation.get("source_event_id") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", source_order_scope) or not re.fullmatch(
        r"[a-f0-9]{64}", source_event_id
    ):
        logger.error("Core source-order observation omitted its trusted receipt")
        return None
    guard.source_order_scope = source_order_scope
    guard.source_event_id = source_event_id
    return guard


async def _observe_telegram_update_ingress(update, context):
    update_message = _telegram_update_message(update)
    chat_id = (
        getattr(update_message, "chat_id", "")
        or getattr(getattr(update_message, "chat", None), "id", "")
        or getattr(getattr(update, "effective_chat", None), "id", "")
    )
    source_sequence = getattr(update_message, "message_id", None)
    thread_id = getattr(update_message, "message_thread_id", None)
    try:
        source_sequence = int(source_sequence)
    except (TypeError, ValueError):
        source_sequence = 0
    if not chat_id or source_sequence <= 0:
        logger.error("Telegram ingress omitted a valid chat or positive message sequence")
        return None
    try:
        robot, _, _api_key, _api_url = get_robot(str(chat_id))
    except Exception as exc:
        logger.error("Telegram ingress could not resolve Core bridge: %s", type(exc).__name__)
        return None
    return await _observe_ingress_source_guard(
        bot=context.bot,
        robot=robot,
        update_message=update_message,
        chat_id=chat_id,
        thread_id=thread_id,
        source_sequence=source_sequence,
    )


async def _with_source_ordered_context_bot(context, guard, operation):
    guarded_context = _SourceOrderedContextProxy(context, guard)
    return await operation(guarded_context)
# === VIVENTIUM END ===


def _telegram_reply_context_v1(
    update_message,
    bot_user_id: Any = None,
    quoted_attachment_text: Any = None,
    current_sender_id: Any = None,
) -> Optional[dict[str, Any]]:
    """Build untrusted reply evidence; Core resolves ownership from durable receipts."""

    replied = getattr(update_message, "reply_to_message", None)
    replied_message_id = getattr(replied, "message_id", None)
    if replied is None or replied_message_id is None:
        return None
    sender = getattr(replied, "from_user", None)
    attachments = []
    for kind in ("document", "audio", "video", "voice", "animation", "sticker"):
        candidate = getattr(replied, kind, None)
        if candidate is None:
            continue
        attachment = {
            "kind": kind,
            "fileId": str(getattr(candidate, "file_id", "") or ""),
        }
        filename = str(getattr(candidate, "file_name", "") or "")
        if filename:
            attachment["filename"] = filename
        if kind == "document" and quoted_attachment_text:
            attachment["extractedText"] = str(quoted_attachment_text)[:32768]
        attachments.append(attachment)
    photos = getattr(replied, "photo", None) or []
    if photos:
        attachments.append(
            {
                "kind": "photo",
                "fileId": str(getattr(photos[-1], "file_id", "") or ""),
            }
        )
    timestamp = getattr(replied, "date", None)
    sender_id = str(getattr(sender, "id", "") or "").strip()
    current_bot_id = str(bot_user_id or "").strip()
    owner_sender_id = str(current_sender_id or "").strip()
    has_sender_chat = getattr(replied, "sender_chat", None) is not None
    is_current_bot = bool(not has_sender_chat and current_bot_id and sender_id == current_bot_id)
    is_current_sender = bool(not has_sender_chat and owner_sender_id and sender_id == owner_sender_id)
    is_known_foreign = bool(
        not has_sender_chat
        and current_bot_id
        and owner_sender_id
        and sender_id
        and sender_id not in {current_bot_id, owner_sender_id}
    )
    return {
        "version": 1,
        "repliedTelegramMessageId": str(replied_message_id),
        "quoteText": str(getattr(replied, "text", None) or getattr(replied, "caption", None) or ""),
        "senderKind": (
            "assistant_candidate"
            if is_current_bot
            else "owner_candidate"
            if is_current_sender
            else "external_candidate"
            if is_known_foreign
            else "unknown"
        ),
        **({"timestamp": timestamp.isoformat()} if timestamp is not None else {}),
        **({"attachments": attachments} if attachments else {}),
    }


def _info_call_refresh_key(chatid, message_id):
    if chatid is None or message_id is None:
        return None
    return (str(chatid), int(message_id))


def _mark_info_call_refresh(chatid, message_id):
    key = _info_call_refresh_key(chatid, message_id)
    if key is not None:
        _PENDING_INFO_CALL_REFRESHES.add(key)


def _cancel_info_call_refresh_for_query(callback_query):
    message = getattr(callback_query, "message", None)
    chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    key = _info_call_refresh_key(chat_id, message_id)
    if key is not None:
        _PENDING_INFO_CALL_REFRESHES.discard(key)


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


# === VIVENTIUM START ===
# Feature: Non-secret voice markup debug logging for Telegram parity QA.
def _voice_debug_enabled() -> bool:
    return (
        os.getenv("VIVENTIUM_VOICE_DEBUG_TTS") == "1"
        or os.getenv("VIVENTIUM_TELEGRAM_DEBUG_TTS") == "1"
    )


def _voice_debug_text(text: str, limit: int = 1200) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Same-token process singleton for Telegram polling.
_TELEGRAM_SINGLETON_LOCK = None


def _acquire_telegram_singleton_or_exit() -> None:
    global _TELEGRAM_SINGLETON_LOCK
    lock_enabled = coerce_bool(os.getenv("VIVENTIUM_TELEGRAM_SINGLETON_LOCK"), True)
    if not lock_enabled:
        logger.warning("Telegram singleton lock disabled by environment")
        return
    try:
        _TELEGRAM_SINGLETON_LOCK = acquire_telegram_singleton_lock(BOT_TOKEN)
    except SingletonAlreadyRunning as exc:
        owner = f" pid={exc.owner_pid}" if exc.owner_pid else ""
        logger.error(
            "Another Telegram bot process already owns this BotFather-token lock%s; "
            "exiting to prevent getUpdates conflicts and delayed voice replies.",
            owner,
        )
        raise SystemExit(78) from exc
# === VIVENTIUM END ===


async def _resolve_voice_input_message(
    context,
    *,
    chatid,
    messageid,
    message_thread_id,
    message,
    voice_text,
    voice_error_text,
    show_transcription: bool = True,
):
    if voice_error_text:
        # Keep transcription failures plain text so Telegram does not need
        # Markdown escaping for runtime-generated error details.
        await context.bot.send_message(
            chat_id=chatid,
            message_thread_id=message_thread_id,
            text=voice_error_text,
            reply_to_message_id=messageid,
        )
        return None, True

    if message is None and voice_text and show_transcription:
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

    if message is None:
        return voice_text, False
    return message, False

from telegram.constants import ChatAction
from telegram import BotCommand, ForceReply, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, ApplicationBuilder, filters, CallbackQueryHandler, Application, AIORateLimiter, ContextTypes
from datetime import timedelta

lock = asyncio.Lock()
event = asyncio.Event()
stop_event = asyncio.Event()
# Use configurable timeout from config.py (default: 30 seconds for small deployments)
from config import TIMEOUT as time_out, POLLING_TIMEOUT

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# === VIVENTIUM START ===
# Feature: Account-wide Parallel Work Telegram surface.
# Purpose: Core owns account/link/preference/work truth. Telegram stores only short-lived,
# user/chat-scoped opaque capabilities so workRef never enters callback_data.
PARALLEL_WORK_PROMPT_PREFIX = "Parallel work instruction"
_PARALLEL_WORK_CLIENT = None
_PARALLEL_WORK_CALLBACK_STORE = None
_PARALLEL_WORK_ACTION_LABELS = {
    "queue": "Queue",
    "message": "Message",
    "steer": "Steer",
    "pause": "Pause",
    "resume": "Resume",
    "stop": "Stop / Cancel",
    "retry": "Retry",
    "dismiss": "Dismiss",
}


def _get_parallel_work_client():
    global _PARALLEL_WORK_CLIENT
    if _PARALLEL_WORK_CLIENT is None:
        base_url = (os.getenv("VIVENTIUM_LIBRECHAT_ORIGIN") or "http://127.0.0.1:3180").strip()
        secret = (
            os.getenv("VIVENTIUM_TELEGRAM_SECRET")
            or os.getenv("VIVENTIUM_CALL_SESSION_SECRET")
            or ""
        ).strip()
        _PARALLEL_WORK_CLIENT = OrchestrationClient(base_url, secret)
    return _PARALLEL_WORK_CLIENT


def _get_parallel_work_callback_store():
    global _PARALLEL_WORK_CALLBACK_STORE
    if _PARALLEL_WORK_CALLBACK_STORE is None:
        try:
            ttl_s = int(os.getenv("VIVENTIUM_TELEGRAM_WORK_CALLBACK_TTL_S") or "900")
        except ValueError:
            ttl_s = 900
        _PARALLEL_WORK_CALLBACK_STORE = CallbackCapabilityStore(
            default_callback_store_path(),
            ttl_s=max(60, min(ttl_s, 3600)),
        )
    return _PARALLEL_WORK_CALLBACK_STORE


def _main_menu_buttons(
    convo_id,
    *,
    call_url=None,
    fetch_call_url=True,
    parallel_available=False,
):
    button_kwargs = {"fetch_call_url": fetch_call_url}
    if call_url is not None:
        button_kwargs["call_url"] = call_url
    rows = [
        list(row)
        for row in update_first_buttons_message(convo_id, **button_kwargs)
    ]
    if parallel_available:
        rows.append([InlineKeyboardButton("Active work", callback_data="PW:L")])
    return rows


def _preferences_menu_buttons(convo_id, *, parallel_available=False):
    rows = [list(row) for row in update_menu_buttons(PREFERENCES, "_PREFERENCES", convo_id)]
    back_row = rows.pop() if rows else [InlineKeyboardButton("⬅️ Back", callback_data="BACK")]
    if parallel_available:
        rows.append([InlineKeyboardButton("Parallel work", callback_data="PW:S")])
    rows.append(back_row)
    return rows


async def _parallel_work_available(telegram_user_id):
    """Best-effort feature discovery; unavailable controls stay hidden without breaking menus."""

    try:
        snapshot = await _get_parallel_work_client().get_preference(str(telegram_user_id or ""))
    except (OrchestrationError, ValueError):
        return False
    return snapshot.parallel_work_available or snapshot.has_known_work


def _parallel_work_settings_view(snapshot):
    rows = []
    if snapshot.parallel_work_available:
        desired = "0" if snapshot.parallel_work_enabled else "1"
        label = "Turn off" if snapshot.parallel_work_enabled else "Turn on"
        rows.append([InlineKeyboardButton(label, callback_data=f"PW:T:{desired}")])
    if snapshot.parallel_work_available or snapshot.has_known_work:
        rows.append([InlineKeyboardButton("Active work", callback_data="PW:L")])
    rows.append([InlineKeyboardButton("⬅️ Preferences", callback_data="PREFERENCES")])
    return format_parallel_work_settings(snapshot), InlineKeyboardMarkup(rows)


def _active_work_view(snapshot, *, telegram_user_id, chat_id):
    rows = []
    if snapshot.active_state == "fresh":
        store = _get_parallel_work_callback_store()
        for index, item in enumerate(snapshot.items, start=1):
            issued = store.issue_actions(
                telegram_user_id=str(telegram_user_id),
                chat_id=str(chat_id),
                targets=[(item.work_ref, action) for action in item.actions],
            )
            buttons = [
                InlineKeyboardButton(
                    f"{index} · {_PARALLEL_WORK_ACTION_LABELS[target.action]}",
                    callback_data=action_callback_data(target.token),
                )
                for target in issued
            ]
            for start in range(0, len(buttons), 2):
                rows.append(buttons[start:start + 2])
        if snapshot.has_more and snapshot.next_cursor:
            page_token = store.issue_page(
                telegram_user_id=str(telegram_user_id),
                chat_id=str(chat_id),
                cursor=snapshot.next_cursor,
            )
            rows.append(
                [InlineKeyboardButton("Load more", callback_data=page_callback_data(page_token))]
            )
    if snapshot.parallel_work_available:
        rows.extend(
            [
                [InlineKeyboardButton("Refresh", callback_data="PW:L")],
                [
                    InlineKeyboardButton("Parallel work settings", callback_data="PW:S"),
                    InlineKeyboardButton("⬅️ Back", callback_data="BACK"),
                ],
            ]
        )
    else:
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="BACK")])
    text = format_active_work(snapshot)
    if snapshot.action_receipt and snapshot.action_receipt.message:
        text = f"{snapshot.action_receipt.message}\n\n{text}"
    return text, InlineKeyboardMarkup(rows)


def _parallel_work_link_view(error):
    rows = []
    link_url = safe_link_url(getattr(error, "link_url", ""))
    if link_url:
        rows.append([InlineKeyboardButton("Link Viventium account", url=link_url)])
    rows.extend(
        [
            [InlineKeyboardButton("Refresh", callback_data="PW:S")],
            [InlineKeyboardButton("⬅️ Preferences", callback_data="PREFERENCES")],
        ]
    )
    return str(error), InlineKeyboardMarkup(rows)


def _parallel_work_unavailable_view(message=None):
    text = str(message or "").strip() or (
        "Parallel work is unavailable right now. Existing work may still be running."
    )
    return text, InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Refresh Active work", callback_data="PW:L")],
            [InlineKeyboardButton("⬅️ Back", callback_data="BACK")],
        ]
    )


def _parallel_work_action_retry_view(error, callback_data):
    indeterminate = bool(getattr(error, "indeterminate", False))
    explanation = (
        "Viventium may already have accepted this action. Retry safely checks the same operation; it will not create another."
        if indeterminate
        else "Retry uses the same operation, so it cannot duplicate the action."
    )
    return (
        f"{str(error)}\n\n{explanation}",
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Retry same action", callback_data=callback_data)],
                [InlineKeyboardButton("Refresh Active work", callback_data="PW:L")],
                [InlineKeyboardButton("⬅️ Back", callback_data="BACK")],
            ]
        ),
    )


def _parallel_work_page_retry_view(error, callback_data):
    return (
        f"{str(error)}\n\nRetry continues from the same saved page; it does not restart or duplicate any work.",
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Retry Load more", callback_data=callback_data)],
                [InlineKeyboardButton("Refresh Active work", callback_data="PW:L")],
                [InlineKeyboardButton("⬅️ Back", callback_data="BACK")],
            ]
        ),
    )


def _parallel_work_expired_view():
    return (
        "This work control expired or belongs to another Telegram user. Refresh Active work for current controls.",
        InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Refresh Active work", callback_data="PW:L")],
                [InlineKeyboardButton("⬅️ Back", callback_data="BACK")],
            ]
        ),
    )


def _parallel_work_confirmation_view(target, *, telegram_user_id, chat_id):
    confirmation = _get_parallel_work_callback_store().issue_actions(
        telegram_user_id=str(telegram_user_id),
        chat_id=str(chat_id),
        targets=[(target.work_ref, target.action)],
    )[0]
    action_label = "Stop / cancel"
    return (
        f"{action_label} this work? It may interrupt in-flight execution.",
        InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Stop / cancel work",
                        callback_data=confirmation_callback_data(confirmation.token, True),
                    ),
                    InlineKeyboardButton(
                        "Keep running",
                        callback_data=confirmation_callback_data(confirmation.token, False),
                    ),
                ],
                [InlineKeyboardButton("⬅️ Active work", callback_data="PW:L")],
            ]
        ),
    )


async def _edit_parallel_work_view(callback_query, context, *, text, reply_markup, update):
    import telegram
    try:
        if callback_query.message:
            return await callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
    except telegram.error.BadRequest as error:
        if "Message is not modified" in str(error):
            return None
        if "Message to edit not found" not in str(error) and "message can't be edited" not in str(error):
            logger.warning("Failed to edit Parallel Work view: %s", error)
            return None
    except Exception as error:
        logger.warning("Failed to edit Parallel Work view: %s", error)
        return None
    return await context.bot.send_message(
        chat_id=getattr(getattr(update, "effective_chat", None), "id", None),
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


def _parallel_work_prompt_token(message):
    replied = getattr(message, "reply_to_message", None)
    prompt_text = str(getattr(replied, "text", "") or "")
    match = re.match(
        rf"^{re.escape(PARALLEL_WORK_PROMPT_PREFIX)} · ([A-Za-z0-9_-]{{10,48}})(?:\n|$)",
        prompt_text,
    )
    return match.group(1) if match else ""


async def _execute_parallel_work_action(
    *,
    client,
    store,
    telegram_user_id,
    reservation: ActionReservation,
    instruction=None,
):
    """Execute one durable action and preserve its receipt across uncertain transports."""

    try:
        snapshot = await client.act(
            telegram_user_id,
            reservation.target.work_ref,
            reservation.target.action,
            instruction=instruction,
            operation_id=reservation.operation_id,
        )
    except OrchestrationError as error:
        store.complete_action(
            reservation,
            succeeded=False,
            definitive=not bool(getattr(error, "indeterminate", False)),
            receipt=str(error),
        )
        raise
    except Exception:
        # The request may have crossed the process boundary before an unexpected local failure.
        # Preserve the same operation id for reconciliation instead of allowing a new action.
        store.complete_action(reservation, succeeded=False, definitive=False)
        raise
    receipt = getattr(getattr(snapshot, "action_receipt", None), "message", "")
    store.complete_action(
        reservation,
        succeeded=True,
        receipt=str(receipt or "accepted"),
    )
    return snapshot


class _ParallelWorkInstructionReplyFilter(filters.MessageFilter):
    def filter(self, message):
        return bool(_parallel_work_prompt_token(message))


async def parallel_work_instruction_reply(update, context):
    message = getattr(update, "effective_message", None)
    user_id = str(getattr(getattr(update, "effective_user", None), "id", "") or "")
    chat_id = str(getattr(getattr(update, "effective_chat", None), "id", "") or "")
    token = _parallel_work_prompt_token(message)
    instruction = str(getattr(message, "text", "") or "").strip()
    store = _get_parallel_work_callback_store()
    reserved = (
        store.reserve_prompt_action(
            token,
            telegram_user_id=user_id,
            chat_id=chat_id,
            instruction=instruction,
        )
        if token and instruction
        else None
    )
    if not instruction:
        text, markup = (
            "Message and Steer require an instruction. Open Active work and try again.",
            InlineKeyboardMarkup([[InlineKeyboardButton("Active work", callback_data="PW:L")]]),
        )
    elif reserved is None:
        text, markup = _parallel_work_expired_view()
    else:
        reservation, durable_instruction = reserved
        try:
            snapshot = await _execute_parallel_work_action(
                client=_get_parallel_work_client(),
                store=store,
                telegram_user_id=user_id,
                reservation=reservation,
                instruction=durable_instruction,
            )
            text, markup = _active_work_view(
                snapshot,
                telegram_user_id=user_id,
                chat_id=chat_id,
            )
        except OrchestrationLinkRequired as error:
            text, markup = _parallel_work_link_view(error)
        except OrchestrationError as error:
            if bool(getattr(error, "indeterminate", False)):
                text, markup = _parallel_work_action_retry_view(
                    error,
                    prompt_retry_callback_data(reservation.target.token),
                )
            else:
                text, markup = _parallel_work_unavailable_view(str(error))
    await context.bot.send_message(
        chat_id=chat_id,
        message_thread_id=getattr(message, "message_thread_id", None),
        text=text,
        reply_markup=markup,
        disable_web_page_preview=True,
    )
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Telegram Bot API token redaction in local logs.
class _TelegramTokenRedactionFilter(logging.Filter):
    _token_pattern = re.compile(r"(bot)[0-9]{6,}:[A-Za-z0-9_-]{20,}")

    def filter(self, record: logging.LogRecord) -> bool:
        def _redact(value):
            if isinstance(value, str):
                return self._token_pattern.sub(r"\1[REDACTED]", value)
            return value

        record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _redact(value) for key, value in record.args.items()}
        return True

_telegram_token_redaction_filter = _TelegramTokenRedactionFilter()
logger.addFilter(_telegram_token_redaction_filter)
for _handler in logger.handlers:
    _handler.addFilter(_telegram_token_redaction_filter)
# === VIVENTIUM END ===

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
    message_thread_id: Optional[int] = None,
    text: str,
    parse_mode: Optional[str] = None,
    voice_audio: Optional[bytes] = None,
    before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
) -> list[str]:
    rendered = ""
    effective_parse_mode: Optional[str] = None
    message_ids: list[str] = []
    thread_kwargs = (
        {"message_thread_id": message_thread_id}
        if isinstance(message_thread_id, int) and message_thread_id > 0
        else {}
    )

    def _remember_message_id(value: Any) -> None:
        message_id = getattr(value, "message_id", None)
        if message_id is not None and str(message_id).strip():
            message_ids.append(str(message_id).strip())

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
            if before_side_effect is not None:
                await before_side_effect()
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=rendered,
                parse_mode=effective_parse_mode,
                **thread_kwargs,
            )
            _remember_message_id(sent_message)
        except Exception as exc:
            if effective_parse_mode and "parse entities" in str(exc):
                if before_side_effect is not None:
                    await before_side_effect()
                sent_message = await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        strip_html_tags(rendered)
                        if effective_parse_mode == "HTML"
                        else _strip_telegram_markdown(sanitize_telegram_text(text))
                    ),
                    **thread_kwargs,
                )
                _remember_message_id(sent_message)
            else:
                raise

    if voice_audio:
        try:
            audio_stream = BytesIO(voice_audio)
            audio_stream.name = "Voice"
            audio_stream.seek(0)
            if before_side_effect is not None:
                await before_side_effect()
            sent_audio = await bot.send_audio(
                chat_id=chat_id,
                audio=audio_stream,
                title="Voice",
                **thread_kwargs,
            )
            _remember_message_id(sent_audio)
        except Exception as exc:
            logger.warning(
                "Failed to deliver proactive voice message to %s after text send: %s",
                chat_id,
                exc,
            )
    return list(dict.fromkeys(message_ids))
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


# === VIVENTIUM START ===
# Feature: Telegram attachment ingress parity.
# Purpose: Keep media groups and broad file messages on one shared path before
# forwarding to LibreChat's message-file contract.
_MEDIA_GROUP_BUFFERS: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
_MEDIA_GROUP_TASKS: dict[tuple[str, str, str, str], asyncio.Task] = {}
_MEDIA_GROUP_LOCK = asyncio.Lock()


def _unpack_message_info(message_info):
    values = tuple(message_info or ())
    if len(values) == 14:
        return (*values, [])
    if len(values) == 15:
        return values
    raise ValueError(f"Unexpected Telegram message info shape: {len(values)}")


def _telegram_update_message(update):
    return (
        getattr(update, "effective_message", None)
        or getattr(update, "message", None)
        or getattr(update, "edited_message", None)
        or getattr(update, "channel_post", None)
        or getattr(update, "edited_channel_post", None)
    )


def _captioned_transcription_update(update) -> bool:
    update_message = _telegram_update_message(update)
    return bool(
        update_message
        and getattr(update_message, "caption", None)
        and (
            getattr(update_message, "voice", None)
            or getattr(update_message, "video_note", None)
        )
    )


def _local_telegram_source_guard(update, context):
    update_message = _telegram_update_message(update)
    chat_id = (
        getattr(update_message, "chat_id", "")
        or getattr(getattr(update_message, "chat", None), "id", "")
        or getattr(getattr(update, "effective_chat", None), "id", "")
    )
    thread_id = getattr(update_message, "message_thread_id", None)
    source_sequence = getattr(update_message, "message_id", None)
    telegram_user_id = getattr(getattr(update_message, "from_user", None), "id", "")
    try:
        source_sequence = int(source_sequence)
    except (TypeError, ValueError):
        source_sequence = 0
    if not chat_id or source_sequence <= 0:
        return None
    _note_telegram_source_message(
        chat_id, thread_id, source_sequence, telegram_user_id
    )
    return _TelegramSourceOrderGuard(
        bot=context.bot,
        robot=None,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        source_sequence=source_sequence,
    )


async def _preflight_captioned_transcription_failure(update, context):
    if not _captioned_transcription_update(update):
        return None, False
    local_guard = _local_telegram_source_guard(update, context)
    message_info = _unpack_message_info(await GetMesageInfo(update, context))
    voice_error_text = message_info[12]
    if not voice_error_text:
        return message_info, False

    async def send_error(send_context):
        return await _resolve_voice_input_message(
            send_context,
            chatid=message_info[3],
            messageid=message_info[4],
            message_thread_id=message_info[7],
            message=message_info[0],
            voice_text=message_info[11],
            voice_error_text=voice_error_text,
            show_transcription=False,
        )

    if local_guard is None:
        await send_error(context)
    else:
        await _with_source_ordered_context_bot(context, local_guard, send_error)
    return message_info, True


def _telegram_media_group_key(update_message):
    media_group_id = getattr(update_message, "media_group_id", None)
    if not media_group_id:
        return None
    chat_id = str(getattr(update_message, "chat_id", "") or getattr(getattr(update_message, "chat", None), "id", "") or "")
    if not chat_id:
        return None
    thread_id = str(getattr(update_message, "message_thread_id", "") or "")
    user_id = str(getattr(getattr(update_message, "from_user", None), "id", "") or "")
    return (chat_id, thread_id, user_id, str(media_group_id))


def _media_group_wait_s() -> float:
    wait_s = getattr(config, "VIVENTIUM_TELEGRAM_MEDIA_GROUP_WAIT_S", 0.65) or 0.65
    try:
        wait_s = float(wait_s)
    except Exception:
        wait_s = 0.65
    return max(0.1, min(wait_s, 3.0))


def _attachment_error_reason(error_code: str) -> str:
    if error_code == "file_too_large":
        return "is too large for the current Telegram bridge limit"
    if error_code == "download_timeout":
        return "timed out while downloading from Telegram"
    if error_code == "missing_file_path":
        return "could not be resolved by Telegram"
    if error_code == "empty_file":
        return "downloaded as an empty file"
    return "could not be downloaded from Telegram"


def _telegram_attachment_error_text(file_errors) -> str:
    errors = [error for error in (file_errors or []) if isinstance(error, dict)]
    if not errors:
        return "I couldn't process that Telegram attachment. Please retry."
    first = errors[0]
    filename = str(first.get("filename") or first.get("media_kind") or "attachment")
    reason = _attachment_error_reason(str(first.get("error_code") or "download_failed"))
    if len(errors) == 1:
        return f"I couldn't process {filename}: it {reason}. Please retry or send a smaller/supported file."
    return (
        f"I couldn't process {len(errors)} Telegram attachments. The first one, {filename}, "
        f"{reason}. Please retry or send smaller/supported files."
    )


async def _send_telegram_attachment_error(context, chatid, message_thread_id, messageid, file_errors) -> None:
    await context.bot.send_message(
        chat_id=chatid,
        message_thread_id=message_thread_id,
        text=_telegram_attachment_error_text(file_errors),
        reply_to_message_id=messageid,
    )


def _telegram_attachment_filter():
    return (filters.PHOTO | filters.Document.ALL | filters.AUDIO | filters.VIDEO) & ~filters.COMMAND


def _telegram_captioned_attachment_filter():
    return filters.CAPTION & _telegram_attachment_filter()


def _telegram_uncaptioned_attachment_filter():
    return ~filters.CAPTION & _telegram_attachment_filter()


async def _process_media_group_entries(key, entries):
    ordered = sorted(
        entries,
        key=lambda entry: getattr(_telegram_update_message(entry["update"]), "message_id", 0) or 0,
    )
    parsed = []
    for entry in ordered:
        parsed.append((entry, _unpack_message_info(await GetMesageInfo(entry["update"], entry["context"]))))

    primary = None
    for entry, info in parsed:
        message = info[0]
        rawtext = info[1]
        if message or rawtext:
            primary = (entry, info)
            break
    if primary is None and parsed:
        primary = parsed[0]
    if primary is None:
        return

    primary_entry, primary_info = primary
    (
        message,
        rawtext,
        _image_url,
        chatid,
        messageid,
        _reply_to_message_text,
        update_message,
        message_thread_id,
        convo_id,
        _file_url,
        reply_to_message_file_content,
        voice_text,
        voice_error_text,
        _file_data_list,
        _file_error_list,
    ) = primary_info

    all_files = []
    all_errors = []
    for _entry, info in parsed:
        all_files.extend(info[13] or [])
        all_errors.extend(info[14] or [])
    source_sequence = max(
        (int(info[4]) for _entry, info in parsed if str(info[4] or "").isdigit()),
        default=int(messageid),
    )
    robot, _, _api_key, _api_url = get_robot(convo_id)
    ingress_guard = max(
        (entry.get("ingress_guard") for entry, _info in parsed if entry.get("ingress_guard")),
        key=lambda guard: int(guard.source_sequence),
        default=None,
    )
    if ingress_guard is None:
        return
    ingress_guard.robot = robot

    logger.info(
        "[VIVENTIUM] Coalesced Telegram media group: key=%s messages=%d files=%d errors=%d",
        ":".join(key),
        len(parsed),
        len(all_files),
        len(all_errors),
    )

    if voice_error_text:
        await _with_source_ordered_context_bot(
            primary_entry["context"],
            ingress_guard,
            lambda guarded_context: _resolve_voice_input_message(
                guarded_context,
                chatid=chatid,
                messageid=messageid,
                message_thread_id=message_thread_id,
                message=message,
                voice_text=voice_text,
                voice_error_text=voice_error_text,
                show_transcription=False,
            ),
        )
        return

    if all_errors:
        await _with_source_ordered_context_bot(
            primary_entry["context"],
            ingress_guard,
            lambda guarded_context: _send_telegram_attachment_error(
                guarded_context,
                chatid,
                message_thread_id,
                messageid,
                all_errors,
            ),
        )
        return

    text = message or rawtext or voice_text or ""
    if update_message and update_message.chat.type in ['group', 'supergroup'] and text:
        sender_name = update_message.from_user.first_name
        text = f"{sender_name}: {text}"

    trace_id = f"tg-{chatid}-{messageid}-{uuid.uuid4().hex[:6]}"
    await getViventiumResponse(
        update_message,
        primary_entry["context"],
        primary_entry.get("title", ""),
        robot,
        text,
        chatid,
        messageid,
        convo_id,
        message_thread_id,
        voice_note_detected=False,
        files=all_files,
        trace_id=trace_id,
        telegram_message_id=source_sequence,
        telegram_update_id=getattr(primary_entry["update"], "update_id", None),
        reply_context=_telegram_reply_context_v1(
            update_message,
            getattr(getattr(primary_entry["context"], "bot", None), "id", None),
            reply_to_message_file_content,
            getattr(getattr(update_message, "from_user", None), "id", None),
        ),
        _source_guard=ingress_guard,
    )


async def _flush_media_group_after_delay(key):
    try:
        await asyncio.sleep(_media_group_wait_s())
        async with _MEDIA_GROUP_LOCK:
            entries = _MEDIA_GROUP_BUFFERS.pop(key, [])
            _MEDIA_GROUP_TASKS.pop(key, None)
        if entries:
            await _process_media_group_entries(key, entries)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Failed to process Telegram media group")


async def _queue_media_group_update(
    update,
    context,
    *,
    title="",
    has_command=False,
    source="message",
    ingress_guard=None,
) -> bool:
    update_message = _telegram_update_message(update)
    key = _telegram_media_group_key(update_message) if update_message is not None else None
    if key is None:
        return False
    async with _MEDIA_GROUP_LOCK:
        _MEDIA_GROUP_BUFFERS.setdefault(key, []).append({
            "update": update,
            "context": context,
            "title": title,
            "has_command": has_command,
            "source": source,
            "ingress_guard": ingress_guard,
        })
        existing_task = _MEDIA_GROUP_TASKS.get(key)
        if existing_task and not existing_task.done():
            existing_task.cancel()
        _MEDIA_GROUP_TASKS[key] = asyncio.create_task(_flush_media_group_after_delay(key))
    return True
# === VIVENTIUM END ===

@decorators.GroupAuthorization
@decorators.Authorization
@decorators.APICheck
async def command_bot(update, context, title="", has_command=True):
    stop_event.clear()
    preparsed_message_info, transcription_failed = (
        await _preflight_captioned_transcription_failure(update, context)
    )
    if transcription_failed:
        return
    ingress_guard = await _observe_telegram_update_ingress(update, context)
    if ingress_guard is None:
        return
    if await _queue_media_group_update(
        update,
        context,
        title=title,
        has_command=has_command,
        source="command",
        ingress_guard=ingress_guard,
    ):
        return
    # === VIVENTIUM START ===
    # Feature: Timing hooks for Telegram request lifecycle.
    request_start_ts = time.monotonic()
    # === VIVENTIUM END ===
    # === VIVENTIUM START ===
    # Updated to capture file_data_list for LibreChat agent file upload
    message_info = preparsed_message_info or _unpack_message_info(
        await GetMesageInfo(update, context)
    )
    message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list, file_error_list = message_info
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
            f"voice_note={int(bool(update_message and (update_message.voice or update_message.video_note)))} "
            f"files={len(file_data_list) if file_data_list else 0}"
        ),
    )
    # === VIVENTIUM END ===
    # === VIVENTIUM END ===
    voice_note_detected = bool(update_message and (update_message.voice or update_message.video_note))
    robot, _, api_key, api_url = get_robot(convo_id)
    ingress_guard.robot = robot

    if file_error_list:
        await _with_source_ordered_context_bot(
            context,
            ingress_guard,
            lambda guarded_context: _send_telegram_attachment_error(
                guarded_context,
                chatid,
                message_thread_id,
                messageid,
                file_error_list,
            ),
        )
        return

    if has_command == False or len(context.args) > 0:
        if has_command:
            message = ' '.join(context.args)
        # REMOVED: pass_history - Not used by LiveKit Bridge, Viventium handles conversation history
        message, voice_input_failed = await _with_source_ordered_context_bot(
            context,
            ingress_guard,
            lambda guarded_context: _resolve_voice_input_message(
                guarded_context,
                chatid=chatid,
                messageid=messageid,
                message_thread_id=message_thread_id,
                message=message,
                voice_text=voice_text,
                voice_error_text=voice_error_text,
            ),
        )
        if voice_input_failed:
            return
            
        if message and len(message) == 1 and is_emoji(message):
            return

        message_has_nick = False
        botNick = config.NICK.lower() if config.NICK else None
        if rawtext and rawtext.split()[0].lower() == botNick:
            message_has_nick = True

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

            # === VIVENTIUM START ===
            # Feature: Durable Telegram reply provenance.
            # Purpose: Never flatten quoted text/files into the user's message or discard replies
            # to an unrecognized bot. Core resolves ownership from owner/chat-scoped receipts.
            reply_context = _telegram_reply_context_v1(
                update_message,
                getattr(getattr(context, "bot", None), "id", None),
                reply_to_message_file_content,
                getattr(getattr(update_message, "from_user", None), "id", None),
            )
            # === VIVENTIUM END ===

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
                reply_context=reply_context,
                _source_guard=ingress_guard,
            )
            _tg_timing_log(trace_id, "request_complete", request_start_ts)
            _tg_deep_log(trace_id, "request_complete", request_start_ts, base_ts=request_start_ts)
            # === VIVENTIUM END ===
    else:
        message = await _SourceOrderedBotProxy(ingress_guard).send_message(
            chat_id=chatid,
            message_thread_id=message_thread_id,
            text=escape("Please enter text after the command"),
            parse_mode='MarkdownV2',
            reply_to_message_id=messageid,
        )

async def delete_message(update, context, messageid=None, delay=60):
    await asyncio.sleep(delay)
    if messageid is None:
        return
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        return
    if isinstance(messageid, list):
        for mid in messageid:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as e:
                pass
    else:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=messageid)
        except Exception:
            pass


def schedule_delete_message(update, context, messageid=None, delay=60):
    if messageid is None:
        return None
    messageids = messageid if isinstance(messageid, list) else [messageid]
    messageids = [mid for mid in messageids if mid is not None]
    if not messageids:
        return None
    coroutine = delete_message(update, context, messageids, delay=delay)
    application = getattr(context, "application", None)
    if application is not None and hasattr(application, "create_task"):
        return application.create_task(
            coroutine,
            update=update,
            name="telegram-delayed-delete-message",
        )
    try:
        return asyncio.create_task(coroutine)
    except RuntimeError:
        coroutine.close()
        logger.debug("Skipped Telegram delayed cleanup task: no running event loop")
        return None


def schedule_background_task(context, coroutine, update=None, name=None):
    application = getattr(context, "application", None)
    if application is not None and hasattr(application, "create_task"):
        return application.create_task(coroutine, update=update, name=name)
    try:
        return asyncio.create_task(coroutine)
    except RuntimeError:
        coroutine.close()
        logger.debug("Skipped Telegram background task %s: no running event loop", name)
        return None


async def refresh_call_button_message(
    context,
    chatid,
    message_id,
    convo_id,
    info_message_md,
    *,
    parallel_available=False,
):
    key = _info_call_refresh_key(chatid, message_id)
    if key is None or key not in _PENDING_INFO_CALL_REFRESHES:
        return
    try:
        call_link = await asyncio.to_thread(get_telegram_call_link_result, convo_id)
        if key not in _PENDING_INFO_CALL_REFRESHES:
            return
        call_url = str(call_link.get("url") or "").strip()
        if not call_url:
            return
        await context.bot.edit_message_text(
            chat_id=chatid,
            message_id=message_id,
            text=info_message_md,
            reply_markup=InlineKeyboardMarkup(
                _main_menu_buttons(
                    convo_id,
                    call_url=call_url,
                    fetch_call_url=False,
                    parallel_available=parallel_available,
                )
            ),
            parse_mode='MarkdownV2',
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.debug("Deferred Telegram call button refresh skipped: %s", e)
    finally:
        _PENDING_INFO_CALL_REFRESHES.discard(key)

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

async def _getViventiumResponse(
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
    reply_context=None,
    _source_guard=None,
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
    # Bind the source sequence before model work. A concurrently ingested later message advances
    # this fence even if Core has not admitted revision N+1 yet.
    source_message_id = telegram_message_id if telegram_message_id is not None else messageid
    source_sender_id = getattr(getattr(update_message, "from_user", None), "id", "")
    _note_telegram_source_message(
        chatid, message_thread_id, source_message_id, source_sender_id
    )
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
    delivery_plan = parse_delivery_controls("")
    delivery_disposition = None
    delivery_disposition_required = False
    delivery_disposition_present = False
    final_segments = []
    logical_turn_id = ""
    logical_turn_revision = None
    delivered_message_ids = []
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
    source_guard = _source_guard or _TelegramSourceOrderGuard(
        bot=context.bot,
        robot=robot,
        telegram_user_id=telegram_user_id,
        chat_id=chatid,
        thread_id=message_thread_id,
        source_sequence=source_message_id,
    )
    context = _SourceOrderedContextProxy(context, source_guard)
    try:
        await _retry_source_order_retractions(source_guard.bot)
        await _retry_pending_source_order_terminals(source_guard.bot, robot, limit=5)
        await _cleanup_obsolete_retry_terminals(
            source_guard.bot,
            telegram_user_id=telegram_user_id,
            chat_id=chatid,
            thread_id=message_thread_id,
            source_sequence=source_message_id,
        )
    except Exception as exc:
        logger.warning("Telegram source-order recovery pass failed: %s", type(exc).__name__)

    # Telegram remains a text-mode surface. Voice preferences control optional audio delivery only;
    # LiveKit voice-call mode/prompt routing stays false for Telegram turns.
    always_voice = False
    voice_responses_enabled = True
    try:
        always_voice = Users.get_config(convo_id, "ALWAYS_VOICE_RESPONSE")
    except Exception:
        pass  # Default to False if preference is unset/unavailable.
    try:
        voice_responses_enabled = Users.get_config(convo_id, "VOICE_RESPONSES_ENABLED")
    except Exception:
        pass  # Default to True if preference is unset/unavailable.
    always_voice_active = normalize_voice_preference(always_voice, False)
    voice_responses_active = normalize_voice_preference(voice_responses_enabled, True)

    telegram_audio_requested = should_request_audio_reply(
        voice_note_detected=voice_note_detected,
        always_voice=always_voice_active,
        voice_enabled=voice_responses_active,
    )
    voice_mode = False
    input_mode = "voice_note" if voice_note_detected else "text"
    # === VIVENTIUM START ===
    _tg_timing_log(
        trace_id,
        "response_start",
        response_start_ts,
        extra=(
            f"voice={int(voice_mode)} audio_requested={int(telegram_audio_requested)} "
            f"input_voice={int(bool(voice_note_detected))} always_voice={int(always_voice_active)} "
            f"files={len(files) if files else 0}"
        ),
    )
    _tg_deep_log(
        trace_id,
        "response_start",
        response_start_ts,
        base_ts=response_start_ts,
        extra=(
            f"voice={int(voice_mode)} audio_requested={int(telegram_audio_requested)} "
            f"input_voice={int(bool(voice_note_detected))} always_voice={int(always_voice_active)} "
            f"files={len(files) if files else 0}"
        ),
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

    async def _source_is_current_for_presentation() -> bool:
        return await source_guard.is_current()

    def _render_telegram_response(text: str, *, streaming_preview: bool = False):
        # === VIVENTIUM NOTE ===
        # Fix: Always render HTML for text display, even when input was a voice note.
        # Voice-note input should NOT degrade text readability.
        # TTS synthesis has its own sanitization path (prepare_tts_text in tts.py).
        return (
            render_telegram_markdown(
                text,
                strip_voice_markup=telegram_audio_requested,
                streaming_preview=streaming_preview,
            ),
            "HTML",
        )
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
    async def _ensure_answer_message(
        rendered_text,
        parse_mode,
        *,
        fallback_text=None,
        reply_to_original=True,
    ):
        nonlocal answer_messageid, lastresult
        if answer_messageid:
            return answer_messageid
        if not await _source_is_current_for_presentation():
            return None
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
        }
        if reply_to_original and messageid:
            send_kwargs["reply_to_message_id"] = messageid
        delivered_text = rendered_text
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
                    **(
                        {"reply_to_message_id": messageid}
                        if reply_to_original and messageid
                        else {}
                    ),
                )
                delivered_text = safe_text
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
        lastresult = delivered_text
        typing_stop.set()
        return answer_messageid
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Coalesced non-blocking stream edits (keeps token ingestion hot).
    stream_preview_pending: Optional[dict[str, Any]] = None
    stream_preview_task: Optional[asyncio.Task] = None
    stream_preview_lock = asyncio.Lock()
    stream_preview_last_sent_ts = 0.0
    stream_preview_superseded = False

    async def _apply_stream_preview(preview: dict[str, Any]) -> None:
        nonlocal answer_messageid, lastresult, stream_preview_last_sent_ts
        source_text = str(preview.get("source_text") or "")
        if not source_text:
            return
        preview_rendered, parse_mode = _render_telegram_response(
            source_text,
            streaming_preview=True,
        )
        rendered_text = first_telegram_html_chunk(preview_rendered)
        fallback_text = strip_html_tags(rendered_text)
        if stream_preview_superseded or not rendered_text or lastresult == rendered_text:
            return
        if not await _source_is_current_for_presentation():
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
                lastresult = fallback
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
        source_text: str,
        *,
        force: bool = False,
    ) -> None:
        nonlocal stream_preview_pending, stream_preview_task
        if (
            stream_preview_superseded
            or not source_text
            or not _is_newest_telegram_source_message(
                chatid,
                message_thread_id,
                source_message_id,
                telegram_user_id,
            )
        ):
            return
        async with stream_preview_lock:
            prev_force = bool(stream_preview_pending.get("force")) if stream_preview_pending else False
            stream_preview_pending = {
                "source_text": source_text,
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

    async def _supersede_stream_preview() -> bool:
        nonlocal answer_messageid, lastresult, stream_preview_superseded
        stream_preview_superseded = True
        await _cancel_stream_previews()
        preview_message_id = answer_messageid
        answer_messageid = None
        lastresult = ""
        if preview_message_id is None:
            return True
        return await source_guard.retract_ref(chatid, preview_message_id)

    async def _deliver_final_message_segments(segments) -> bool:
        nonlocal answer_messageid, lastresult

        async def _notify_interrupted_delivery() -> None:
            try:
                await context.bot.send_message(
                    chat_id=chatid,
                    message_thread_id=message_thread_id,
                    text=TELEGRAM_DELIVERY_INTERRUPTED_NOTICE,
                    disable_web_page_preview=True,
                    read_timeout=time_out,
                    write_timeout=time_out,
                    pool_timeout=time_out,
                    connect_timeout=time_out,
                    reply_to_message_id=messageid,
                )
            except _StaleTelegramSourceOrder:
                raise
            except Exception as notice_error:
                logger.warning(
                    "Failed to deliver Telegram interruption notice: %s",
                    notice_error,
                )

        for index, rendered in enumerate(segments):
            if not await _source_is_current_for_presentation():
                await source_guard.mark_stale()
                return False
            if not rendered:
                continue
            parse_mode = "HTML"
            fallback = strip_html_tags(rendered)
            if index == 0 and answer_messageid:
                if lastresult == rendered:
                    continue
                try:
                    await context.bot.edit_message_text(
                        chat_id=chatid,
                        message_id=answer_messageid,
                        text=rendered,
                        parse_mode=parse_mode,
                        disable_web_page_preview=True,
                        read_timeout=time_out,
                        write_timeout=time_out,
                        pool_timeout=time_out,
                        connect_timeout=time_out,
                    )
                except _StaleTelegramSourceOrder:
                    raise
                except Exception as error:
                    error_text = str(error).lower()
                    if "message is not modified" in error_text:
                        lastresult = rendered
                        continue
                    if "parse entities" in error_text:
                        try:
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
                        except _StaleTelegramSourceOrder:
                            raise
                        except Exception as fallback_error:
                            logger.warning(
                                "Failed to finalize Telegram delivery segment %s: %s",
                                index,
                                fallback_error,
                            )
                            await _notify_interrupted_delivery()
                            return False
                        lastresult = fallback
                        continue
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chatid,
                            message_id=answer_messageid,
                            text=rendered,
                            parse_mode=parse_mode,
                            disable_web_page_preview=True,
                            read_timeout=time_out,
                            write_timeout=time_out,
                            pool_timeout=time_out,
                            connect_timeout=time_out,
                        )
                    except _StaleTelegramSourceOrder:
                        raise
                    except Exception as retry_error:
                        logger.warning(
                            "Failed to finalize Telegram delivery segment %s after retry: %s",
                            index,
                            retry_error,
                        )
                        await _notify_interrupted_delivery()
                        return False
                lastresult = rendered
                continue

            answer_messageid = None
            try:
                await _ensure_answer_message(
                    rendered,
                    parse_mode,
                    fallback_text=fallback,
                    reply_to_original=index == 0,
                )
            except _StaleTelegramSourceOrder:
                raise
            except Exception as error:
                logger.warning(
                    "Failed to send Telegram delivery segment %s: %s",
                    index,
                    error,
                )
                await _notify_interrupted_delivery()
                return False
        return True
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
        bridge_error_audio_allowed = True
        # === VIVENTIUM END ===
        # Installed local-QA only: all unrelated awaits are complete and source order was recorded
        # at ingress. Delay the exact synthetic N+1 event at the Core-admission boundary. The
        # private runtime token and one-shot artifact own authorization and structured targeting.
        if os.environ.get("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE") == TR014_LOCAL_QA_MODE:
            try:
                await maybe_delay_tr014_core_ingestion(
                    SyntheticTelegramSourceEvent(
                        update_id=int(telegram_update_id or 0),
                        chat_id=int(chatid),
                        thread_id=int(message_thread_id or 0),
                        source_sequence=int(source_message_id),
                        owner_user_id=int(telegram_user_id),
                    )
                )
            except Exception as exc:
                logger.error(
                    "TR-014 local-QA control failed closed before Core ingestion: %s",
                    type(exc).__name__,
                )
        async for data in robot.ask_stream_async(
            text,
            convo_id=convo_id,
            telegram_chat_id=chatid,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_message_id=telegram_message_id,
            telegram_message_thread_id=message_thread_id,
            telegram_update_id=telegram_update_id,
            source_event_id=source_guard.source_event_id,
            source_order_scope=source_guard.source_order_scope,
            voice_mode=voice_mode,
            input_mode=input_mode,
            audio_requested=telegram_audio_requested,
            files=files if files else None,  # File data for vision models
            message_timestamp=message_timestamp,  # Time context for scheduling
            client_timezone=client_timezone,  # Timezone for time context formatting
            trace_id=trace_id,
            reply_context=reply_context,
        ):
        # === VIVENTIUM END ===
            # === VIVENTIUM START ===
            # If the bridge emits structured events (e.g., attachments), capture them and continue.
            if isinstance(data, dict):
                if data.get("type") == "bridge_error":
                    bridge_error_audio_allowed = bool(data.get("speak", False))
                    if data.get("recoverable") is True:
                        # The bridge has durably handed this turn to its DB-backed recovery poll.
                        # A pending failure is not a delivered Telegram response and must not be
                        # acknowledged as committed.
                        continue
                    data = str(data.get("text") or "")
                    if not data:
                        continue
                else:
                    if data.get("type") == "delivery_disposition":
                        raw_disposition = data.get("delivery_disposition")
                        delivery_disposition = normalize_delivery_disposition(
                            raw_disposition
                        )
                        delivery_disposition_required = bool(
                            data.get("required") is True
                            or (
                                isinstance(raw_disposition, dict)
                                and raw_disposition.get("required") is True
                            )
                        )
                        delivery_disposition_present = data.get("present") is True
                        continue
                    if data.get("type") == "logical_turn":
                        logical_turn_id = str(data.get("logical_turn_id") or "").strip()
                        logical_turn_revision = data.get("revision")
                        source_guard.bind_delivery(logical_turn_id, logical_turn_revision)
                        continue
                    if data.get("type") == "superseded":
                        logical_turn_id = str(
                            data.get("logical_turn_id") or logical_turn_id or ""
                        ).strip()
                        logical_turn_revision = data.get("revision", logical_turn_revision)
                        preview_removed = await _supersede_stream_preview()
                        if (
                            logical_turn_id
                            and logical_turn_revision is not None
                            and hasattr(robot, "ack_delivery")
                        ):
                            await robot.ack_delivery(
                                logical_turn_id,
                                logical_turn_revision,
                                "partial_removed" if preview_removed else "failed",
                                f"telegram:{chatid}",
                            )
                        return
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
                    if not await _source_is_current_for_presentation():
                        continue
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
            force_preview = "message_search_stage_" in data
            if tmpresult:
                await _queue_stream_preview(
                    tmpresult,
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
        delivery_plan = parse_delivery_controls(result)
        result = delivery_plan.clean_text
        logical_segments = list(delivery_plan.segments)
        if title and logical_segments:
            logical_segments[0] = f"{title}{logical_segments[0]}"
        final_segments = [
            chunk
            for segment in logical_segments
            for chunk in split_telegram_html(_render_telegram_response(segment)[0])
        ]
        tmpresult = f"{title or ''}{result}"
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

            if await _source_is_current_for_presentation():
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
    except _StaleTelegramSourceOrder:
        await source_guard.mark_stale()
        return
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
        bridge_error_audio_allowed = False
        interruption_notice = "Response interrupted before completion. Please try again."
        tmpresult = strip_incomplete_control_suffix(tmpresult)
        tmpresult = (
            f"{tmpresult.rstrip()}\n\n{interruption_notice}"
            if tmpresult.strip()
            else interruption_notice
        )
        delivery_plan = parse_delivery_controls(tmpresult)
        tmpresult = delivery_plan.clean_text
        final_segments = [
            chunk
            for segment in delivery_plan.segments
            for chunk in split_telegram_html(_render_telegram_response(segment)[0])
        ]
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

    # Telegram source order wins even when the newer update reaches Core a few milliseconds late.
    # Remove any preview, record non-delivery for the old revision, and send no obsolete final.
    if not await _source_is_current_for_presentation():
        await source_guard.mark_stale()
        return

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

    text_delivery_succeeded = False
    if final_segments:
        if len(final_segments) > 1:
            await _supersede_stream_preview()
        text_delivery_succeeded = await _deliver_final_message_segments(final_segments)

    # === VIVENTIUM START ===
    # Feature: Centralized gating for voice replies.
    # Reuse the same preference snapshot used before generation so audio delivery
    # stays consistent during one Telegram turn.
    should_send_voice = should_send_voice_reply(
        voice_note_detected=voice_note_detected,
        always_voice=always_voice_active,
        voice_enabled=voice_responses_active,
        text=tmpresult,
    )
    model_skip_requested = bool(delivery_plan.skip_voice)
    delivery_audio_allowed, disposition_decision = resolve_delivery_audio_gate(
        legacy_skip_requested=model_skip_requested,
        delivery_disposition=delivery_disposition,
        disposition_required=delivery_disposition_required,
    )
    model_skip_effective = bool(
        model_skip_requested and should_send_voice and bridge_error_audio_allowed
    )
    disposition_skip_effective = bool(
        not delivery_audio_allowed
        and should_send_voice
        and bridge_error_audio_allowed
    )
    voice_decision = "sent" if should_send_voice else "disabled_user"
    if not delivery_audio_allowed:
        should_send_voice = False
        if disposition_skip_effective:
            voice_decision = {
                "legacy_skip": "skipped_model",
                "structured_skip": "skipped_structured",
                "required_invalid": "skipped_required_contract",
            }.get(disposition_decision, "skipped_delivery_contract")
    if not bridge_error_audio_allowed:
        should_send_voice = False
        voice_decision = "transport_error"
    if not text_delivery_succeeded:
        should_send_voice = False
        voice_decision = "text_delivery_failed"
    disposition_valid = delivery_disposition is not None
    disposition_audio = (
        delivery_disposition["audio"] if disposition_valid else "missing"
    )
    tts_avoided_chars = len(tmpresult) if disposition_skip_effective else 0
    logger.info(
        "[TG_VOICE] trace=%s gate voice_note=%s always_voice=%s voice_enabled=%s "
        "send=%s voice_decision=%s model_skip_requested=%s model_skip_effective=%s "
        "delivery_disposition_present=%s delivery_disposition_required=%s "
        "delivery_disposition_valid=%s delivery_disposition_audio=%s "
        "delivery_disposition_decision=%s tts_avoided_chars=%s "
        "msg_breaks=%s segments=%s segment_merge=%s",
        trace_id,
        int(bool(voice_note_detected)),
        int(always_voice_active),
        int(voice_responses_active),
        int(bool(should_send_voice)),
        voice_decision,
        int(model_skip_requested),
        int(model_skip_effective),
        int(delivery_disposition_present),
        int(delivery_disposition_required),
        int(disposition_valid),
        disposition_audio,
        disposition_decision,
        tts_avoided_chars,
        delivery_plan.message_break_count,
        len(delivery_plan.segments),
        delivery_plan.merged_break_count,
    )
    _tg_timing_log(
        trace_id,
        "voice_gate",
        response_start_ts,
        extra=(
            f"voice_note={int(bool(voice_note_detected))} "
            f"always_voice={int(always_voice_active)} "
            f"voice_enabled={int(voice_responses_active)} "
            f"send={int(bool(should_send_voice))} voice_decision={voice_decision} "
            f"model_skip_requested={int(model_skip_requested)} "
            f"model_skip_effective={int(model_skip_effective)} "
            f"delivery_disposition_present={int(delivery_disposition_present)} "
            f"delivery_disposition_required={int(delivery_disposition_required)} "
            f"delivery_disposition_valid={int(disposition_valid)} "
            f"delivery_disposition_audio={disposition_audio} "
            f"delivery_disposition_decision={disposition_decision} "
            f"tts_avoided_chars={tts_avoided_chars} "
            f"msg_breaks={delivery_plan.message_break_count} "
            f"segments={len(delivery_plan.segments)} "
            f"segment_merge={delivery_plan.merged_break_count}"
        ),
    )
    _tg_deep_log(
        trace_id,
        "voice_gate",
        response_start_ts,
        base_ts=response_start_ts,
        extra=(
            f"voice_note={int(bool(voice_note_detected))} "
            f"always_voice={int(always_voice_active)} "
            f"voice_enabled={int(voice_responses_active)} "
            f"send={int(bool(should_send_voice))} voice_decision={voice_decision} "
            f"model_skip_requested={int(model_skip_requested)} "
            f"model_skip_effective={int(model_skip_effective)} "
            f"delivery_disposition_present={int(delivery_disposition_present)} "
            f"delivery_disposition_required={int(delivery_disposition_required)} "
            f"delivery_disposition_valid={int(disposition_valid)} "
            f"delivery_disposition_audio={disposition_audio} "
            f"delivery_disposition_decision={disposition_decision} "
            f"tts_avoided_chars={tts_avoided_chars} "
            f"msg_breaks={delivery_plan.message_break_count} "
            f"segments={len(delivery_plan.segments)} "
            f"segment_merge={delivery_plan.merged_break_count}"
        ),
    )
    # === VIVENTIUM END ===
    
    if should_send_voice:
        cleaned_voice = config.prepare_tts_text(tmpresult)
        if cleaned_voice:
            try:
                if _voice_debug_enabled():
                    logger.info(
                        "[VoiceMarkup][telegram] trace=%s raw_llm=%s tts_text=%s display_text=%s",
                        trace_id,
                        _voice_debug_text(tmpresult),
                        _voice_debug_text(cleaned_voice),
                        _voice_debug_text(sanitize_telegram_display_text(tmpresult)),
                    )
                voice_route = None
                if hasattr(robot, "get_cached_voice_route"):
                    voice_route = (
                        robot.get_cached_voice_route(str(convo_id))
                        or robot.get_cached_voice_route(str(chatid))
                    )
                resolved_tts = resolve_tts_selection(voice_route=voice_route)
                tts_provider = (resolved_tts.get("provider") or "").strip().lower()
                voice_markup = summarize_voice_markup(cleaned_voice)
                logger.info(
                    "[TG_VOICE] trace=%s tts_start provider=%s source=%s chars=%s route_cached=%s",
                    trace_id,
                    tts_provider or "default",
                    resolved_tts.get("source") or "unknown",
                    len(cleaned_voice),
                    int(isinstance(voice_route, dict)),
                )
                logger.info(
                    "[VoiceMarkup][telegram] trace=%s tts_markers laughter=%s "
                    "emotion_tags=%s break_tags=%s speed_tags=%s volume_tags=%s "
                    "xai_inline_tags=%s xai_wrapping_tags=%s "
                    "xai_square_wrapping_tags=%s xai_total=%s",
                    trace_id,
                    voice_markup["laughter"],
                    voice_markup["emotion"],
                    voice_markup["break"],
                    voice_markup["speed"],
                    voice_markup["volume"],
                    voice_markup["xai_inline"],
                    voice_markup["xai_wrapping"],
                    voice_markup["xai_square_wrapping"],
                    voice_markup["xai_total"],
                )
                # === VIVENTIUM START ===
                # Feature: Timing for TTS synthesis + send.
                tts_start_ts = time.monotonic()
                # === VIVENTIUM END ===
                # Chunk long text to prevent audio degradation and cutoffs (ElevenLabs best practice: < 800 chars)
                # Split by sentences to maintain natural flow
                # Note: 're' is already imported at top of file
                max_chunk_size = 800
                if "chatterbox" in tts_provider or tts_provider in {"cartesia", "xai"}:
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
                    chunk_wall_start_ts = time.monotonic()
                    voice_bytes = await synthesize_speech(chunk, convo_id, voice_route=voice_route)
                    if voice_bytes:
                        all_audio_chunks.append(voice_bytes)
                        logger.info(
                            "[TG_VOICE] trace=%s tts_chunk idx=%s/%s chars=%s bytes=%s ms=%.1f",
                            trace_id,
                            i + 1,
                            len(chunks),
                            len(chunk),
                            len(voice_bytes),
                            (time.monotonic() - chunk_wall_start_ts) * 1000,
                        )
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
                    logger.info(
                        "[TG_VOICE] trace=%s audio_sent chunks=%s bytes=%s ms=%.1f",
                        trace_id,
                        len(all_audio_chunks),
                        len(combined_audio),
                        (time.monotonic() - tts_start_ts) * 1000,
                    )
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

    if source_guard.stale:
        return

    presentation_refs = source_guard.presentation_refs()
    if logical_turn_id and logical_turn_revision is not None and presentation_refs:
        delivery_ack_status = "unavailable"
        try:
            ack_args = (
                logical_turn_id,
                logical_turn_revision,
                "committed",
                presentation_refs[-1],
                presentation_refs,
            )
            if hasattr(robot, "ack_delivery_status"):
                delivery_ack_status = await robot.ack_delivery_status(*ack_args)
            elif hasattr(robot, "ack_delivery") and await robot.ack_delivery(*ack_args):
                delivery_ack_status = "recorded"
        except Exception as exc:
            logger.warning(
                "Telegram commit acknowledgement failed closed: %s", type(exc).__name__
            )
        if delivery_ack_status != "recorded":
            if delivery_ack_status not in {
                "stale_revision",
                "stale_source_order",
                "conflict",
            }:
                pending_claim = source_guard.reserve_pending_retry_terminal()
                if pending_claim is None:
                    await source_guard.retract_all()
                    return
                retry_terminal_id = None
                try:
                    retry_terminal_id = await source_guard.send_retryable_terminal(
                        persist=False, pending_claim=pending_claim
                    )
                except Exception as exc:
                    logger.warning(
                        "Telegram retry terminal delivery failed: %s", type(exc).__name__
                    )
                if source_guard.stale:
                    source_guard._store.complete_pending_terminal(pending_claim)
                elif retry_terminal_id is None:
                    source_guard._store.reschedule_pending_terminal(pending_claim)
            else:
                await source_guard.retract_all()
            return

    # REMOVED: FOLLOW_UP feature - Uses SummaryBot which is None (not available with LiveKit Bridge)
    # Follow-up questions should be handled by Viventium if needed

    # REMOVED: Memory manager - LiveKitBridge doesn't have memory_manager
    # Memory is handled by Viventium, not the bot


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
    reply_context=None,
    _source_guard=None,
):
    source_message_id = telegram_message_id if telegram_message_id is not None else messageid
    telegram_user_id = getattr(getattr(update_message, "from_user", None), "id", "")
    cache_key = _activate_telegram_source_message(
        chatid, message_thread_id, source_message_id, telegram_user_id
    )
    try:
        return await _getViventiumResponse(
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
            files=files,
            trace_id=trace_id,
            telegram_message_id=telegram_message_id,
            telegram_update_id=telegram_update_id,
            reply_context=reply_context,
            _source_guard=_source_guard,
        )
    except _StaleTelegramSourceOrder:
        return None
    finally:
        _release_telegram_source_message(cache_key)

# === VIVENTIUM START ===
# Performance: Removed @AdminAuthorization, @GroupAuthorization, @Authorization
# decorators from button_press.  Each decorator calls GetMesageInfo which downloads
# files, extracts documents, transcribes voice — adding ~500ms+ per decorator.
# Local preference callbacks resolve against the requesting Telegram identity. Parallel Work
# callbacks additionally require one-use user/chat-scoped capabilities because group keyboards
# can be pressed by someone other than the person who opened them.
# === VIVENTIUM END ===
async def _handle_parallel_work_callback(update, context, callback_query, data):
    user_id = str(getattr(getattr(update, "effective_user", None), "id", "") or "")
    chat_id = str(getattr(getattr(update, "effective_chat", None), "id", "") or "")
    client = _get_parallel_work_client()
    store = _get_parallel_work_callback_store()
    retry_callback_data = ""
    page_retry_callback_data = ""

    try:
        if data == "PW:S":
            snapshot = await client.get_preference(user_id)
            text, markup = _parallel_work_settings_view(snapshot)
        elif data == "PW:L":
            snapshot = await client.get_snapshot(user_id)
            text, markup = _active_work_view(
                snapshot,
                telegram_user_id=user_id,
                chat_id=chat_id,
            )
        elif data.startswith("PW:P:"):
            reservation = store.reserve_page(
                data[len("PW:P:"):],
                telegram_user_id=user_id,
                chat_id=chat_id,
            )
            if reservation is None:
                text, markup = _parallel_work_expired_view()
            else:
                try:
                    snapshot = await client.get_snapshot(user_id, cursor=reservation.cursor)
                except OrchestrationError as error:
                    store.complete_page(
                        reservation,
                        succeeded=False,
                        definitive=not bool(getattr(error, "indeterminate", False)),
                    )
                    if getattr(error, "indeterminate", False):
                        page_retry_callback_data = data
                    raise
                except Exception as error:
                    store.complete_page(reservation, succeeded=False, definitive=False)
                    page_retry_callback_data = data
                    raise OrchestrationError(
                        "Active work could not be loaded right now. Existing work may still be running.",
                        indeterminate=True,
                    ) from error
                store.complete_page(reservation, succeeded=True)
                text, markup = _active_work_view(
                    snapshot,
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                )
        elif data in {"PW:T:0", "PW:T:1"}:
            snapshot = await client.set_parallel_work(user_id, data.endswith(":1"))
            text, markup = _parallel_work_settings_view(snapshot)
        elif data.startswith("PW:A:"):
            token = data[len("PW:A:"):]
            reservation = store.reserve_action(
                token,
                telegram_user_id=user_id,
                chat_id=chat_id,
            )
            if reservation is None:
                text, markup = _parallel_work_expired_view()
            elif reservation.target.action in CONFIRM_ACTIONS:
                store.complete_action(reservation, succeeded=True, receipt="confirmation_opened")
                text, markup = _parallel_work_confirmation_view(
                    reservation.target,
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                )
            elif reservation.target.action in INSTRUCTION_ACTIONS:
                store.complete_action(reservation, succeeded=True, receipt="instruction_prompted")
                prompt = store.reserve_prompt(
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                    work_ref=reservation.target.work_ref,
                    action=reservation.target.action,
                )
                action_description = {
                    "queue": "queue follow-up work for",
                    "message": "message",
                    "steer": "steer",
                }[reservation.target.action]
                await context.bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=getattr(callback_query.message, "message_thread_id", None),
                    text=(
                        f"{PARALLEL_WORK_PROMPT_PREFIX} · {prompt.token}\n"
                        f"Reply with the instruction to {action_description} this worker."
                    ),
                    reply_markup=ForceReply(selective=True),
                )
                return
            else:
                retry_callback_data = data
                snapshot = await _execute_parallel_work_action(
                    client=client,
                    store=store,
                    telegram_user_id=user_id,
                    reservation=reservation,
                )
                text, markup = _active_work_view(
                    snapshot,
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                )
        elif data.startswith("PW:C:"):
            parts = data.split(":", 3)
            if len(parts) != 4 or parts[2] not in {"Y", "N"}:
                text, markup = _parallel_work_expired_view()
            else:
                if parts[2] == "N":
                    target = store.consume_action(
                        parts[3],
                        telegram_user_id=user_id,
                        chat_id=chat_id,
                    )
                    if target is None:
                        text, markup = _parallel_work_expired_view()
                    else:
                        text, markup = (
                            "Action cancelled. The work was not stopped.",
                            InlineKeyboardMarkup(
                                [[InlineKeyboardButton("Active work", callback_data="PW:L")]]
                            ),
                        )
                else:
                    reservation = store.reserve_action(
                        parts[3],
                        telegram_user_id=user_id,
                        chat_id=chat_id,
                    )
                    if reservation is None:
                        text, markup = _parallel_work_expired_view()
                    else:
                        retry_callback_data = data
                        snapshot = await _execute_parallel_work_action(
                            client=client,
                            store=store,
                            telegram_user_id=user_id,
                            reservation=reservation,
                        )
                        text, markup = _active_work_view(
                            snapshot,
                            telegram_user_id=user_id,
                            chat_id=chat_id,
                        )
        elif data.startswith("PW:R:"):
            token = data[len("PW:R:"):]
            reserved = store.reserve_prompt_action(
                token,
                telegram_user_id=user_id,
                chat_id=chat_id,
            )
            if reserved is None:
                text, markup = _parallel_work_expired_view()
            else:
                reservation, instruction = reserved
                retry_callback_data = data
                snapshot = await _execute_parallel_work_action(
                    client=client,
                    store=store,
                    telegram_user_id=user_id,
                    reservation=reservation,
                    instruction=instruction,
                )
                text, markup = _active_work_view(
                    snapshot,
                    telegram_user_id=user_id,
                    chat_id=chat_id,
                )
        else:
            text, markup = _parallel_work_expired_view()
    except OrchestrationLinkRequired as error:
        text, markup = _parallel_work_link_view(error)
    except OrchestrationError as error:
        if retry_callback_data and bool(getattr(error, "indeterminate", False)):
            text, markup = _parallel_work_action_retry_view(error, retry_callback_data)
        elif page_retry_callback_data:
            text, markup = _parallel_work_page_retry_view(error, page_retry_callback_data)
        else:
            text, markup = _parallel_work_unavailable_view(str(error))

    await _edit_parallel_work_view(
        callback_query,
        context,
        text=text,
        reply_markup=markup,
        update=update,
    )


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

        if data.startswith("PW:"):
            _cancel_info_call_refresh_for_query(callback_query)
            await _handle_parallel_work_callback(update, context, callback_query, data)

        elif data.endswith("_PREFERENCES"):
            _cancel_info_call_refresh_for_query(callback_query)
            pref_key = data[:-12]
            _t3 = _time.monotonic()
            try:
                Users.toggle_config(convo_id, pref_key)
            except Exception as e:
                logger.info(e)
            _t4 = _time.monotonic()
            parallel_available = await _parallel_work_available(
                getattr(getattr(update, "effective_user", None), "id", "")
            )
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(
                    _preferences_menu_buttons(
                        convo_id,
                        parallel_available=parallel_available,
                    )
                ),
                fallback_text=info_message_md,
            )
            _t5 = _time.monotonic()
            logger.info("[PREF_TIMING] toggle=%s set=%.0fms edit=%.0fms total=%.0fms", pref_key, (_t4-_t3)*1000, (_t5-_t4)*1000, (_t5-_t0)*1000)

        elif data.startswith("PREFERENCES"):
            _cancel_info_call_refresh_for_query(callback_query)
            parallel_available = await _parallel_work_available(
                getattr(getattr(update, "effective_user", None), "id", "")
            )
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(
                    _preferences_menu_buttons(
                        convo_id,
                        parallel_available=parallel_available,
                    )
                ),
                fallback_text=info_message_md,
            )
            _t5 = _time.monotonic()
            logger.info("[PREF_TIMING] open_menu edit=%.0fms total=%.0fms", (_t5-_t2)*1000, (_t5-_t0)*1000)

        elif data.startswith("BACK"):
            _cancel_info_call_refresh_for_query(callback_query)
            parallel_available = await _parallel_work_available(
                getattr(getattr(update, "effective_user", None), "id", "")
            )
            await _edit_or_send_menu(
                reply_markup=InlineKeyboardMarkup(
                    _main_menu_buttons(
                        convo_id,
                        fetch_call_url=False,
                        parallel_available=parallel_available,
                    )
                ),
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
                reply_markup=InlineKeyboardMarkup(
                    _preferences_menu_buttons(convo_id, parallel_available=False)
                ),
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
    ingress_guard = await _observe_telegram_update_ingress(update, context)
    if ingress_guard is None:
        return
    if await _queue_media_group_update(
        update, context, source="file", ingress_guard=ingress_guard
    ):
        return
    message, rawtext, image_url, chatid, messageid, reply_to_message_text, update_message, message_thread_id, convo_id, file_url, reply_to_message_file_content, voice_text, voice_error_text, file_data_list, file_error_list = _unpack_message_info(await GetMesageInfo(update, context))
    if voice_error_text:
        await _with_source_ordered_context_bot(
            context,
            ingress_guard,
            lambda guarded_context: _resolve_voice_input_message(
                guarded_context,
                chatid=chatid,
                messageid=messageid,
                message_thread_id=message_thread_id,
                message=message,
                voice_text=voice_text,
                voice_error_text=voice_error_text,
                show_transcription=False,
            ),
        )
        return
    if file_error_list:
        await _with_source_ordered_context_bot(
            context,
            ingress_guard,
            lambda guarded_context: _send_telegram_attachment_error(
                guarded_context,
                chatid,
                message_thread_id,
                messageid,
                file_error_list,
            ),
        )
        return
    robot, _, api_key, api_url = get_robot(convo_id)  # api_key/api_url only for document extraction
    ingress_guard.robot = robot
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
        telegram_message_id=messageid,
        telegram_update_id=getattr(update, "update_id", None),
        reply_context=_telegram_reply_context_v1(
            update_message,
            getattr(getattr(context, "bot", None), "id", None),
            reply_to_message_file_content,
            getattr(getattr(update_message, "from_user", None), "id", None),
        ),
        _source_guard=ingress_guard,
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
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, _, _, _, _ = _unpack_message_info(await GetMesageInfo(update, context))
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
    schedule_delete_message(update, context, [message.message_id, user_message_id])

@decorators.AdminAuthorization
@decorators.GroupAuthorization
@decorators.Authorization
async def info(update, context):
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, voice_text, _, _, _ = _unpack_message_info(await GetMesageInfo(update, context))
    info_message = update_info_message(convo_id)
    parallel_available = await _parallel_work_available(
        getattr(getattr(update, "effective_user", None), "id", "")
    )
    message = await context.bot.send_message(
        chat_id=chatid,
        message_thread_id=message_thread_id,
        text=escape(info_message, italic=False),
        reply_markup=InlineKeyboardMarkup(
            _main_menu_buttons(
                convo_id,
                fetch_call_url=False,
                parallel_available=parallel_available,
            )
        ),
        parse_mode='MarkdownV2',
        disable_web_page_preview=True,
        read_timeout=600,
    )
    _mark_info_call_refresh(chatid, message.message_id)
    schedule_delete_message(update, context, [user_message_id])
    schedule_background_task(
        context,
        refresh_call_button_message(
            context,
            chatid,
            message.message_id,
            convo_id,
            escape(info_message, italic=False),
            parallel_available=parallel_available,
        ),
        update=update,
        name="telegram-refresh-info-call-button",
    )


@decorators.GroupAuthorization
@decorators.Authorization
async def call(update, context):
    _, _, _, chatid, user_message_id, _, _, message_thread_id, convo_id, _, _, _, _, _, _ = _unpack_message_info(await GetMesageInfo(
        update, context
    ))
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
        schedule_delete_message(update, context, [message.message_id, user_message_id])
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
    schedule_delete_message(update, context, [user_message_id])

@decorators.GroupAuthorization
@decorators.Authorization
async def start(update, context):
    # === VIVENTIUM NOTE ===
    # Feature: Route /start through getViventiumResponse for dynamic agent-driven onboarding.
    # Preserves legacy API key arg handling for residual features.
    # === VIVENTIUM NOTE ===
    _, _, _, chatid, messageid, _, update_message, message_thread_id, convo_id, _, _, _, _, _, _ = _unpack_message_info(await GetMesageInfo(update, context))

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
    if "telegram.error.Conflict" in traceback_string or "terminated by other getUpdates request" in traceback_string:
        logger.error(
            "Telegram getUpdates conflict detected: another process is polling this BotFather token. "
            "Stop the duplicate Telegram bot process before retrying voice replies."
        )
        return
    if "telegram.error.TimedOut: Timed out" in traceback_string:
        logger.warning('error: telegram.error.TimedOut: Timed out')
        return
    if "Message to be replied not found" in traceback_string:
        logger.warning('error: telegram.error.BadRequest: Message to be replied not found')
        return
    logger.warning(
        'Telegram update caused error "%s" (update_id=%s, message_id=%s)',
        context.error,
        getattr(update, "update_id", None),
        getattr(getattr(update, "effective_message", None), "message_id", None),
    )
    logger.warning('Error traceback: %s', ''.join(traceback_string))

# REMOVED: MCP Commands - MCP integration is handled by Viventium agent directly
# The bot no longer needs separate MCP client commands since Viventium manages MCP servers

# ========================================

# REMOVED: unknown function - Returns immediately, does nothing. Handler still registered but function removed.

_SOURCE_ORDER_RECOVERY_TASK_KEY = "viventium_source_order_recovery_task"
_BOT_METADATA_TASK_KEY = "viventium_bot_metadata_task"


async def _source_order_recovery_loop(application: Application) -> None:
    while True:
        try:
            await _retry_source_order_retractions(application.bot)
            robot = config.ChatGPTbot
            if robot and hasattr(robot, "source_order_is_current"):
                await _retry_pending_source_order_terminals(
                    application.bot,
                    robot,
                    limit=1,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram source-order recovery loop failed: %s", type(exc).__name__)
        await asyncio.sleep(5)

def _write_telegram_ready_marker() -> bool:
    ready_file = os.environ.get("VIVENTIUM_TELEGRAM_READY_FILE")
    if not ready_file:
        logger.error("Telegram ready marker path is not configured")
        return False
    marker = Path(ready_file)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_name(f"{marker.name}.{os.getpid()}.tmp")
    temporary.write_text(f"{os.getpid()}\n", encoding="utf-8")
    os.replace(temporary, marker)
    logger.info("Telegram application ready marker written (pid=%s)", os.getpid())
    return True


async def _refresh_telegram_bot_metadata(application: Application) -> None:
    try:
        await application.bot.set_my_commands([
            BotCommand('call', 'Open a live Viventium call'),
            BotCommand('info', 'Basic information'),
            BotCommand('reset', 'Reset the bot'),
            BotCommand('start', 'Start the bot'),
        ])
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Telegram command metadata refresh failed: %s", type(exc).__name__)

    description = (
        "I am an Assistant, a large language model trained by OpenAI. I will do my best to help answer your questions."
    )
    try:
        await application.bot.set_my_description(description)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Telegram description metadata refresh failed: %s", type(exc).__name__)


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
        message_thread_id: Optional[int] = None,
        before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    ):
        try:
            return await deliver_proactive_telegram_message(
                application.bot,
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                voice_audio=voice_audio,
                message_thread_id=message_thread_id,
                before_side_effect=before_side_effect,
            )
        except Exception as e:
            logging.error(f"Failed to deliver proactive message to {chat_id}: {e}")
            raise

    async def on_proactive_retraction(chat_id: int, message_id: str) -> None:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            _TelegramRetractionStore().enqueue(str(chat_id), str(message_id))

    if config.ChatGPTbot:
        config.ChatGPTbot.set_on_message_callback(on_proactive_message)
        config.ChatGPTbot.set_on_retraction_callback(on_proactive_retraction)
        config.ChatGPTbot.start_cortex_ack_dispatcher()
        if hasattr(config.ChatGPTbot, "start_glasshive_delivery_dispatcher"):
            config.ChatGPTbot.start_glasshive_delivery_dispatcher()
        logging.info(
            "✅ Registered proactive message callback with Telegram bridge (%s)",
            getattr(config, "VIVENTIUM_TELEGRAM_BACKEND", "unknown"),
        )

    application.bot_data[_SOURCE_ORDER_RECOVERY_TASK_KEY] = asyncio.create_task(
        _source_order_recovery_loop(application)
    )
    application.bot_data[_BOT_METADATA_TASK_KEY] = asyncio.create_task(
        _refresh_telegram_bot_metadata(application)
    )
    application.bot_data["viventium_telegram_readiness_task"] = None
    if getattr(application, "updater", None) is not None:
        application.bot_data["viventium_telegram_readiness_task"] = (
            schedule_telegram_singleton_readiness(
                application,
                BOT_TOKEN,
                transport="webhook" if WEB_HOOK else "polling",
            )
        )
    _write_telegram_ready_marker()
    acknowledge_local_qa_service("telegram-bot")


async def post_shutdown(application: Application) -> None:
    await cancel_telegram_singleton_readiness(
        application.bot_data.pop("viventium_telegram_readiness_task", None)
    )
    for task_key in (_SOURCE_ORDER_RECOVERY_TASK_KEY, _BOT_METADATA_TASK_KEY):
        task = application.bot_data.pop(task_key, None)
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if config.ChatGPTbot and hasattr(config.ChatGPTbot, "stop_glasshive_delivery_dispatcher"):
        config.ChatGPTbot.stop_glasshive_delivery_dispatcher()
    clear_telegram_singleton_receipt()


# === VIVENTIUM START ===
# Feature: Receptive Telegram ingress and control registration.
# Purpose: Slow turns, file capture, settings, and work controls must not occupy the dispatcher.
def _register_application_handlers(application: Application) -> None:
    """Register receptive ingress/control handlers through one testable contract."""

    application.add_handler(CommandHandler("call", call, block=False))
    application.add_handler(CommandHandler("info", info, block=False))
    application.add_handler(CommandHandler("start", start, block=False))
    application.add_handler(CommandHandler("reset", reset_chat, block=False))
    # Preferences and present/future Active Work controls share this callback surface.
    application.add_handler(CallbackQueryHandler(button_press, block=False))
    application.add_handler(
        MessageHandler(
            _ParallelWorkInstructionReplyFilter(),
            parallel_work_instruction_reply,
            block=False,
        )
    )
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.VOICE | filters.VIDEO_NOTE) & ~filters.COMMAND,
            lambda update, context: command_bot(update, context, has_command=False),
            block=False,
        )
    )
    application.add_handler(
        MessageHandler(
            _telegram_captioned_attachment_filter(),
            lambda update, context: command_bot(update, context, has_command=False),
            block=False,
        )
    )
    application.add_handler(
        MessageHandler(
            _telegram_uncaptioned_attachment_filter(),
            handle_file,
            block=False,
        )
    )
    application.add_error_handler(error)
# === VIVENTIUM END ===

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
    _acquire_telegram_singleton_or_exit()

    telegram_bot_api_base_url = (
        getattr(config, "VIVENTIUM_TELEGRAM_BOT_API_BASE_URL", "") or ""
    ).strip()
    telegram_bot_api_base_file_url = (
        getattr(config, "VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL", "") or ""
    ).strip()
    telegram_bot_local_mode = bool(
        getattr(config, "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED", False)
    )

    builder = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
    )
    if telegram_bot_api_base_url:
        builder = builder.base_url(telegram_bot_api_base_url)
    if telegram_bot_api_base_file_url:
        builder = builder.base_file_url(telegram_bot_api_base_file_url)
    if telegram_bot_local_mode:
        builder = builder.local_mode(True)

    application = (
        builder
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
        .post_shutdown(post_shutdown)
        .build()
    )

    # REMOVED: Model selection handler - Model selection is handled by Viventium
    # REMOVED: MCP command handlers - MCP integration handled by Viventium agent directly
    # REMOVED: InlineQueryHandler - Inline queries disabled, all messages route through LiveKit Bridge
    _register_application_handlers(application)

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
