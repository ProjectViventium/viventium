from __future__ import annotations

import json
import logging
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.json_state import JsonStateFile


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_paired_users() -> dict[str, Any]:
    return {"version": 1, "paired_users": []}


def _default_pending_pairs() -> dict[str, Any]:
    return {"version": 1, "pending_pairs": []}


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    state: str
    message: str
    pairing_url: str = ""


@dataclass(frozen=True)
class PendingPair:
    token: str
    telegram_user_id: str
    telegram_username: str
    chat_id: str
    created_at: str
    expires_at: str


class AccessControl:
    def __init__(
        self,
        *,
        paired_users_path: Path,
        paired_users_migration_sources: tuple[Path, ...] = (),
        pending_pairs_path: Path,
        link_ttl_minutes: int,
        bootstrap_if_empty: bool,
    ) -> None:
        self._paired_users = JsonStateFile(paired_users_path, _default_paired_users)
        self._pending_pairs = JsonStateFile(pending_pairs_path, _default_pending_pairs)
        self._paired_users_migration_sources = tuple(path.resolve() for path in paired_users_migration_sources)
        self._link_ttl_minutes = link_ttl_minutes
        self._bootstrap_if_empty = bootstrap_if_empty
        self._migrate_legacy_paired_users()

    def list_paired_users(self) -> list[dict[str, str]]:
        data = self._paired_users.read()
        return list(data.get("paired_users") or [])

    def get_pending_pair(self, token: str) -> PendingPair | None:
        self._prune_expired_pending_tokens()
        data = self._pending_pairs.read()
        for item in data.get("pending_pairs") or []:
            if item.get("token") == token:
                return PendingPair(
                    token=item["token"],
                    telegram_user_id=item["telegram_user_id"],
                    telegram_username=item.get("telegram_username", ""),
                    chat_id=item.get("chat_id", ""),
                    created_at=item["created_at"],
                    expires_at=item["expires_at"],
                )
        return None

    def is_authorized(self, telegram_user_id: str) -> bool:
        normalized = str(telegram_user_id or "").strip()
        if not normalized:
            return False
        return any(item.get("telegram_user_id") == normalized for item in self.list_paired_users())

    def authorize_or_begin_pairing(
        self,
        *,
        telegram_user_id: str,
        telegram_username: str,
        chat_id: str,
        base_url: str,
    ) -> AccessDecision:
        normalized_user_id = str(telegram_user_id or "").strip()
        normalized_username = str(telegram_username or "").strip()
        normalized_chat_id = str(chat_id or "").strip()

        if self.is_authorized(normalized_user_id):
            return AccessDecision(
                allowed=True,
                state="allowed",
                message="Authorized Telegram user.",
            )

        paired_users = self.list_paired_users()
        if paired_users:
            return AccessDecision(
                allowed=False,
                state="denied",
                message="This bot is private and is already locked to a different Telegram account.",
            )

        if not self._bootstrap_if_empty:
            return AccessDecision(
                allowed=False,
                state="denied",
                message="Pairing bootstrap is disabled for this bot.",
            )

        pending = self._create_or_replace_pending_pair(
            telegram_user_id=normalized_user_id,
            telegram_username=normalized_username,
            chat_id=normalized_chat_id,
        )
        return AccessDecision(
            allowed=False,
            state="pairing_required",
            message="Open the pairing link on this laptop to approve this Telegram account.",
            pairing_url=f"{base_url}/pair/{pending.token}",
        )

    def confirm_pairing(self, token: str) -> PendingPair | None:
        pending = self.get_pending_pair(token)
        if pending is None:
            return None

        def _consume_pending(data: dict[str, Any]) -> None:
            data["pending_pairs"] = [
                item for item in (data.get("pending_pairs") or []) if item.get("token") != token
            ]

        def _upsert_paired(data: dict[str, Any]) -> None:
            paired_users = data.get("paired_users") or []
            paired_users = [
                item
                for item in paired_users
                if item.get("telegram_user_id") != pending.telegram_user_id
            ]
            paired_users.append(
                {
                    "telegram_user_id": pending.telegram_user_id,
                    "telegram_username": pending.telegram_username,
                    "paired_at": _utc_now().isoformat(),
                    "paired_on_host": socket.gethostname(),
                    "paired_via_chat_id": pending.chat_id,
                }
            )
            data["paired_users"] = paired_users

        self._pending_pairs.update(_consume_pending)
        self._paired_users.update(_upsert_paired)
        return pending

    def _create_or_replace_pending_pair(
        self,
        *,
        telegram_user_id: str,
        telegram_username: str,
        chat_id: str,
    ) -> PendingPair:
        self._prune_expired_pending_tokens()
        token = secrets.token_urlsafe(24)
        created_at = _utc_now()
        expires_at = created_at + timedelta(minutes=self._link_ttl_minutes)

        pending = PendingPair(
            token=token,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            chat_id=chat_id,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        def _save(data: dict[str, Any]) -> None:
            pending_pairs = data.get("pending_pairs") or []
            pending_pairs = [
                item
                for item in pending_pairs
                if item.get("telegram_user_id") != telegram_user_id and item.get("chat_id") != chat_id
            ]
            pending_pairs.append(
                {
                    "token": pending.token,
                    "telegram_user_id": pending.telegram_user_id,
                    "telegram_username": pending.telegram_username,
                    "chat_id": pending.chat_id,
                    "created_at": pending.created_at,
                    "expires_at": pending.expires_at,
                }
            )
            data["pending_pairs"] = pending_pairs

        self._pending_pairs.update(_save)
        return pending

    def _prune_expired_pending_tokens(self) -> None:
        now = _utc_now()

        def _prune(data: dict[str, Any]) -> None:
            keep: list[dict[str, Any]] = []
            for item in data.get("pending_pairs") or []:
                expires_at_raw = str(item.get("expires_at") or "").strip()
                try:
                    expires_at = datetime.fromisoformat(expires_at_raw)
                except Exception:
                    continue
                if expires_at > now:
                    keep.append(item)
            data["pending_pairs"] = keep

        self._pending_pairs.update(_prune)

    def _migrate_legacy_paired_users(self) -> None:
        if not self._paired_users_migration_sources:
            return

        def _merge(data: dict[str, Any]) -> int:
            paired_users = list(data.get("paired_users") or [])
            seen_user_ids = {
                str(item.get("telegram_user_id") or "").strip()
                for item in paired_users
                if str(item.get("telegram_user_id") or "").strip()
            }
            migrated_count = 0

            for source_path in self._paired_users_migration_sources:
                for entry in self._read_paired_users_snapshot(source_path):
                    telegram_user_id = str(entry.get("telegram_user_id") or "").strip()
                    if not telegram_user_id or telegram_user_id in seen_user_ids:
                        continue
                    normalized_entry = dict(entry)
                    normalized_entry["telegram_user_id"] = telegram_user_id
                    paired_users.append(normalized_entry)
                    seen_user_ids.add(telegram_user_id)
                    migrated_count += 1

            data["paired_users"] = paired_users
            return migrated_count

        migrated_count = self._paired_users.update(_merge)
        if migrated_count:
            logger.info(
                "Migrated %s paired Telegram user(s) into durable store %s",
                migrated_count,
                self._paired_users.path,
            )

    @staticmethod
    def _read_paired_users_snapshot(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        items = payload.get("paired_users") or []
        return [item for item in items if isinstance(item, dict)]
