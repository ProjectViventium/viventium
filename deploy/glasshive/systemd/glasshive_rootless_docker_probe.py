#!/usr/bin/env python3
"""Fail startup unless the configured Docker daemon explicitly reports rootless mode."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence


class RootlessDockerError(RuntimeError):
    pass


def verify_rootless_security_options(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise RootlessDockerError("Docker SecurityOptions was not valid JSON") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RootlessDockerError("Docker SecurityOptions was not a string list")
    if not any("rootless" in item.lower() for item in value):
        raise RootlessDockerError("the connected Docker daemon does not advertise rootless mode")
    return value


def probe(
    *,
    docker_host: str | None = None,
    expected_uid: int | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    endpoint = str(docker_host or os.environ.get("DOCKER_HOST") or "").strip()
    uid = os.getuid() if expected_uid is None else int(expected_uid)
    if endpoint != f"unix:///run/user/{uid}/docker.sock":
        raise RootlessDockerError("DOCKER_HOST must name the runtime user's rootless socket")
    result = runner(
        ["/usr/bin/docker", "info", "--format", "{{json .SecurityOptions}}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
        env={**os.environ, "DOCKER_HOST": endpoint},
    )
    if result.returncode != 0:
        raise RootlessDockerError("the rootless Docker daemon is unavailable")
    return verify_rootless_security_options(result.stdout)


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        probe()
    except (OSError, subprocess.SubprocessError, RootlessDockerError) as exc:
        print(f"glasshive rootless Docker probe failed: {exc}", file=sys.stderr)
        return 1
    print("glasshive rootless Docker probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
