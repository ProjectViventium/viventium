#!/usr/bin/env python3
"""Bind the tagged public bootstrap constants to approved Native release policy."""

from __future__ import annotations

import argparse
import base64
import re
import stat
import sys
from pathlib import Path


RELEASE_SIGNING_IDENTITY = "releases@viventium.example"
BOOTSTRAP_SIGNING_IDENTITY = "bootstrap@viventium.example"
# The public shell bootstrap intentionally accepts the smallest portable signing
# contract that is present in supported macOS ssh-keygen builds.
KEY_TYPE_RE = re.compile(r"^ssh-ed25519$")
TEAM_ID_RE = re.compile(r"^[A-Z0-9]{10}$")


class PolicyError(RuntimeError):
    pass


def _read_file(path: Path, *, maximum: int, label: str) -> str:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise PolicyError(f"{label} is unavailable") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size <= 0
        or metadata.st_size > maximum
    ):
        raise PolicyError(f"{label} is invalid")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise PolicyError(f"{label} is invalid") from error


def _constant(source: str, name: str) -> str:
    pattern = re.compile(rf'^{re.escape(name)}="([^"\r\n]*)"$', re.MULTILINE)
    matches = pattern.findall(source)
    if len(matches) != 1:
        raise PolicyError(f"public Native bootstrap constant is invalid: {name}")
    return matches[0]


def _approved_key(allowed_signers: str) -> tuple[str, str]:
    rows = [
        row.split()
        for raw in allowed_signers.splitlines()
        if (row := raw.strip()) and not row.startswith("#")
    ]
    if len(rows) != 1 or len(rows[0]) < 3 or rows[0][0] != RELEASE_SIGNING_IDENTITY:
        raise PolicyError("approved Native allowed-signers policy is invalid")
    key_type, key_blob = rows[0][1:3]
    if not KEY_TYPE_RE.fullmatch(key_type):
        raise PolicyError("approved Native allowed-signers key type is invalid")
    try:
        decoded = base64.b64decode(key_blob, validate=True)
    except ValueError as error:
        raise PolicyError("approved Native allowed-signers key is invalid") from error
    if len(decoded) < 32 or len(decoded) > 2048:
        raise PolicyError("approved Native allowed-signers key is invalid")
    return key_type, key_blob


def verify_policy(
    install_script: Path,
    allowed_signers_path: Path,
    apple_team_id_path: Path,
    *,
    sequence: int,
) -> None:
    if not 1 <= sequence <= 999_999_999:
        raise PolicyError("candidate Native sequence is invalid")
    source = _read_file(
        install_script, maximum=1024 * 1024, label="public install script"
    )
    allowed_signers = _read_file(
        allowed_signers_path,
        maximum=64 * 1024,
        label="approved Native allowed-signers policy",
    )
    apple_team_id = _read_file(
        apple_team_id_path,
        maximum=1024,
        label="approved Apple team policy",
    ).strip()
    key_type, key_blob = _approved_key(allowed_signers)
    expected_signer = f"{BOOTSTRAP_SIGNING_IDENTITY} {key_type} {key_blob}"
    embedded_signer = _constant(source, "NATIVE_BOOTSTRAP_ALLOWED_SIGNER")
    embedded_team_id = _constant(source, "NATIVE_BOOTSTRAP_TEAM_ID")
    embedded_sequence = _constant(source, "NATIVE_BOOTSTRAP_MINIMUM_SEQUENCE")
    if not embedded_signer or not embedded_team_id:
        raise PolicyError("public Native bootstrap trust is not provisioned")
    if embedded_signer != expected_signer:
        raise PolicyError(
            "public Native bootstrap signer does not match approved policy"
        )
    if not TEAM_ID_RE.fullmatch(apple_team_id) or embedded_team_id != apple_team_id:
        raise PolicyError(
            "public Native bootstrap Apple team does not match approved policy"
        )
    if embedded_sequence != str(sequence):
        raise PolicyError(
            "public Native bootstrap sequence floor does not match candidate"
        )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--install-script", type=Path, required=True)
    value.add_argument("--allowed-signers", type=Path, required=True)
    value.add_argument("--apple-team-id", type=Path, required=True)
    value.add_argument("--sequence", type=int, required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        verify_policy(
            args.install_script,
            args.allowed_signers,
            args.apple_team_id,
            sequence=args.sequence,
        )
    except PolicyError as error:
        print(f"Native bootstrap policy: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
