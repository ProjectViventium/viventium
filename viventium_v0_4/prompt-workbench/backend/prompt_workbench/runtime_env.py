from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


RUNTIME_ENV_PATH = Path.home() / "Library" / "Application Support" / "Viventium" / "runtime" / "runtime.env"
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].strip()
    try:
        parts = shlex.split(text, comments=True, posix=True)
    except ValueError:
        return None
    if not parts or "=" not in parts[0]:
        return None
    key, value = parts[0].split("=", 1)
    key = key.strip()
    if not ENV_KEY_RE.match(key):
        return None
    return key, value


def load_viventium_runtime_env(path: Path | None = None, *, override: bool = False) -> None:
    env_path = path or RUNTIME_ENV_PATH
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        parsed = _parse_env_assignment(line)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value
