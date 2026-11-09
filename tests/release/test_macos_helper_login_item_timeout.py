"""Login-item removal uses the existing bounded AppleScript process owner."""

import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/viventium/install_macos_helper.sh"


def removal(tmp_path, *, delay=0, status=0, skip=False):
    marker = tmp_path / "synthetic-call"
    executable = tmp_path / "fake osascript"
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import os, pathlib, sys, time\n"
        "script = sys.stdin.read()\n"
        "assert 'delete login item \"Viventium\"' in script\n"
        "pathlib.Path(os.environ['SYNTHETIC_CALL_MARKER']).write_text('called')\n"
        "time.sleep(float(os.environ['SYNTHETIC_DELAY']))\n"
        "raise SystemExit(int(os.environ['SYNTHETIC_STATUS']))\n"
    )
    executable.chmod(0o700)
    source = SCRIPT.read_text()
    start = source.index("unregister_login_item() {")
    function = source[start:source.index("\n}\n", start) + 3]
    # Replace only the external executable in the extracted production function;
    # this test must never operate the machine's actual login items.
    assert function.count('["/usr/bin/osascript"]') == 1
    function = function.replace('["/usr/bin/osascript"]', "[" + repr(str(executable)) + "]")
    program = (
        "resolve_repo_python() { printf '%s\\n' " + shlex.quote(sys.executable) + "; }\n"
        f"SKIP_LOGIN_ITEM={int(skip)}\nOSASCRIPT_TIMEOUT_SECONDS=1\n"
        + function + "\nunregister_login_item\n"
    )
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL"}}
    environment.update(SYNTHETIC_CALL_MARKER=str(marker), SYNTHETIC_DELAY=str(delay), SYNTHETIC_STATUS=str(status))
    return subprocess.run(["bash", "-c", program], env=environment, capture_output=True,
                          text=True, timeout=5), marker


def test_login_item_removal_times_out_without_hanging_the_installer(tmp_path):
    result, marker = removal(tmp_path, delay=3)
    assert marker.read_text() == "called"
    assert result.returncode == 124
    assert "Login-item removal timed out" in result.stderr


@pytest.mark.parametrize("status", [0, 7])
def test_login_item_removal_preserves_the_command_result(tmp_path, status):
    result, marker = removal(tmp_path, status=status)
    assert marker.read_text() == "called"
    assert result.returncode == status
    assert "timed out" not in result.stderr


def test_skipped_login_item_removal_does_not_invoke_the_command(tmp_path):
    result, marker = removal(tmp_path, delay=2, skip=True)
    assert result.returncode == 0
    assert not marker.exists()
