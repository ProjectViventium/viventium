from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_installer():
    scripts = ROOT / "scripts" / "viventium"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        "native_installer_diagnostics_test", scripts / "install_native_payload.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("exit_code", [0, 1])
def test_native_child_error_reaches_operator_without_exposing_stdout(
    tmp_path: Path, capfd: pytest.CaptureFixture, exit_code: int
) -> None:
    installer = load_installer()
    release = tmp_path / "release"
    executable = release / "bin" / "viventium-native-install"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/bin/sh\n"
        "printf 'private setup output\\n'\n"
        "printf 'Viventium Native: synthetic setup failure\\n' >&2\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    assert installer.run_release(release, "install", tmp_path / "support") is (
        exit_code == 0
    )
    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == "Viventium Native: synthetic setup failure\n"


def test_missing_native_child_still_reports_failure(tmp_path: Path) -> None:
    assert load_installer().run_release(tmp_path / "missing", "install", tmp_path) is False
