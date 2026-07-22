# VIVENTIUM START
# Purpose: Persist VM runtime mappings for openclaw-bridge across restarts.
#
# Stores lightweight VM metadata keyed by (user_id, vm_id).
# This file is runtime-owned state and intentionally simple JSON.
# VIVENTIUM END

from __future__ import annotations

import json
import logging
import os
import secrets
import stat
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VMRegistryRecord:
    user_id: str
    vm_id: str
    runtime: str
    state: str = "unknown"
    sandbox_id: Optional[str] = None
    gateway_url: str = ""
    gateway_token: str = ""
    desktop_url: str = ""
    desktop_auth_key: str = ""
    port: Optional[int] = None
    pid: Optional[int] = None
    state_dir: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def key(self) -> tuple[str, str]:
        return (self.user_id, self.vm_id)


class VMRegistry:
    """Small JSON-backed registry for VM records."""

    def __init__(self, path: Path):
        self.path = path
        self._ensure_private_parent()
        self._validate_registry_path()

    def _ensure_private_parent(self) -> None:
        parent = self.path.parent
        try:
            info = parent.lstat()
        except FileNotFoundError:
            parent.mkdir(mode=0o700, parents=True, exist_ok=False)
            info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeError(f"Refusing unsafe registry directory: {parent}")
        if info.st_uid != os.getuid():
            raise RuntimeError(f"Refusing registry directory owned by another user: {parent}")
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(parent, 0o700, follow_symlinks=False)

    def _validate_registry_path(self) -> None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise RuntimeError(f"Refusing unsafe registry file: {self.path}")
        if info.st_uid != os.getuid():
            raise RuntimeError(f"Refusing registry file owned by another user: {self.path}")
        if stat.S_IMODE(info.st_mode) & 0o077:
            os.chmod(self.path, 0o600, follow_symlinks=False)

    def _read(self) -> Dict:
        self._validate_registry_path()
        if not self.path.exists():
            return {"version": 1, "records": []}
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags)
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise RuntimeError(f"Refusing unsafe registry file: {self.path}")
                payload = json.load(handle)
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            logger.warning("Failed to parse VM registry at %s: %s", self.path, exc)
            return {"version": 1, "records": []}
        if not isinstance(payload, dict):
            return {"version": 1, "records": []}
        payload.setdefault("version", 1)
        payload.setdefault("records", [])
        return payload

    def _write(self, payload: Dict) -> None:
        self._ensure_private_parent()
        self._validate_registry_path()
        tmp = self.path.parent / f".{self.path.name}.{secrets.token_hex(8)}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600, follow_symlinks=False)
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def list_records(self, user_id: Optional[str] = None) -> List[VMRegistryRecord]:
        payload = self._read()
        out: List[VMRegistryRecord] = []
        for item in payload.get("records", []):
            if not isinstance(item, dict):
                continue
            try:
                rec = VMRegistryRecord(**item)
            except TypeError:
                continue
            if user_id and rec.user_id != user_id:
                continue
            out.append(rec)
        out.sort(key=lambda r: (r.user_id, r.vm_id))
        return out

    def get(self, user_id: str, vm_id: str) -> Optional[VMRegistryRecord]:
        for rec in self.list_records(user_id=user_id):
            if rec.vm_id == vm_id:
                return rec
        return None

    def upsert(self, record: VMRegistryRecord) -> None:
        payload = self._read()
        records = payload.get("records", [])
        if not isinstance(records, list):
            records = []
        updated: List[Dict] = []
        replaced = False
        for item in records:
            if not isinstance(item, dict):
                continue
            if item.get("user_id") == record.user_id and item.get("vm_id") == record.vm_id:
                updated.append(asdict(record))
                replaced = True
            else:
                updated.append(item)
        if not replaced:
            updated.append(asdict(record))
        payload["records"] = updated
        self._write(payload)

    def delete(self, user_id: str, vm_id: str) -> None:
        payload = self._read()
        records = payload.get("records", [])
        if not isinstance(records, list):
            records = []
        payload["records"] = [
            item for item in records
            if not isinstance(item, dict)
            or not (item.get("user_id") == user_id and item.get("vm_id") == vm_id)
        ]
        self._write(payload)

    def clear(self) -> None:
        self._write({"version": 1, "records": []})
