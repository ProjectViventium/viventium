#!/usr/bin/env python3
"""Reject secret-bearing paths or high-confidence secrets from Git's staged index."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from public_life_boundary import (
    PUBLIC_LIFE_FILES, PrivateFingerprintError, PrivateIdentityFingerprints,
    personal_workspace_path, personal_workspace_reference,
)


FORBIDDEN_DIRECTORY_NAMES = {
    "service-env",
    "successor-bridge",
    "upgrade-backups",
}
FORBIDDEN_ROOT_DIRECTORIES = {"claude", "codex"}
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
        ["git", "--no-replace-objects", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=text,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
    )
    if completed.returncode != 0:
        raise StagedSafetyError("Git staged-state inspection failed")
    return completed.stdout


def staged_paths(repo: Path) -> list[str]:
    raw = git(
        repo,
        "diff",
        "--cached",
        "--name-status",
        "--find-renames",
        "--diff-filter=ACMRT",
        "-z",
    )
    assert isinstance(raw, bytes)
    fields = iter(raw.split(b"\0"))
    paths = []
    for status in fields:
        if not status:
            continue
        path = next(fields).decode("utf-8", "strict")
        if status.startswith((b"R", b"C")):
            if personal_workspace_path(path):
                raise StagedSafetyError("Personal workspace data cannot enter the public index")
            path = next(fields).decode("utf-8", "strict")
        paths.append(path)
    return paths


def check_personal_blob(blob: bytes, *, symlink: bool, location: str) -> None:
    if personal_workspace_reference(blob) or (
        symlink and personal_workspace_path(blob.decode("utf-8", "strict"))
    ):
        raise StagedSafetyError(f"Personal workspace metadata appears in {location}")


def forbidden_path_kind(raw_path: str) -> str | None:
    """Use one private-path policy for the index and every outgoing revision."""
    path = PurePosixPath(raw_path)
    if len(path.parts) > 1 and path.parts[0] in FORBIDDEN_ROOT_DIRECTORIES:
        return "private session"
    if any(".private." in part.lower() or "-private." in part.lower() for part in path.parts):
        return "private evidence"
    if (
        path.name in FORBIDDEN_FILE_NAMES
        or any(part in FORBIDDEN_DIRECTORY_NAMES for part in path.parts)
        or any(
            part.startswith(prefix)
            for part in path.parts
            for prefix in FORBIDDEN_DIRECTORY_PREFIXES
        )
    ):
        return "environment"
    return None


def has_private_or_secret_content(blob: bytes) -> bool:
    return any(pattern.search(blob) for pattern in PRIVATE_OR_SECRET_PATTERNS)


def verify(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise StagedSafetyError("Staged public-safety target is not a Git checkout")
    paths = staged_paths(repo)
    fingerprints = PrivateIdentityFingerprints()
    index = git(repo, "ls-files", "--stage", "-z")
    special_modes = {
        record.split(b"\t", 1)[1].decode("utf-8", "strict"): record.split(b" ", 1)[0]
        for record in index.split(b"\0")
        if record.startswith((b"120000 ", b"160000 "))
    }
    findings: list[str] = []
    for raw_path in paths:
        if personal_workspace_path(raw_path) or (raw_path in PUBLIC_LIFE_FILES and raw_path in special_modes):
            raise StagedSafetyError("Personal workspace data cannot enter the public index")
        path = PurePosixPath(raw_path)
        forbidden_kind = forbidden_path_kind(raw_path)
        if forbidden_kind:
            findings.append(f"forbidden staged {forbidden_kind} path: {path.as_posix()}")
            continue
        blob = git(repo, "show", f":{raw_path}")
        assert isinstance(blob, bytes)
        check_personal_blob(blob, symlink=special_modes.get(raw_path) == b"120000", location="the public index")
        if fingerprints.matches_blob(blob):
            raise StagedSafetyError("Private identity bytes cannot enter the public index")
        if has_private_or_secret_content(blob):
            findings.append(f"private or secret content in staged file: {path.as_posix()}")
    if findings:
        raise StagedSafetyError("\n".join(sorted(findings)))
    return {"status": "pass", "staged_files": len(paths)}


def verify_outgoing(repo: Path, ref: str, target_ref: str | None = None) -> dict[str, object]:
    """Inspect introductions in every outgoing commit, including later deletions."""
    tip = git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}", text=True).strip()
    for name in (ref, target_ref or ref):
        if personal_workspace_path(name) or personal_workspace_reference(name.encode("utf-8")):
            raise StagedSafetyError("Personal workspace metadata cannot enter a public ref")
        if has_private_or_secret_content(name.encode("utf-8")):
            raise StagedSafetyError("Private or secret content cannot enter a public ref")
    fetched = git(repo, "for-each-ref", "--format=%(objectname) %(symref)", "refs/remotes/origin/", text=True)
    trusted = [line.partition(" ")[0] for line in fetched.splitlines() if not line.partition(" ")[2]]
    history = (tip, "--not", *trusted)
    raw = git(repo, "log", "--format=", "--raw", "--no-abbrev", "--no-renames",
              "--diff-filter=ACMT", "-m", "--root", "-r", "-z", *history)
    objects: set[tuple[str, bool]] = set()
    entries = iter(raw.split(b"\0"))
    for header in entries:
        header = header.lstrip(b"\n")
        if not header:
            continue
        fields = header.split()
        path = next(entries, b"")
        if len(fields) != 5 or not header.startswith(b":") or not path:
            raise StagedSafetyError("Could not inspect outgoing commit changes")
        name = path.decode("utf-8", "strict")
        symlink = fields[1] == b"120000"
        if personal_workspace_path(name) or (name in PUBLIC_LIFE_FILES and fields[1] not in {b"100644", b"100755"}):
            raise StagedSafetyError("Personal workspace data appears in outgoing history")
        if forbidden_path_kind(name):
            raise StagedSafetyError("Forbidden private path appears in outgoing history")
        if fields[1] != b"160000":
            objects.add((fields[3].decode("ascii"), symlink))
    metadata = git(repo, "log", "--format=raw", *history)
    if personal_workspace_reference(metadata):
        raise StagedSafetyError("Personal workspace metadata appears in outgoing history")
    if has_private_or_secret_content(metadata):
        raise StagedSafetyError("Private or secret metadata appears in outgoing history")
    fingerprints = PrivateIdentityFingerprints()
    for object_id, symlink in objects:
        blob = git(repo, "cat-file", "blob", object_id)
        check_personal_blob(blob, symlink=symlink, location="outgoing history")
        if fingerprints.matches_blob(blob):
            raise StagedSafetyError("Private identity bytes appear in outgoing history")
        if has_private_or_secret_content(blob):
            raise StagedSafetyError("Private or secret content appears in outgoing history")
    return {"status": "pass", "outgoing_blobs": len(objects)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--outgoing-ref")
    parser.add_argument("--target-ref")
    parser.add_argument("--message-stdin", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.message_stdin:
            message = sys.stdin.buffer.read()
            if personal_workspace_reference(message) or has_private_or_secret_content(message):
                raise StagedSafetyError("Private content cannot enter a commit message")
        result = (verify_outgoing(args.repo, args.outgoing_ref, args.target_ref)
                  if args.outgoing_ref else verify(args.repo))
    except (OSError, UnicodeDecodeError, PrivateFingerprintError, StagedSafetyError) as error:
        print(f"Staged public-safety verification failed:\n{error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
