#!/usr/bin/env python3
"""Build a deterministic Native payload archive and canonical signed manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import native_payload


ZIP_MIN_EPOCH = 315532800  # 1980-01-01T00:00:00Z, the first ZIP timestamp.
ZIP_MAX_EPOCH = 4354819198  # 2107-12-31T23:59:58Z.


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str
    size: int
    sha256: str
    mode: int


class BuildError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _inventory_payload(payload_root: Path) -> list[SourceFile]:
    if payload_root.is_symlink() or not payload_root.is_dir():
        raise BuildError("payload root must be a real directory")

    files: list[SourceFile] = []
    for current_root, dirnames, filenames in os.walk(
        payload_root, topdown=True, followlinks=False
    ):
        root = Path(current_root)
        for name in dirnames:
            directory = root / name
            if directory.is_symlink() or not directory.is_dir():
                raise BuildError("payload contains a symlink or unsafe directory")
        for name in filenames:
            path = root / name
            metadata = path.lstat()
            relative_path = path.relative_to(payload_root).as_posix()
            native_payload._safe_relative_path(relative_path, label="payload")
            if stat.S_ISLNK(metadata.st_mode):
                raise BuildError("payload contains a symlink")
            if not stat.S_ISREG(metadata.st_mode):
                raise BuildError("payload contains a non-regular file")
            if metadata.st_nlink != 1:
                raise BuildError("payload contains a hard-linked file")
            mode = stat.S_IMODE(metadata.st_mode)
            if mode not in {0o644, 0o755}:
                raise BuildError(
                    f"payload file mode must be 0644 or 0755: {relative_path}"
                )
            files.append(
                SourceFile(
                    path=path,
                    relative_path=relative_path,
                    size=metadata.st_size,
                    sha256=_sha256_file(path),
                    mode=mode,
                )
            )
    if not files:
        raise BuildError("payload must contain at least one file")
    return sorted(files, key=lambda item: item.relative_path)


def _zip_datetime(source_date_epoch: int) -> tuple[int, int, int, int, int, int]:
    if not ZIP_MIN_EPOCH <= source_date_epoch <= ZIP_MAX_EPOCH:
        raise BuildError("source date epoch is outside the ZIP timestamp range")
    value = time.gmtime(source_date_epoch - (source_date_epoch % 2))
    return (value.tm_year, value.tm_mon, value.tm_mday, value.tm_hour, value.tm_min, value.tm_sec)


def _write_deterministic_archive(
    destination: Path,
    files: list[SourceFile],
    source_date_epoch: int,
) -> None:
    timestamp = _zip_datetime(source_date_epoch)
    # Deflate avoids turning the dependency-rich runtime into an avoidable multi-GB
    # novice download. A fixed implementation, level, ordering, timestamp, and
    # metadata keep archives reproducible for the pinned build Python.
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for source_file in files:
            info = zipfile.ZipInfo(source_file.relative_path, date_time=timestamp)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | source_file.mode) << 16
            digest = hashlib.sha256()
            copied = 0
            with source_file.path.open("rb") as source, archive.open(info, "w") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    copied += len(chunk)
            if copied != source_file.size or digest.hexdigest() != source_file.sha256:
                raise BuildError("payload source changed while the archive was being built")


def _sign_manifest(manifest_path: Path, signing_key: Path) -> Path:
    if signing_key.is_symlink() or not signing_key.is_file():
        raise BuildError("manifest signing key is unavailable or unsafe")
    completed = subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(signing_key),
            "-n",
            native_payload.SIGNING_NAMESPACE,
            str(manifest_path),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    signature_path = Path(f"{manifest_path}.sig")
    if completed.returncode != 0 or not signature_path.is_file():
        raise BuildError("manifest signing failed")
    return signature_path


def build_payload(
    *,
    payload_root: Path,
    output_dir: Path,
    release_id: str,
    sequence: int,
    channel: str,
    arch: str,
    node_version: str,
    minimum_macos: str,
    data_schema_minimum: int,
    data_schema_maximum: int,
    source_date_epoch: int,
    manifest_signing_key: Path | None,
) -> dict[str, object]:
    payload_root = Path(payload_root)
    if payload_root.is_symlink():
        raise BuildError("payload root must be a real directory")
    payload_root = payload_root.resolve()
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise BuildError("output directory must not be a symlink")
    output_dir = output_dir.resolve()
    if output_dir == payload_root or output_dir.is_relative_to(payload_root):
        raise BuildError("output directory must be outside the payload root")
    if channel not in {"local-qa", "stable"}:
        raise BuildError("channel must be local-qa or stable")
    if channel == "stable" and manifest_signing_key is None:
        raise BuildError("stable channel requires --manifest-signing-key")
    if channel == "local-qa" and manifest_signing_key is not None:
        raise BuildError("local-qa channel must not use a production manifest signing key")
    if output_dir.exists():
        raise BuildError("output directory already exists; refusing to replace an artifact set")

    files = _inventory_payload(payload_root)
    artifact_name = f"viventium-native-{release_id}-{arch}.zip"
    manifest_name = f"{artifact_name}.manifest.json"
    signature_name = f"{manifest_name}.sig"
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".native-payload-build-", dir=output_dir.parent
    ) as temporary_raw:
        temporary = Path(temporary_raw)
        publish_dir = temporary / "artifacts"
        publish_dir.mkdir(mode=0o755)
        artifact_path = publish_dir / artifact_name
        manifest_path = publish_dir / manifest_name
        _write_deterministic_archive(artifact_path, files, source_date_epoch)
        _fsync_file(artifact_path)
        manifest = {
            "schema_version": native_payload.MANIFEST_SCHEMA_VERSION,
            "release_id": release_id,
            "sequence": sequence,
            "channel": channel,
            "local_qa": channel == "local-qa",
            "platform": {
                "os": "macos",
                "arch": arch,
                "minimum_version": minimum_macos,
            },
            "artifact": {
                "filename": artifact_name,
                "sha256": _sha256_file(artifact_path),
                "size": artifact_path.stat().st_size,
                "uncompressed_size": sum(item.size for item in files),
            },
            "runtime": {
                "node": node_version,
                "data_schema": {
                    "minimum": data_schema_minimum,
                    "maximum": data_schema_maximum,
                },
            },
            "files": [
                {
                    "path": item.relative_path,
                    "sha256": item.sha256,
                    "size": item.size,
                    "mode": item.mode,
                }
                for item in files
            ],
        }
        native_payload._validate_manifest(manifest)
        manifest_path.write_bytes(native_payload.canonical_manifest_bytes(manifest))
        _fsync_file(manifest_path)
        signature_path = None
        if manifest_signing_key is not None:
            signature_path = _sign_manifest(manifest_path, manifest_signing_key)
            _fsync_file(signature_path)

        _fsync_directory(publish_dir)
        os.replace(publish_dir, output_dir)
        _fsync_directory(output_dir.parent)

    return {
        "artifact": artifact_name,
        "artifactSha256": manifest["artifact"]["sha256"],
        "channel": channel,
        "manifest": manifest_name,
        "manifestSha256": hashlib.sha256(
            native_payload.canonical_manifest_bytes(manifest)
        ).hexdigest(),
        "signature": signature_name if manifest_signing_key is not None else None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--channel", choices=("local-qa", "stable"), required=True)
    parser.add_argument("--arch", choices=("arm64", "x86_64"), required=True)
    parser.add_argument("--node-version", required=True)
    parser.add_argument("--minimum-macos", required=True)
    parser.add_argument("--data-schema-minimum", type=int, required=True)
    parser.add_argument("--data-schema-maximum", type=int, required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    parser.add_argument("--manifest-signing-key", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = build_payload(
            payload_root=args.payload_root,
            output_dir=args.output_dir,
            release_id=args.release_id,
            sequence=args.sequence,
            channel=args.channel,
            arch=args.arch,
            node_version=args.node_version,
            minimum_macos=args.minimum_macos,
            data_schema_minimum=args.data_schema_minimum,
            data_schema_maximum=args.data_schema_maximum,
            source_date_epoch=args.source_date_epoch,
            manifest_signing_key=args.manifest_signing_key,
        )
    except (BuildError, native_payload.PayloadError, ValueError) as error:
        print(f"Native payload build failed: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("Native payload build failed; inspect the sanitized build log.", file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
