from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class AuthContext:
    authenticated: bool
    admin: bool
    method: str = "none"
    user_id: str = ""
    email: str = ""
    reason: str = ""

    def payload(self) -> dict[str, Any]:
        return {
            "authenticated": self.authenticated,
            "admin": self.admin,
            "method": self.method,
            "userId": self.user_id or None,
            "email": self.email or None,
            "reason": self.reason or None,
        }


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _configured_launch_token() -> str:
    return (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN") or "").strip()


def _request_token(request: Request) -> str:
    header = request.headers.get("x-viventium-workbench-token", "").strip()
    if header:
        return header
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip()
    return ""


def _token_auth(request: Request) -> AuthContext | None:
    expected = _configured_launch_token()
    if not expected:
        return None
    if _request_token(request) != expected:
        return None
    return AuthContext(
        authenticated=True,
        admin=True,
        method="launch_token",
        user_id=(os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID") or "local-admin").strip(),
        email=(os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL") or "").strip(),
    )


def _is_loopback_request(request: Request) -> bool:
    host = (request.client.host if request.client else "").strip().lower()
    return host == "localhost" or host == "::1" or host.startswith("127.")


def _query_local_admin_users() -> list[dict[str, str]]:
    port = os.getenv("VIVENTIUM_MONGO_PORT") or os.getenv("MONGO_PORT") or "27117"
    db_name = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DB") or "LibreChatViventium"
    script = """
const rows = db.users.find({
  $or: [
    { role: { $in: ["ADMIN", "admin"] } },
    { roles: { $in: ["ADMIN", "admin"] } },
    { admin: true }
  ]
}).sort({ updatedAt: -1, _id: -1 }).limit(2).toArray();
print(JSON.stringify(rows.map(u => ({
  _id: String(u._id),
  email: u.email || "",
  role: u.role || (Array.isArray(u.roles) ? u.roles.join(",") : "")
}))));
"""
    try:
        completed = subprocess.run(
            ["mongosh", "--quiet", f"mongodb://127.0.0.1:{port}/{db_name}", "--eval", script],
            text=True,
            capture_output=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    text = completed.stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text.splitlines()[-1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    users: list[dict[str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        user_id = str(row.get("_id") or "").strip()
        if not user_id:
            continue
        users.append(
            {
                "_id": user_id,
                "email": str(row.get("email") or "").strip(),
                "role": str(row.get("role") or "").strip(),
            }
        )
    return users


def _scheduling_db_path() -> Path:
    return Path(
        os.getenv("SCHEDULING_DB_PATH")
        or (
            Path.home()
            / "Library"
            / "Application Support"
            / "Viventium"
            / "state"
            / "runtime"
            / "isolated"
            / "scheduling"
            / "schedules.db"
        )
    ).expanduser()


def _admin_with_unique_schedule_ownership(admin_users: list[dict[str, str]]) -> dict[str, str] | None:
    if not admin_users:
        return None
    admin_by_id = {row["_id"]: row for row in admin_users if row.get("_id")}
    if not admin_by_id:
        return None
    db_path = _scheduling_db_path()
    if not db_path.exists():
        return None
    placeholders = ",".join("?" for _ in admin_by_id)
    try:
        with sqlite3.connect(str(db_path)) as conn:
            for table in ("scheduled_prompt_definitions", "scheduled_tasks"):
                try:
                    rows = conn.execute(
                        f"select distinct user_id from {table} where user_id in ({placeholders})",
                        tuple(admin_by_id.keys()),
                    ).fetchall()
                except sqlite3.DatabaseError:
                    continue
                owners = {str(row[0]) for row in rows if row and row[0] in admin_by_id}
                if len(owners) == 1:
                    return admin_by_id[next(iter(owners))]
    except sqlite3.DatabaseError:
        return None
    return None


def _select_local_admin_user(admin_users: list[dict[str, str]]) -> dict[str, str] | None:
    if len(admin_users) == 1:
        return admin_users[0]
    return _admin_with_unique_schedule_ownership(admin_users)


def _local_loopback_admin_auth(request: Request) -> AuthContext | None:
    if (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_LOOPBACK_ADMIN_AUTH") or "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return None
    if not _is_loopback_request(request):
        return None

    env_user_id = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID") or "").strip()
    env_email = (os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL") or "").strip()
    if env_user_id and env_user_id not in {"local-admin", "test-admin"}:
        return AuthContext(
            authenticated=True,
            admin=True,
            method="local_loopback_admin",
            user_id=env_user_id,
            email=env_email,
        )

    admin_user = _select_local_admin_user(_query_local_admin_users())
    if not admin_user:
        return None
    return AuthContext(
        authenticated=True,
        admin=True,
        method="local_loopback_admin",
        user_id=admin_user["_id"],
        email=admin_user.get("email", ""),
    )


def _librechat_origin() -> str:
    return (
        os.getenv("VIVENTIUM_LIBRECHAT_ORIGIN")
        or os.getenv("LIBRECHAT_API_URL")
        or "http://127.0.0.1:3080"
    ).rstrip("/")


def _librechat_admin_auth(request: Request) -> AuthContext | None:
    headers: dict[str, str] = {}
    cookie = request.headers.get("cookie")
    auth = request.headers.get("authorization")
    if cookie:
        headers["Cookie"] = cookie
    if auth:
        headers["Authorization"] = auth
    if not headers:
        return None
    req = urllib.request.Request(f"{_librechat_origin()}/api/admin/verify", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return AuthContext(True, False, method="librechat", reason="not_admin")
        return None
    except OSError:
        return None
    if status != 200:
        return None
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        payload = {}
    user = payload.get("user") if isinstance(payload, dict) and isinstance(payload.get("user"), dict) else {}
    user_id = str(user.get("id") or user.get("_id") or "").strip()
    email = str(user.get("email") or "").strip()
    return AuthContext(True, True, method="librechat_admin", user_id=user_id, email=email)


def get_auth_context(request: Request) -> AuthContext:
    if _env_flag("VIVENTIUM_PROMPT_WORKBENCH_AUTH_DISABLED") and (
        _env_flag("CODEX_CI") or bool(os.getenv("PYTEST_CURRENT_TEST"))
    ):
        return AuthContext(
            authenticated=True,
            admin=True,
            method="disabled_for_tests",
            user_id=(os.getenv("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID") or "test-admin").strip(),
        )
    token_context = _token_auth(request)
    if token_context:
        return token_context
    librechat_context = _librechat_admin_auth(request)
    if librechat_context:
        return librechat_context
    local_admin_context = _local_loopback_admin_auth(request)
    if local_admin_context:
        return local_admin_context
    return AuthContext(False, False, reason="missing_or_invalid_admin_auth")


def require_admin(request: Request) -> AuthContext:
    context = get_auth_context(request)
    if not context.authenticated:
        raise HTTPException(status_code=401, detail="Prompt Workbench admin authentication is required")
    if not context.admin:
        raise HTTPException(status_code=403, detail="Prompt Workbench admin role is required")
    return context
