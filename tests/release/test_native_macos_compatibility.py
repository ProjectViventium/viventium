from __future__ import annotations

import importlib.util
import plistlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "verify_native_macos_compatibility.py"
POLICY = ROOT / "release" / "native-payload" / "minimum-macos"


def load_verifier():
    spec = importlib.util.spec_from_file_location("native_macos_compatibility_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_candidate(root: Path) -> tuple[Path, Path]:
    candidate = root / "candidate"
    payload = candidate / "payload"
    tool = payload / "runtime" / "bin" / "tool"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"\xcf\xfa\xed\xfe synthetic Mach-O fixture")
    tool.chmod(0o755)
    metadata = payload / "release-metadata" / "apple-code-paths.txt"
    metadata.parent.mkdir(parents=True)
    metadata.write_text("runtime/bin/tool\n", encoding="utf-8")

    bootstrap = candidate / "bootstrap" / "ViventiumBootstrap.app"
    executable = bootstrap / "Contents" / "MacOS" / "ViventiumBootstrap"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"\xcf\xfa\xed\xfe synthetic bootstrap fixture")
    executable.chmod(0o755)
    info = bootstrap / "Contents" / "Info.plist"
    info.write_bytes(
        plistlib.dumps(
            {
                "CFBundleExecutable": "ViventiumBootstrap",
                "LSMinimumSystemVersion": "13.0",
            }
        )
    )

    otool = root / "otool"
    otool.write_text(
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        "  */runtime/bin/tool) printf 'Load command 1\\n      cmd LC_BUILD_VERSION\\n platform 1\\n    minos 14.0\\n' ;;\n"
        "  *) printf 'Load command 1\\n      cmd LC_BUILD_VERSION\\n platform 1\\n    minos 13.0\\n' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    otool.chmod(0o755)
    return candidate, otool


def test_candidate_binary_targets_must_not_exceed_declared_minimum(tmp_path: Path) -> None:
    verifier = load_verifier()
    candidate, otool = fake_candidate(tmp_path)
    minimum = tmp_path / "minimum-macos"
    minimum.write_text("14.0\n", encoding="utf-8")
    result = verifier.verify(candidate, minimum, otool)
    assert result["maximum_binary_requirement"] == "14.0"
    assert result["checked_code_objects"] == 2

    minimum.write_text("13.0\n", encoding="utf-8")
    with pytest.raises(verifier.CompatibilityError, match="requires macOS 14.0"):
        verifier.verify(candidate, minimum, otool)


def test_nested_bundle_code_objects_are_all_enforced(tmp_path: Path) -> None:
    verifier = load_verifier()
    candidate, otool = fake_candidate(tmp_path)
    nested = (
        candidate
        / "bootstrap/ViventiumBootstrap.app/Contents/Resources/runtime/python/lib/libsynthetic.dylib"
    )
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"\xcf\xfa\xed\xfe synthetic nested Mach-O fixture")
    nested.chmod(0o755)
    otool.write_text(
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        "  */libsynthetic.dylib) printf 'Load command 1\\n      cmd LC_BUILD_VERSION\\n platform 1\\n    minos 15.0\\n' ;;\n"
        "  *) printf 'Load command 1\\n      cmd LC_BUILD_VERSION\\n platform 1\\n    minos 13.0\\n' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    otool.chmod(0o755)
    minimum = tmp_path / "minimum-macos"
    minimum.write_text("14.0\n", encoding="utf-8")

    with pytest.raises(verifier.CompatibilityError, match="requires macOS 15.0"):
        verifier.verify(candidate, minimum, otool)


def test_non_macos_code_object_is_rejected(tmp_path: Path) -> None:
    verifier = load_verifier()
    candidate, otool = fake_candidate(tmp_path)
    otool.write_text(
        "#!/bin/sh\n"
        "printf 'Load command 1\\n      cmd LC_BUILD_VERSION\\n platform 2\\n    minos 13.0\\n'\n",
        encoding="utf-8",
    )
    otool.chmod(0o755)
    minimum = tmp_path / "minimum-macos"
    minimum.write_text("14.0\n", encoding="utf-8")

    with pytest.raises(verifier.CompatibilityError, match="non-macOS platform"):
        verifier.verify(candidate, minimum, otool)


def test_unlisted_macho_object_is_rejected(tmp_path: Path) -> None:
    verifier = load_verifier()
    candidate, otool = fake_candidate(tmp_path)
    unlisted = candidate / "payload/runtime/lib/unlisted.dylib"
    unlisted.parent.mkdir(parents=True)
    unlisted.write_bytes(b"\xcf\xfa\xed\xfe synthetic unlisted Mach-O fixture")
    unlisted.chmod(0o755)
    minimum = tmp_path / "minimum-macos"
    minimum.write_text("14.0\n", encoding="utf-8")

    with pytest.raises(verifier.CompatibilityError, match="does not cover every Mach-O"):
        verifier.verify(candidate, minimum, otool)


def test_native_minimum_macos_policy_is_consistent_across_apps_build_and_release() -> None:
    assert POLICY.read_text(encoding="utf-8") == "14.0\n"
    helper_plist = plistlib.loads(
        (ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/Resources/Info.plist").read_bytes()
    )
    bootstrap_plist = plistlib.loads(
        (ROOT / "apps/macos/ViventiumBootstrap/Sources/ViventiumBootstrap/Info.plist").read_bytes()
    )
    assert helper_plist["LSMinimumSystemVersion"] == "13.0"
    assert bootstrap_plist["LSMinimumSystemVersion"] == "13.0"
    assert ".macOS(.v13)" in (ROOT / "apps/macos/ViventiumHelper/Package.swift").read_text(encoding="utf-8")
    assert ".macOS(.v13)" in (ROOT / "apps/macos/ViventiumBootstrap/Package.swift").read_text(encoding="utf-8")

    candidate_workflow = (ROOT / ".github/workflows/native-payload-candidate.yml").read_text(encoding="utf-8")
    release_workflow = (ROOT / ".github/workflows/native-payload-release.yml").read_text(encoding="utf-8")
    assert "verify_native_macos_compatibility.py" in candidate_workflow
    assert "verify_native_macos_compatibility.py" in release_workflow
    assert '--minimum-macos "$MINIMUM_MACOS"' in release_workflow
    assert 'current_macos=os.environ["MINIMUM_MACOS"]' in release_workflow
    assert 'minimum_macos = Path("release/native-payload/minimum-macos").read_text' in release_workflow
    assert "current_macos=minimum_macos" in release_workflow
    assert "--minimum-macos 13.0" not in release_workflow

    public_bootstrap = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'NATIVE_BOOTSTRAP_MINIMUM_MACOS="14.0"' in public_bootstrap
    assert "requires macOS" in public_bootstrap
