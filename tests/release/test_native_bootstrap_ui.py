from __future__ import annotations

import os
import plistlib
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "apps" / "macos" / "ViventiumBootstrap"
SOURCE = PACKAGE / "Sources" / "ViventiumBootstrap" / "main.swift"
INFO_PLIST = PACKAGE / "Sources" / "ViventiumBootstrap" / "Info.plist"


def test_finder_launch_has_an_accessible_bounded_easy_install_window() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for required in (
        "import AppKit",
        "CommandLine.arguments.dropFirst().isEmpty",
        '"Easy Install Viventium"',
        "NSProgressIndicator",
        '"Cancel"',
        '"Retry"',
        '"Open Viventium"',
        '"Quit"',
        "accessibilityDisplayShouldReduceMotion",
        "setAccessibilityLabel",
        "setAccessibilityHelp",
        'keyEquivalent = "\\r"',
        'keyEquivalent = "\\u{1b}"',
        '"Cancel requested — finishing a safe checkpoint…"',
        "process.interrupt()",
        "process.terminate()",
        "Darwin.kill(process.processIdentifier, SIGKILL)",
        'URL(string: "http://127.0.0.1:3190")',
    ):
        assert required in source


def test_finder_launch_announces_dynamic_status_without_exposing_child_output() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "private func updateStatus(" in source
    assert "NSAccessibility.post(" in source
    assert "notification: .announcementRequested" in source
    assert ".announcement: stage" in source
    assert "updateStatus(" in source.split("@objc private func requestCancel()", 1)[1]


def test_finder_launch_never_renders_child_output_or_unbounded_logs() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "process.standardOutput = FileHandle.nullDevice" in source
    assert "process.standardError = FileHandle.nullDevice" in source
    assert "readDataToEndOfFile" not in source
    assert "terminationReason" not in source
    assert "localizedDescription" not in source


