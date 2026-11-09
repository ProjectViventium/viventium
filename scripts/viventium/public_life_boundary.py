"""Shared, redacted checks for personal workspace data at publication boundaries."""

from __future__ import annotations

import re
import hashlib
import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote_to_bytes

from life_bootstrap import DEFAULT_STATE_FILE, recorded_life_dir


# These are shipped code and test definitions, not user data directories.
PUBLIC_LIFE_FILES = frozenset({"qa/life/cases.yaml", "packages/api/src/life/setup.ts"})
PACKAGED_LIFE_FILES = frozenset(
    "payload/runtime/librechat/" + root + "/" + path
    for root in ("packages/api", "node_modules/@librechat/api")
    for path in ("src/life/setup.ts", "dist/types/life/setup.d.ts", "dist/types/life/setup.d.ts.map")
)
PRIVATE_LIFE_REFERENCE = re.compile(
    rb"(?:/(?:Users|home)/[^/\x00\s\"']+/(?:[^/\x00\r\n\"']+/)*life(?=/|[\x00\s\"']|$)"
    rb"|~/[^\x00\r\n\"']*?/life/[^\x00\s\"']+)",
    re.IGNORECASE,
)


def personal_workspace_path(path: str, public_files: frozenset[str] = PUBLIC_LIFE_FILES) -> bool:
    relative = PurePosixPath(path.replace("\\", "/"))
    return (
        relative.as_posix() not in public_files
        and any(part.casefold() == "life" for part in relative.parts)
    )


def personal_workspace_reference(data: bytes) -> bool:
    normalized = re.sub(rb"/{2,}", b"/", unquote_to_bytes(data).replace(b"\\", b"/"))
    return PRIVATE_LIFE_REFERENCE.search(normalized) is not None


class PrivateFingerprintError(RuntimeError):
    pass


class PrivateIdentityFingerprints:
    """Compare publication bytes to local private identity files without emitting their data."""

    def __init__(self) -> None:
        life = Path(os.environ.get("VIVENTIUM_LIFE_DIR") or recorded_life_dir(DEFAULT_STATE_FILE.parent))
        root = life.expanduser() / "Self/Identity"
        self._files: dict[int, list[Path]] = {}
        self._digests: dict[int, set[bytes]] = {}
        if not root.exists():
            return
        if root.is_symlink():
            raise PrivateFingerprintError("Private identity fingerprint source is not a real folder")
        try:
            for folder, _, filenames in os.walk(root, onerror=self._raise_walk_error):
                for name in filenames:
                    path = Path(folder) / name
                    if not path.is_symlink() and path.is_file() and (size := path.stat().st_size):
                        self._files.setdefault(size, []).append(path)
        except OSError:
            raise PrivateFingerprintError("Private identity fingerprints could not be read") from None

    def _for_size(self, size: int) -> set[bytes]:
        if size not in self._digests:
            try:
                self._digests[size] = {self._digest(path) for path in self._files.get(size, ())}
            except OSError:
                raise PrivateFingerprintError("Private identity fingerprints could not be read") from None
        return self._digests[size]

    @staticmethod
    def _raise_walk_error(error: OSError) -> None:
        raise error

    @staticmethod
    def _digest(path: Path) -> bytes:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").digest()

    def matches_blob(self, blob: bytes) -> bool:
        if blob.startswith((b"version https://git-lfs.github.com/spec/v1",
                            b"version https://hawser.github.com/spec/v1")):
            pointer = re.search(
                rb"^oid sha256:([a-f0-9]{64})\r?\nsize ([0-9]{1,20})\r?$", blob, re.MULTILINE,
            )
            if pointer:
                return bytes.fromhex(pointer[1].decode("ascii")) in self._for_size(int(pointer[2]))
        digests = self._for_size(len(blob))
        return bool(digests and hashlib.sha256(blob).digest() in digests)

    def matches_file(self, path: Path, size: int) -> bool:
        digests = self._for_size(size)
        return bool(digests and self._digest(path) in digests)
