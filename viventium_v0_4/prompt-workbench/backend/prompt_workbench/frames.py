from __future__ import annotations

from typing import Any

from .paths import REPO_ROOT

from scripts.viventium.prompt_observability_dashboard import (
    _default_logs_root,
    _read_frame_log_summary,
)


def recent_frames(limit: int = 80) -> list[dict[str, Any]]:
    return _read_frame_log_summary(_default_logs_root(), limit=limit, include_private_details=False)
