# VIVENTIUM START
# Purpose: Persist VM runtime mappings for openclaw-bridge across restarts.
#
# Stores lightweight VM metadata keyed by (user_id, vm_id).
# This file is runtime-owned state and intentionally simple JSON.
# VIVENTIUM END

from __future__ import annotations

import json
import logging
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
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> Dict:
        if not self.path.exists():
            return {"version": 1, "records": []}
        try:
            payload = json.loads(self.path.read_text())
        except Exception as exc:
            logger.warning("Failed to parse VM registry at %s: %s", self.path, exc)
            return {"version": 1, "records": []}
        if not isinstance(payload, dict):
            return {"version": 1, "records": []}
        payload.setdefault("version", 1)
        payload.setdefault("records", [])
        return payload

    def _write(self, payload: Dict) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self.path)

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
