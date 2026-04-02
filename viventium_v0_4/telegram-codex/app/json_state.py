from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable


class JsonStateFile:
    def __init__(self, path: Path, default_factory: Callable[[], dict[str, Any]]) -> None:
        self.path = path
        self.default_factory = default_factory
        self._lock = threading.Lock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def write(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._write_unlocked(data)

    def update(self, updater: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            data = self._read_unlocked()
            result = updater(data)
            self._write_unlocked(data)
            return result

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            data = self.default_factory()
            self._write_unlocked(data)
            return data
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = self.default_factory()
            self._write_unlocked(data)
            return data

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)

