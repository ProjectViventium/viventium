from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.json_state import JsonStateFile


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_sessions() -> dict[str, Any]:
    return {"version": 1, "sessions": {}}


@dataclass(frozen=True)
class ChatSession:
    chat_id: str
    project_alias: str
    thread_id: str | None
    updated_at: str


class SessionStore:
    def __init__(self, path: Path, default_project_alias: str) -> None:
        self._state = JsonStateFile(path, _default_sessions)
        self._default_project_alias = default_project_alias

    def get(self, chat_id: int | str) -> ChatSession:
        key = str(chat_id)
        data = self._state.read()
        sessions = data.get("sessions") or {}
        item = sessions.get(key) or {}
        return ChatSession(
            chat_id=key,
            project_alias=str(item.get("project_alias") or self._default_project_alias),
            thread_id=str(item.get("thread_id")).strip() if item.get("thread_id") else None,
            updated_at=str(item.get("updated_at") or _utc_now()),
        )

    def set_project(self, chat_id: int | str, project_alias: str, *, clear_thread: bool = True) -> ChatSession:
        key = str(chat_id)

        def _update(data: dict[str, Any]) -> ChatSession:
            sessions = data.setdefault("sessions", {})
            item = sessions.setdefault(key, {})
            item["project_alias"] = project_alias
            if clear_thread:
                item["thread_id"] = None
            item["updated_at"] = _utc_now()
            return ChatSession(
                chat_id=key,
                project_alias=project_alias,
                thread_id=item.get("thread_id"),
                updated_at=item["updated_at"],
            )

        return self._state.update(_update)

    def set_thread(self, chat_id: int | str, thread_id: str | None) -> ChatSession:
        key = str(chat_id)

        def _update(data: dict[str, Any]) -> ChatSession:
            sessions = data.setdefault("sessions", {})
            item = sessions.setdefault(
                key,
                {"project_alias": self._default_project_alias, "thread_id": None, "updated_at": _utc_now()},
            )
            item["thread_id"] = thread_id
            item["updated_at"] = _utc_now()
            return ChatSession(
                chat_id=key,
                project_alias=str(item.get("project_alias") or self._default_project_alias),
                thread_id=item.get("thread_id"),
                updated_at=item["updated_at"],
            )

        return self._state.update(_update)

    def reset(self, chat_id: int | str) -> ChatSession:
        return self.set_thread(chat_id, None)

