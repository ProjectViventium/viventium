from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "stage_native_component.py"


def load_stager():
    spec = importlib.util.spec_from_file_location("native_component_stager_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, body: bytes = b"fixture\n", mode: int = 0o644) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(mode)
    return path


def test_node_staging_keeps_only_runtime_and_license(tmp_path: Path) -> None:
    stager = load_stager()
    source = tmp_path / "node-source"
    write(source / "bin/node", b"node-runtime", 0o755)
    write(source / "bin/npm", b"npm", 0o755)
    write(source / "include/node/node.h")
    write(source / "lib/node_modules/npm/LICENSE")
    write(source / "LICENSE", b"node-license")

    output = tmp_path / "node-output"
    result = stager.stage_component("node", source, output, source_date_epoch=1_700_000_000)

    assert result["component"] == "node"
    assert sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == [
        "LICENSE",
        "bin/node",
    ]
    assert (output / "bin/node").stat().st_mode & 0o777 == 0o755
    assert (output / "LICENSE").stat().st_mode & 0o777 == 0o644


def test_python_staging_excludes_package_manager_development_and_gui_surfaces(tmp_path: Path) -> None:
    stager = load_stager()
    source = tmp_path / "python-source"
    interpreter = write(source / "bin/python3.12", b"python-runtime", 0o755)
    (source / "bin/python3").symlink_to("python3.12")
    write(source / "bin/pip", b"pip", 0o755)
    write(source / "include/python3.12/Python.h")
    write(source / "share/man/man1/python.1")
    write(source / "lib/libpython3.12.dylib", b"libpython", 0o755)
    write(source / "lib/libtcl9.0.dylib", b"tcl", 0o755)
    write(source / "lib/python3.12/LICENSE.txt", b"python-license")
    write(source / "lib/python3.12/os.py")
    write(source / "lib/python3.12/encodings/__init__.py")
    write(source / "lib/python3.12/lib-dynload/_socket.so", b"socket", 0o755)
    write(source / "lib/python3.12/lib-dynload/_tkinter.cpython-312-darwin.so", b"tk", 0o755)
    write(source / "lib/python3.12/site-packages/pip/__init__.py")
    write(source / "lib/python3.12/ensurepip/__init__.py")
    write(source / "lib/python3.12/venv/__init__.py")
    write(source / "lib/python3.12/tkinter/__init__.py")
    write(source / "lib/python3.12/idlelib/__init__.py")
    write(source / "lib/python3.12/lib2to3/__init__.py")
    write(source / "lib/python3.12/test/test_os.py")
    write(source / "lib/python3.12/turtledemo/__init__.py")
    write(source / "lib/python3.12/config-3.12-darwin/Makefile")
    write(source / "lib/python3.12/__pycache__/os.cpython-312.pyc")
    for name in stager.PYTHON_STANDALONE_LICENSE_FILES:
        write(source / "python-build-standalone-licenses" / name, name.encode("utf-8"))

    output = tmp_path / "python-output"
    stager.stage_component("python", source, output, source_date_epoch=1_700_000_000)

    assert (output / "bin/python3").read_bytes() == interpreter.read_bytes()
    assert not (output / "lib/libpython3.12.dylib").exists()
    assert (output / "lib/python3.12/os.py").is_file()
    assert (output / "lib/python3.12/lib-dynload/_socket.so").is_file()
    assert (
        output / "share/licenses/python-build-standalone/LICENSE.openssl-3.txt"
    ).is_file()
    assert (
        output / "share/licenses/python-build-standalone/python-licenses.rst"
    ).is_file()
    assert not (output / "bin/pip").exists()
    assert not (output / "include").exists()
    assert not (output / "share/man").exists()
    assert not (output / "lib/libtcl9.0.dylib").exists()
    for forbidden in (
        "site-packages",
        "ensurepip",
        "venv",
        "tkinter",
        "idlelib",
        "lib2to3",
        "turtledemo",
        "test",
        "config-3.12-darwin",
        "__pycache__",
    ):
        assert not any(path.name == forbidden for path in output.rglob("*"))
    assert not (output / "lib/python3.12/lib-dynload/_tkinter.cpython-312-darwin.so").exists()
    assert not any(path.is_symlink() for path in output.rglob("*"))


def test_mongodb_staging_keeps_mongod_and_distribution_notices_only(tmp_path: Path) -> None:
    stager = load_stager()
    source = tmp_path / "mongo-source"
    write(source / "bin/mongod", b"mongod", 0o755)
    write(source / "bin/mongos", b"mongos", 0o755)
    write(source / "bin/install_compass", b"installer", 0o755)
    write(source / "LICENSE-Community.txt")
    write(source / "THIRD-PARTY-NOTICES")
    write(source / "MPL-2")
    write(source / "README")

    output = tmp_path / "mongo-output"
    stager.stage_component("mongodb", source, output, source_date_epoch=1_700_000_000)

    assert sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()) == [
        "LICENSE-Community.txt",
        "MPL-2",
        "THIRD-PARTY-NOTICES",
        "bin/mongod",
    ]


def test_staging_fails_closed_on_existing_output_and_unsafe_source(tmp_path: Path) -> None:
    stager = load_stager()
    source = tmp_path / "node-source"
    write(source / "bin/node", b"node-runtime", 0o755)
    write(source / "LICENSE", b"node-license")
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(stager.StagingError, match="already exists"):
        stager.stage_component("node", source, output, source_date_epoch=1_700_000_000)

    output.rmdir()
    source_link = tmp_path / "source-link"
    source_link.symlink_to(source, target_is_directory=True)
    with pytest.raises(stager.StagingError, match="real directory"):
        stager.stage_component("node", source_link, output, source_date_epoch=1_700_000_000)

    assert not output.exists()
    assert not any(path.name == "__pycache__" for path in tmp_path.rglob("*"))


def test_staging_rejects_output_symlink_ancestors_and_source_containment(tmp_path: Path) -> None:
    stager = load_stager()
    source = tmp_path / "node-source"
    write(source / "bin/node", b"node-runtime", 0o755)
    write(source / "LICENSE", b"node-license")
    external = tmp_path / "external"
    external.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(external, target_is_directory=True)

    with pytest.raises(stager.StagingError, match="ancestor is a symlink"):
        stager.stage_component(
            "node",
            source,
            linked_parent / "output",
            source_date_epoch=1_700_000_000,
        )
    with pytest.raises(stager.StagingError, match="outside the source"):
        stager.stage_component(
            "node",
            source,
            source / "nested-output",
            source_date_epoch=1_700_000_000,
        )

    assert list(external.iterdir()) == []
    assert not (source / "nested-output").exists()


def test_staging_accepts_only_the_canonical_macos_var_alias(tmp_path: Path) -> None:
    if sys.platform != "darwin" or not Path("/var").is_symlink():
        pytest.skip("macOS system alias contract")
    stager = load_stager()
    source = tmp_path / "node-source"
    write(source / "bin/node", b"node-runtime", 0o755)
    write(source / "LICENSE", b"node-license")
    assert tmp_path.parts[:3] == ("/", "private", "var")
    aliased_parent = Path("/var").joinpath(*tmp_path.parts[3:])
    aliased_output = aliased_parent / "alias-output"

    stager.stage_component(
        "node",
        source,
        aliased_output,
        source_date_epoch=1_700_000_000,
    )

    assert (tmp_path / "alias-output" / "bin" / "node").is_file()
