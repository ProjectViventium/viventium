from __future__ import annotations

import logging
import os
import stat
import subprocess
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

_CASE_ID_ENV = "VIVENTIUM_LOCAL_QA_CASE_ID"
_SESSION_REF_ENV = "VIVENTIUM_LOCAL_QA_SESSION_REF"
_FAILURE_MARKER = "local_qa_service_ack_failed"
_HELPER_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "viventium"
    / "local_qa_service_ack.py"
)


def _resolve_helper() -> Path:
    configured = _HELPER_PATH
    if not configured.is_absolute():
        raise ValueError("invalid helper")

    configured_info = configured.lstat()
    if not stat.S_ISREG(configured_info.st_mode):
        raise ValueError("invalid helper")

    helper = configured.resolve(strict=True)
    helper_info = helper.stat()
    permissions = stat.S_IMODE(helper_info.st_mode)
    if (
        not stat.S_ISREG(helper_info.st_mode)
        or helper_info.st_uid != os.geteuid()
        or not permissions & stat.S_IXUSR
        or permissions & (stat.S_IWGRP | stat.S_IWOTH)
        or helper_info.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
    ):
        raise ValueError("invalid helper")
    return helper


def acknowledge_local_qa_service(service_id: str) -> bool:
    case_id = str(os.environ.get(_CASE_ID_ENV, "") or "").strip()
    session_ref = str(os.environ.get(_SESSION_REF_ENV, "") or "").strip()
    if not case_id or not session_ref:
        return False

    try:
        helper = _resolve_helper()
        completed = subprocess.run(
            [
                str(helper),
                "acknowledge",
                "--service-id",
                service_id,
                "--pid",
                str(os.getpid()),
                "--executable",
                sys.executable,
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            close_fds=True,
        )
        if completed.returncode != 0:
            raise RuntimeError("helper rejected acknowledgement")
    except Exception:
        logger.warning(_FAILURE_MARKER)
        return False
    return True
