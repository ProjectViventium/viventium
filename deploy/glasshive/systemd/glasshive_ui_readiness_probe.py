#!/usr/bin/env python3
"""Hold UI startup until nested runtime health and the auth registry are readable."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

AUTH_TABLES = frozenset({"auth_principals", "auth_sessions", "auth_oidc_flows"})


class UiReadinessError(RuntimeError):
    pass


def verify_auth_registry(path: Path) -> None:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise UiReadinessError("authentication registry is missing or unsafe")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        connection.execute("PRAGMA query_only=ON")
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()
    if not AUTH_TABLES.issubset(tables):
        raise UiReadinessError("authentication registry schema is not initialized")


def verify_ui_health(
    url: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    response = opener(url, timeout=3)
    try:
        status = int(getattr(response, "status", 0))
        content = response.read(1024 * 1024)
    finally:
        response.close()
    if status != 200:
        raise UiReadinessError("Glass Drive health did not return 200")
    try:
        body = json.loads(content)
    except ValueError as exc:
        raise UiReadinessError("Glass Drive health was not JSON") from exc
    nested = body.get("runtime") if isinstance(body, dict) else None
    if (
        not isinstance(body, dict)
        or body.get("status") != "ok"
        or not isinstance(nested, dict)
        or nested.get("status") != "ok"
    ):
        raise UiReadinessError("Glass Drive or nested runtime health is not ok")


def wait_until_ready(*, url: str, auth_state: Path, timeout_sec: float) -> None:
    deadline = time.monotonic() + max(1.0, timeout_sec)
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            verify_ui_health(url)
            verify_auth_registry(auth_state)
            return
        except (OSError, sqlite3.Error, UiReadinessError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise UiReadinessError(f"Glass Drive readiness timed out: {last_error}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--auth-state", type=Path, required=True)
    parser.add_argument("--timeout-sec", type=float, default=60)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        wait_until_ready(
            url=arguments.url,
            auth_state=arguments.auth_state,
            timeout_sec=arguments.timeout_sec,
        )
    except UiReadinessError as exc:
        print(f"glasshive UI readiness failed: {exc}", file=sys.stderr)
        return 1
    print("glasshive UI readiness passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
