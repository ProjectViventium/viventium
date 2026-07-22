from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "verify_native_component_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("native_component_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fixture_tree(tmp_path: Path) -> Path:
    root = tmp_path / "python"
    executable = root / "bin" / "python3"
    executable.parent.mkdir(parents=True)
    executable.write_text("synthetic interpreter\n", encoding="utf-8")
    executable.chmod(0o755)
    license_file = root / "share" / "licenses" / "python-build-standalone" / "cpython.txt"
    license_file.parent.mkdir(parents=True)
    license_file.write_text("synthetic license\n", encoding="utf-8")
    license_file.chmod(0o644)
    return root


def test_component_manifest_binds_every_file_mode_size_digest_and_policy(tmp_path: Path) -> None:
    module = load_module()
    root = fixture_tree(tmp_path)
    component = {
        "archive_sha256": "a" * 64,
        "license_source_commit": "b" * 40,
        "license_source_sha256": "c" * 64,
        "version": "3.12.13",
    }
    manifest = module.build_manifest(root, name="python", component=component)
    manifest_path = tmp_path / "python-runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    verified = module.verify(root, manifest_path, expected_name="python")
    assert verified["component"] == {"name": "python", **component}
    assert [record["path"] for record in verified["files"]] == [
        "bin/python3",
        "share/licenses/python-build-standalone/cpython.txt",
    ]
    assert verified["root_mode"] == 0o755
    assert verified["directories"]
    assert all(len(record["sha256"]) == 64 for record in verified["files"])
    assert len(verified["tree_sha256"]) == 64


@pytest.mark.parametrize(
    "mutation", ["content", "mode", "directory_mode", "extra", "missing"]
)
def test_component_manifest_fails_closed_on_any_tree_mutation(
    tmp_path: Path, mutation: str
) -> None:
    module = load_module()
    root = fixture_tree(tmp_path)
    manifest_path = tmp_path / "python-runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(
            module.build_manifest(
                root,
                name="python",
                component={"archive_sha256": "a" * 64, "version": "3.12.13"},
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    executable = root / "bin" / "python3"
    if mutation == "content":
        executable.write_text("tampered\n", encoding="utf-8")
    elif mutation == "mode":
        executable.chmod(0o700)
    elif mutation == "directory_mode":
        (root / "bin").chmod(0o700)
    elif mutation == "extra":
        (root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    else:
        executable.unlink()

    with pytest.raises(module.ComponentManifestError):
        module.verify(root, manifest_path, expected_name="python")


def test_component_manifest_rejects_symlinks(tmp_path: Path) -> None:
    module = load_module()
    root = fixture_tree(tmp_path)
    (root / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(module.ComponentManifestError, match="symlink"):
        module.build_manifest(
            root,
            name="python",
            component={"archive_sha256": "a" * 64, "version": "3.12.13"},
        )


def test_native_workflows_verify_payload_and_bootstrap_component_manifests() -> None:
    candidate = (REPO_ROOT / ".github/workflows/native-payload-candidate.yml").read_text()
    release = (REPO_ROOT / ".github/workflows/native-payload-release.yml").read_text()
    for source in (candidate, release):
        assert source.count("verify_native_component_manifest.py") >= 2
        assert "payload/release-metadata/python-runtime-manifest.json" in source
        assert "ViventiumBootstrap.app/Contents/Resources/python-runtime-manifest.json" in source
    assert release.count("verify_native_component_manifest.py") >= 3