@pytest.fixture(scope="module")
def compiled_bootstrap(tmp_path_factory: pytest.TempPathFactory) -> Path:
    scratch = tmp_path_factory.mktemp("native-bootstrap-swift-build")
    build = subprocess.run(
        [
            "swift",
            "build",
            "--package-path",
            str(PACKAGE),
            "--scratch-path",
            str(scratch),
            "-c",
            "debug",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert build.returncode == 0, build.stderr
    show_bin = subprocess.run(
        [
            "swift",
            "build",
            "--package-path",
            str(PACKAGE),
            "--scratch-path",
            str(scratch),
            "-c",
            "debug",
            "--show-bin-path",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert show_bin.returncode == 0, show_bin.stderr
    binary = Path(show_bin.stdout.strip()) / "ViventiumBootstrap"
    assert binary.is_file()
    return binary


def test_compiled_cli_forwards_exact_arguments_streams_and_exit_status(
    tmp_path: Path, compiled_bootstrap: Path
) -> None:
    app = tmp_path / "ViventiumBootstrap.app"
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    bundled_python = resources / "runtime" / "python" / "bin" / "python3"
    installer = resources / "scripts" / "install_native_payload.py"
    macos.mkdir(parents=True)
    bundled_python.parent.mkdir(parents=True)
    installer.parent.mkdir(parents=True)
    shutil.copy2(compiled_bootstrap, macos / "ViventiumBootstrap")
    shutil.copy2(INFO_PLIST, app / "Contents" / "Info.plist")
    installer.write_text("# synthetic installer fixture\n", encoding="utf-8")
    bundled_python.write_text(
        "#!/bin/sh\n"
        "set -u\n"
        "if [ \"$#\" -ne 6 ] || [ \"$1\" != \"-E\" ] || [ \"$2\" != \"-s\" ] || "
        "[ \"$3\" != \"-B\" ] || "
        f"[ \"$4\" != \"{installer}\" ] || "
        "[ \"$5\" != \"--self-check\" ] || [ \"$6\" != \"synthetic-value\" ]; then\n"
        "  printf 'unexpected arguments\\n' >&2\n"
        "  exit 91\n"
        "fi\n"
        "if [ \"${PYTHONNOUSERSITE:-}\" != \"1\" ] || "
        "[ \"${PYTHONPATH+x}\" = x ] || [ \"${PYTHONHOME+x}\" = x ] || "
        "[ \"${PYTHONSTARTUP+x}\" = x ]; then\n"
        "  printf 'unsafe Python environment\\n' >&2\n"
        "  exit 92\n"
        "fi\n"
        "printf 'synthetic stdout\\n'\n"
        "printf 'synthetic stderr\\n' >&2\n"
        "exit 23\n",
        encoding="utf-8",
    )
    os.chmod(bundled_python, 0o755)

    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        result = subprocess.run(
            [
                str(macos / "ViventiumBootstrap"),
                "--self-check",
                "synthetic-value",
            ],
            check=False,
            stdout=stdout,
            stderr=stderr,
            env={
                **os.environ,
                "PYTHONPATH": str(tmp_path / "injected-pythonpath"),
                "PYTHONHOME": str(tmp_path / "injected-pythonhome"),
                "PYTHONSTARTUP": str(tmp_path / "injected-startup.py"),
            },
            timeout=30,
        )

    assert result.returncode == 23
    assert stdout_path.read_text(encoding="utf-8") == "synthetic stdout\n"
    assert stderr_path.read_text(encoding="utf-8") == "synthetic stderr\n"


def test_bootstrap_app_is_declared_as_a_regular_foreground_app() -> None:
    with INFO_PLIST.open("rb") as handle:
        info = plistlib.load(handle)

    assert info["CFBundleDisplayName"] == "Viventium Bootstrap"
    assert info["CFBundlePackageType"] == "APPL"
    assert info.get("LSUIElement") is not True
    assert info.get("LSBackgroundOnly") is not True


def test_signed_bootstrap_refuses_pending_restore_before_download_or_activation() -> None:
    installer = (
        REPO_ROOT / "scripts" / "viventium" / "install_native_payload.py"
    ).read_text(encoding="utf-8")
    install_body = installer.split("def install(args: argparse.Namespace) -> None:", 1)[1]

    assert "native-restore-transaction.json" in installer
    assert install_body.index("refuse_pending_native_restore(support)") < install_body.index(
        "download("
    )


def test_python_bootstrap_cancel_terminates_the_owned_process_group(tmp_path: Path) -> None:
    scripts = REPO_ROOT / "scripts" / "viventium"
    ready = tmp_path / "descendant-ready"
    child = tmp_path / "owned-child.py"
    wrapper = tmp_path / "bootstrap-wrapper.py"

    child.write_text(
        "import signal, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "ready = Path(sys.argv[1])\n"
        "program = (\n"
        "    'import signal, sys, time\\n'\n"
        "    'from pathlib import Path\\n'\n"
        "    'signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n'\n"
        "    f'Path({str(ready)!r}).write_text(str(__import__(\"os\").getpid()) + \"\\\\n\", encoding=\"utf-8\")\\n'\n"
        "    'time.sleep(60)\\n'\n"
        ")\n"
        "subprocess.Popen([sys.executable, '-c', program])\n"
        "deadline = time.monotonic() + 10\n"
        "while not ready.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        "if not ready.exists():\n"
        "    raise SystemExit(91)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    wrapper.write_text(
        "import signal, sys\n"
        f"sys.path.insert(0, {str(scripts)!r})\n"
        "import install_native_payload as installer\n"
        "signal.signal(signal.SIGTERM, installer.raise_install_cancel)\n"
        "try:\n"
        f"    installer.run_owned_process([{sys.executable!r}, {str(child)!r}, {str(ready)!r}])\n"
        "except KeyboardInterrupt:\n"
        "    raise SystemExit(130)\n",
        encoding="utf-8",
    )

    process = subprocess.Popen([sys.executable, str(wrapper)])
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists(), f"owned descendant did not start; wrapper exit={process.poll()}"
    descendant_pid = int(ready.read_text(encoding="utf-8").strip())

    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=15) == 130
    deadline = time.monotonic() + 5
    descendant_state = ""
    while time.monotonic() < deadline:
        observed = subprocess.run(
            ["/bin/ps", "-p", str(descendant_pid), "-o", "state="],
            check=False,
            capture_output=True,
            text=True,
        )
        descendant_state = observed.stdout.strip()
        if observed.returncode != 0 or not descendant_state:
            break
        time.sleep(0.01)
    assert not descendant_state, f"owned descendant survived cancellation: {descendant_state}"
