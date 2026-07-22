from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "transport_native_candidate.py"


def load_transport():
    spec = importlib.util.spec_from_file_location("native_candidate_transport_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_fixture(root: Path) -> Path:
    candidate = root / "candidate"
    executable = candidate / "payload" / "bin" / "viventium-native-install"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    hidden = candidate / "payload" / "runtime" / "librechat" / "node_modules" / ".package-lock.json"
    hidden.parent.mkdir(parents=True)
    hidden.write_text('{"synthetic":true}\n', encoding="utf-8")
    hidden.chmod(0o644)
    ordinary = candidate / "bootstrap" / "ViventiumBootstrap.app" / "Contents" / "Info.plist"
    ordinary.parent.mkdir(parents=True)
    ordinary.write_text("<plist/>\n", encoding="utf-8")
    ordinary.chmod(0o644)
    for directory in [candidate, *[path for path in candidate.rglob("*") if path.is_dir()]]:
        directory.chmod(0o755)
    return candidate


def candidate_snapshot(candidate: Path) -> list[tuple[str, str, int]]:
    snapshot: list[tuple[str, str, int]] = []
    for path in [candidate, *sorted(candidate.rglob("*"), key=lambda item: item.as_posix())]:
        relative = path.relative_to(candidate).as_posix() or "."
        body = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
        snapshot.append((relative, body, path.stat().st_mode & 0o777))
    return snapshot


def test_exact_transport_round_trip_preserves_hidden_files_modes_and_digest(tmp_path: Path) -> None:
    transport = load_transport()
    candidate = candidate_fixture(tmp_path / "source")
    archive = tmp_path / "transport" / "candidate.tar"
    digest = tmp_path / "transport" / "candidate.tar.sha256"

    transport.pack(candidate, archive, digest)
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert digest.read_text(encoding="utf-8") == f"{expected}\n"

    output = tmp_path / "unpacked"
    extracted = transport.unpack(archive, digest, output)
    assert extracted == output / "candidate"
    assert (extracted / "payload/runtime/librechat/node_modules/.package-lock.json").is_file()
    assert (extracted / "payload/bin/viventium-native-install").stat().st_mode & 0o777 == 0o755
    assert (extracted / "bootstrap/ViventiumBootstrap.app/Contents/Info.plist").stat().st_mode & 0o777 == 0o644


def test_transport_archive_is_reproducible_across_source_mtimes(tmp_path: Path) -> None:
    transport = load_transport()
    first = candidate_fixture(tmp_path / "first")
    second = candidate_fixture(tmp_path / "second")
    for index, path in enumerate([second, *sorted(second.rglob("*"), key=lambda item: item.as_posix())]):
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index), follow_symlinks=False)

    first_archive = tmp_path / "first.tar"
    second_archive = tmp_path / "second.tar"
    transport.pack(first, first_archive, tmp_path / "first.sha256")
    transport.pack(second, second_archive, tmp_path / "second.sha256")

    assert hashlib.sha256(first_archive.read_bytes()).digest() == hashlib.sha256(second_archive.read_bytes()).digest()


def test_pack_rejects_symlinks_and_hardlinks(tmp_path: Path) -> None:
    transport = load_transport()
    candidate = candidate_fixture(tmp_path / "symlink")
    (candidate / "payload" / "unsafe-link").symlink_to("bin/viventium-native-install")
    with pytest.raises(transport.TransportError, match="symlink"):
        transport.pack(candidate, tmp_path / "symlink.tar", tmp_path / "symlink.sha256")

    candidate = candidate_fixture(tmp_path / "hardlink")
    source = candidate / "payload" / "bin" / "viventium-native-install"
    os.link(source, candidate / "payload" / "bin" / "second-name")
    with pytest.raises(transport.TransportError, match="hard link"):
        transport.pack(candidate, tmp_path / "hardlink.tar", tmp_path / "hardlink.sha256")


