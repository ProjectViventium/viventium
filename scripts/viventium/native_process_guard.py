#!/usr/bin/env python3
"""Own one Native child process and keep an auditable process-group marker."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess


child: subprocess.Popen[bytes] | None = None


def forward(signum: int, _frame: object) -> None:
    if child is not None and child.poll() is None:
        try:
            child.send_signal(signum)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or len(args.token) != 64:
        return 2
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, forward)
    global child
    child = subprocess.Popen(command, env=os.environ, close_fds=True)
    try:
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
