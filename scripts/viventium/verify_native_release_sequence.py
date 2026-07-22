#!/usr/bin/env python3
"""Verify that a Native release advances the complete signed release history."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path


BOOTSTRAP_IDENTITY = "bootstrap@viventium.example"
BOOTSTRAP_NAMESPACE = "viventium-bootstrap"
MANIFEST_NAME = "viventium-native-bootstrap-manifest.json"
SIGNATURE_NAME = f"{MANIFEST_NAME}.sig"
RELEASE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_SIGNATURE_BYTES = 64 * 1024


class SequenceError(RuntimeError):
    pass


def _real_regular_file(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise SequenceError(f"{label} is unsafe") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size <= 0
        or metadata.st_size > maximum
    ):
        raise SequenceError(f"{label} is unsafe")
    try:
        return path.read_bytes()
    except OSError as error:
        raise SequenceError(f"{label} is unsafe") from error


def _require_release_value(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not RELEASE_VALUE_RE.fullmatch(value):
        raise SequenceError(f"{label} is invalid")
    return value


def _require_positive_int(value: object, *, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= 999_999_999
    ):
        raise SequenceError(f"{label} is invalid")
    return value


def _validate_manifest(manifest_bytes: bytes, *, release_tag: str) -> tuple[int, str]:
    try:
        payload = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise SequenceError("published Native bootstrap manifest is invalid") from error
    canonical = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if manifest_bytes != canonical:
        raise SequenceError("published Native bootstrap manifest is not canonical JSON")
    required = {"schema_version", "release_tag", "release_id", "sequence", "artifacts"}
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema_version") != 1
    ):
        raise SequenceError("published Native bootstrap manifest is invalid")
    manifest_tag = _require_release_value(
        payload.get("release_tag"), label="published release tag"
    )
    _require_release_value(payload.get("release_id"), label="published release id")
    sequence = _require_positive_int(
        payload.get("sequence"), label="published release sequence"
    )
    if manifest_tag != release_tag:
        raise SequenceError(
            "published Native manifest tag does not match its GitHub release"
        )
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"arm64", "x86_64"}:
        raise SequenceError("published Native bootstrap manifest is invalid")
    for arch in ("arm64", "x86_64"):
        artifact = artifacts.get(arch)
        if not isinstance(artifact, dict) or set(artifact) != {
            "filename",
            "sha256",
            "size",
            "uncompressed_size",
        }:
            raise SequenceError("published Native bootstrap manifest is invalid")
        if artifact.get("filename") != f"ViventiumBootstrap-{arch}.zip":
            raise SequenceError("published Native bootstrap manifest is invalid")
        if not isinstance(artifact.get("sha256"), str) or not SHA256_RE.fullmatch(
            artifact["sha256"]
        ):
            raise SequenceError("published Native bootstrap manifest is invalid")
        size = artifact.get("size")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or not 1 <= size <= 268435456
        ):
            raise SequenceError("published Native bootstrap manifest is invalid")
        uncompressed_size = artifact.get("uncompressed_size")
        if (
            isinstance(uncompressed_size, bool)
            or not isinstance(uncompressed_size, int)
            or not 1 <= uncompressed_size <= 2147483648
        ):
            raise SequenceError("published Native bootstrap manifest is invalid")
    return sequence, hashlib.sha256(manifest_bytes).hexdigest()


def _verify_signature(
    manifest_bytes: bytes, signature: Path, allowed_signers: Path
) -> None:
    _real_regular_file(
        signature, maximum=MAX_SIGNATURE_BYTES, label="published Native signature"
    )
    _real_regular_file(
        allowed_signers,
        maximum=MAX_SIGNATURE_BYTES,
        label="Native allowed-signers policy",
    )
    completed = subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(allowed_signers),
            "-I",
            BOOTSTRAP_IDENTITY,
            "-n",
            BOOTSTRAP_NAMESPACE,
            "-s",
            str(signature),
        ],
        input=manifest_bytes,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise SequenceError("published Native bootstrap signature is invalid")


def _read_record(entry: Path, allowed_signers: Path) -> tuple[str, int, str]:
    if entry.is_symlink() or not entry.is_dir():
        raise SequenceError("Native release history entry is unsafe")
    record_path = entry / "record.json"
    record_bytes = _real_regular_file(
        record_path, maximum=64 * 1024, label="Native release history record"
    )
    try:
        record = json.loads(record_bytes)
    except json.JSONDecodeError as error:
        raise SequenceError("Native release history record is invalid") from error
    if not isinstance(record, dict) or set(record) != {"release_tag"}:
        raise SequenceError("Native release history record is invalid")
    release_tag = _require_release_value(
        record.get("release_tag"), label="Native release history record"
    )
    manifest_path = entry / MANIFEST_NAME
    manifest_bytes = _real_regular_file(
        manifest_path,
        maximum=MAX_MANIFEST_BYTES,
        label="published Native bootstrap manifest",
    )
    _verify_signature(manifest_bytes, entry / SIGNATURE_NAME, allowed_signers)
    sequence, digest = _validate_manifest(manifest_bytes, release_tag=release_tag)
    return release_tag, sequence, digest


def verify_history(
    history_root: Path,
    allowed_signers: Path,
    *,
    candidate_release_tag: str,
    candidate_sequence: int,
) -> None:
    candidate_release_tag = _require_release_value(
        candidate_release_tag, label="candidate release tag"
    )
    candidate_sequence = _require_positive_int(
        candidate_sequence, label="candidate sequence"
    )
    if history_root.is_symlink() or not history_root.is_dir():
        raise SequenceError("Native release history root is unsafe")
    by_sequence: dict[int, tuple[str, str]] = {}
    seen_tags: set[str] = set()
    for entry in sorted(history_root.iterdir()):
        tag, sequence, digest = _read_record(entry, allowed_signers)
        if tag in seen_tags:
            raise SequenceError(f"duplicate published Native release tag: {tag}")
        seen_tags.add(tag)
        prior = by_sequence.get(sequence)
        if prior is not None:
            raise SequenceError(
                f"duplicate published Native sequence {sequence}: {prior[0]} and {tag}"
            )
        by_sequence[sequence] = (tag, digest)
    if candidate_release_tag in seen_tags:
        raise SequenceError("candidate release tag already has Native release history")
    if not by_sequence:
        if candidate_sequence != 1:
            raise SequenceError("first Native release sequence must be 1")
        return
    for expected_sequence, published_sequence in enumerate(sorted(by_sequence), start=1):
        if published_sequence != expected_sequence:
            raise SequenceError(
                "published Native release history is incomplete; "
                f"missing sequence {expected_sequence}"
            )
    expected = max(by_sequence) + 1
    if candidate_sequence != expected:
        raise SequenceError(
            f"candidate Native release sequence must be exactly {expected}; got {candidate_sequence}"
        )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--history-root", type=Path, required=True)
    value.add_argument("--allowed-signers", type=Path, required=True)
    value.add_argument("--candidate-release-tag", required=True)
    value.add_argument("--candidate-sequence", type=int, required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        verify_history(
            args.history_root,
            args.allowed_signers,
            candidate_release_tag=args.candidate_release_tag,
            candidate_sequence=args.candidate_sequence,
        )
    except SequenceError as error:
        print(f"Native release sequence: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