def test_transport_rejects_symlink_roots_and_output_targets(tmp_path: Path) -> None:
    transport = load_transport()
    candidate = candidate_fixture(tmp_path / "source")
    candidate_link = tmp_path / "candidate-link"
    candidate_link.symlink_to(candidate, target_is_directory=True)
    with pytest.raises(transport.TransportError, match="candidate root.*symlink"):
        transport.pack(candidate_link, tmp_path / "root-link.tar", tmp_path / "root-link.sha256")

    outside = tmp_path / "outside"
    outside.write_text("untouched\n", encoding="utf-8")
    archive_link = tmp_path / "archive-link.tar"
    archive_link.symlink_to(outside)
    with pytest.raises(transport.TransportError, match="archive output.*already exists"):
        transport.pack(candidate, archive_link, tmp_path / "archive-link.sha256")
    assert outside.read_text(encoding="utf-8") == "untouched\n"

    archive = tmp_path / "safe.tar"
    digest = tmp_path / "safe.sha256"
    transport.pack(candidate, archive, digest)
    output_target = tmp_path / "outside-output"
    output_target.mkdir()
    output_link = tmp_path / "output-link"
    output_link.symlink_to(output_target, target_is_directory=True)
    with pytest.raises(transport.TransportError, match="extraction directory.*symlink"):
        transport.unpack(archive, digest, output_link)
    assert list(output_target.iterdir()) == []

    outside_parent = tmp_path / "outside-parent"
    outside_parent.mkdir()
    ancestor_link = tmp_path / "ancestor-link"
    ancestor_link.symlink_to(outside_parent, target_is_directory=True)
    with pytest.raises(transport.TransportError, match="ancestor.*symlink"):
        transport.pack(
            candidate,
            ancestor_link / "new" / "candidate.tar",
            tmp_path / "ancestor.sha256",
        )
    assert not (outside_parent / "new").exists()
    with pytest.raises(transport.TransportError, match="ancestor.*symlink"):
        transport.unpack(archive, digest, ancestor_link / "extract" / "root")
    assert not (outside_parent / "extract").exists()


def test_pack_rejects_candidate_outputs_without_mutating_candidate(tmp_path: Path) -> None:
    transport = load_transport()
    candidate = candidate_fixture(tmp_path / "source")
    before = candidate_snapshot(candidate)

    with pytest.raises(transport.TransportError, match="outside the candidate root"):
        transport.pack(
            candidate,
            candidate / "new" / "candidate.tar",
            tmp_path / "candidate.sha256",
        )
    assert candidate_snapshot(candidate) == before
    assert not (candidate / "new").exists()

    with pytest.raises(transport.TransportError, match="outside the candidate root"):
        transport.pack(
            candidate,
            tmp_path / "candidate.tar",
            candidate / "new" / "candidate.sha256",
        )
    assert candidate_snapshot(candidate) == before
    assert not (candidate / "new").exists()


def test_macos_system_var_alias_is_canonicalized_without_permitting_other_symlinks() -> None:
    if os.uname().sysname != "Darwin" or not Path("/var").is_symlink():
        pytest.skip("macOS /var alias regression")
    transport = load_transport()

    canonical = transport.lexical(Path("/var/folders"))

    assert canonical == Path("/private/var/folders")


def test_unpack_rejects_digest_mismatch_traversal_links_and_case_collisions(tmp_path: Path) -> None:
    transport = load_transport()

    def archive_with(*members: tuple[str, bytes, int, bytes | None]) -> tuple[Path, Path]:
        archive = tmp_path / f"unsafe-{len(list(tmp_path.glob('unsafe-*.tar')))}.tar"
        with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as handle:
            for name, body, type_code, linkname in members:
                info = tarfile.TarInfo(name)
                info.type = type_code
                info.mode = 0o755 if type_code == tarfile.DIRTYPE else 0o644
                info.size = len(body) if type_code == tarfile.REGTYPE else 0
                if linkname is not None:
                    info.linkname = linkname.decode("utf-8")
                handle.addfile(info, io.BytesIO(body) if body else None)
        digest = archive.with_suffix(".sha256")
        digest.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}\n", encoding="utf-8")
        return archive, digest

    safe_archive, safe_digest = archive_with(
        ("candidate", b"", tarfile.DIRTYPE, None),
        ("candidate/file", b"ok", tarfile.REGTYPE, None),
    )
    safe_digest.write_text("0" * 64 + "\n", encoding="utf-8")
    with pytest.raises(transport.TransportError, match="digest"):
        transport.unpack(safe_archive, safe_digest, tmp_path / "digest-output")

    traversal, traversal_digest = archive_with(("candidate/../escape", b"bad", tarfile.REGTYPE, None))
    with pytest.raises(transport.TransportError, match="unsafe member path"):
        transport.unpack(traversal, traversal_digest, tmp_path / "traversal-output")

    link, link_digest = archive_with(("candidate/link", b"", tarfile.SYMTYPE, b"target"))
    with pytest.raises(transport.TransportError, match="non-regular"):
        transport.unpack(link, link_digest, tmp_path / "link-output")

    collision, collision_digest = archive_with(
        ("candidate", b"", tarfile.DIRTYPE, None),
        ("candidate/File", b"one", tarfile.REGTYPE, None),
        ("candidate/file", b"two", tarfile.REGTYPE, None),
    )
    with pytest.raises(transport.TransportError, match="case-colliding"):
        transport.unpack(collision, collision_digest, tmp_path / "collision-output")
