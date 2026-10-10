"""A GUI launch can find the native vendor install without changing CLI selection."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4/viventium-librechat-start.sh"


def _run(tmp_path, *, override=None, path_binary=False, executable=True, symlink=False):
    text = LAUNCHER.read_text()
    start = text.index("configure_glasshive_grok_binary() {\n")
    function = text[start : text.index("\n}\n", start) + 3]
    home = tmp_path / "user home"
    vendor = home / ".grok/bin/grok"
    vendor.parent.mkdir(parents=True)
    vendor.write_text("#!/bin/sh\nexit 0\n")
    vendor.chmod(0o700 if executable else 0o600)
    if symlink:
        target = vendor.parent.parent / "downloads/native-cli"
        target.parent.mkdir()
        vendor.rename(target)
        vendor.symlink_to("../downloads/native-cli")
    path = tmp_path / "path-bin"
    path.mkdir()
    if path_binary:
        selected = path / "grok"
        selected.write_text("#!/bin/sh\nexit 0\n")
        selected.chmod(0o700)
    env = {"HOME": str(home), "PATH": str(path)}
    if override is not None:
        env["WPR_GROK_BIN"] = override
    result = subprocess.run(
        ["/bin/bash", "-c", function + '\nconfigure_glasshive_grok_binary\nprintf "%s\\n%s" "${WPR_GROK_BIN:-}" "$PATH"'],
        env=env, capture_output=True, text=True, check=True,
    )
    selected, retained_path = result.stdout.split("\n", 1)
    assert retained_path == str(path)
    return selected, vendor


def test_vendor_install_is_found_without_shell_path(tmp_path):
    selected, vendor = _run(tmp_path)
    assert selected == str(vendor)


def test_native_relative_symlink_is_found(tmp_path):
    selected, vendor = _run(tmp_path, symlink=True)
    assert selected == str(vendor)


def test_explicit_relative_override_is_preserved(tmp_path):
    selected, _ = _run(tmp_path, override="selected-cli")
    assert selected == "selected-cli"


def test_explicit_override_is_preserved_even_when_missing(tmp_path):
    selected, _ = _run(tmp_path, override="/selected/missing-native-cli")
    assert selected == "/selected/missing-native-cli"


def test_existing_path_selection_is_preserved(tmp_path):
    selected, _ = _run(tmp_path, path_binary=True)
    assert selected == ""


def test_nonexecutable_vendor_install_remains_unavailable(tmp_path):
    selected, _ = _run(tmp_path, executable=False)
    assert selected == ""


def test_missing_vendor_install_remains_unavailable(tmp_path):
    text = LAUNCHER.read_text()
    start = text.index("configure_glasshive_grok_binary() {\n")
    function = text[start : text.index("\n}\n", start) + 3]
    result = subprocess.run(
        ["/bin/bash", "-c", function + '\nconfigure_glasshive_grok_binary\nprintf "%s" "${WPR_GROK_BIN:-}"'],
        env={"HOME": str(tmp_path), "PATH": str(tmp_path)},
        capture_output=True, text=True, check=True,
    )
    assert result.stdout == ""


def test_host_discovery_runs_before_native_launch():
    text = LAUNCHER.read_text()
    start = text.index("start_glasshive() {\n")
    body = text[start : text.index("\n}\n", start) + 3]
    assert body.index("configure_glasshive_grok_binary") < body.index("uv run uvicorn")
