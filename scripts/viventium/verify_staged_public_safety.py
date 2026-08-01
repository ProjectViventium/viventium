#!/usr/bin/env python3
"""Reject secret-bearing paths or high-confidence secrets from Git's staged index."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


FORBIDDEN_DIRECTORY_NAMES = {
    "service-env",
    "successor-bridge",
    "upgrade-backups",
}
FORBIDDEN_DIRECTORY_PREFIXES = (
    "dev-runtime-activation.",
    ".env.viventium-",
)
FORBIDDEN_FILE_NAMES = {
    ".env",
    ".env.local",
    "config.env",
    "librechat.env",
    "librechat.owner.env",
    "owner.env",
    "deleting.env",
    "runtime.env",
    "runtime.local.env",
}
PRIVATE_OR_SECRET_PATTERNS = (
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(rb"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(rb"\b[0-9]{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----"),
    re.compile(
        rb"/Users/(?!(?:example|username|user)(?:/|\\))[A-Za-z0-9._-]+(?:/|\\)"
    ),
    re.compile(
        rb"\b(?!git@github\.com\b)[A-Za-z0-9._%+-]+@"
        rb"(?!(?:example\.(?:com|org|net)|localhost|viventium\.local|"
        rb"users\.noreply\.github\.com)\b)"
        rb"(?!(?:[A-Za-z0-9-]+\.)*(?:example|invalid|test)\b)"
        rb"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rb"https?://[A-Za-z0-9._~-]+:[^@\s/]{8,}@"
        rb"(?!(?:(?:[A-Za-z0-9-]+\.)*(?:example|invalid|test)|"
        rb"localhost|127(?:\.[0-9]{1,3}){3})(?=[:/\s]|$))"
        rb"[A-Za-z0-9.-]+",
        re.IGNORECASE,
    ),
)


class StagedSafetyError(RuntimeError):
    pass


def git(repo: Path, *arguments: str, text: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        raise StagedSafetyError("Git staged-state inspection failed")
    return completed.stdout


def staged_paths(repo: Path) -> list[str]:
    raw = git(
        repo,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=ACMR",
        "-z",
    )
    assert isinstance(raw, bytes)
    return [item.decode("utf-8", "strict") for item in raw.split(b"\0") if item]


def verify(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise StagedSafetyError("Staged public-safety target is not a Git checkout")
    paths = staged_paths(repo)
    findings: list[str] = []
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        if (
            path.name in FORBIDDEN_FILE_NAMES
            or any(part in FORBIDDEN_DIRECTORY_NAMES for part in path.parts)
            or any(
                part.startswith(prefix)
                for part in path.parts
                for prefix in FORBIDDEN_DIRECTORY_PREFIXES
            )
        ):
            findings.append(f"forbidden staged environment path: {path.as_posix()}")
            continue
        blob = git(repo, "show", f":{raw_path}")
        assert isinstance(blob, bytes)
        if any(pattern.search(blob) for pattern in PRIVATE_OR_SECRET_PATTERNS):
            findings.append(f"private or secret content in staged file: {path.as_posix()}")
    if findings:
        raise StagedSafetyError("\n".join(sorted(findings)))
    return {"status": "pass", "staged_files": len(paths)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo)
    except (OSError, UnicodeDecodeError, StagedSafetyError) as error:
        print(f"Staged public-safety verification failed:\n{error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
